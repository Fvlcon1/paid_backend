import json
import psycopg2
import psycopg2.extras
from datetime import datetime
import openai
import time

DATABASE_URL = "postgresql://neondb_owner:npg_Emq9gohbK8se@ep-ancient-smoke-a4h6qbnr-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


openai.api_key = OPENAI_API_KEY


def find_code_details(cursor, code_to_find, exclude_tables=None):
    exclude_tables = exclude_tables or set()
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
    """)
    tables = [row['table_name'] for row in cursor.fetchall()]

    for table in tables:
        if table in exclude_tables:
            continue

        try:
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = %s AND column_name = 'code'
            """, (table,))
            if cursor.fetchone():
                cursor.execute(f"SELECT * FROM {table} WHERE code = %s LIMIT 1", (code_to_find,))
                match = cursor.fetchone()
                if match:
                    return {**match, "source_table": table}
        except Exception as e:
            print(f"Skipped table {table}: {e}")
            continue
    return None

def process_pending_claims():
    time.sleep(20)
    try:
        with psycopg2.connect(DATABASE_URL) as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute("SELECT * FROM claims WHERE status = %s LIMIT 1", ('pending',))
                pending_claim = cursor.fetchone()
                if not pending_claim:
                    print(json.dumps({"message": "No pending claims found."}, indent=2))
                    return

                claim_encounter_token = pending_claim['encounter_token']
                claim_data = {k: v for k, v in pending_claim.items() if k != 'created_at'}

                for k, v in claim_data.items():
                    if isinstance(v, datetime):
                        claim_data[k] = v.isoformat()

                for section in ['drugs', 'medical_procedures', 'lab_tests']:
                    if section in claim_data and isinstance(claim_data[section], list):
                        enriched = []
                        for item in claim_data[section]:
                            code = item['code'] if isinstance(item, dict) else item
                            details = find_code_details(cursor, code, exclude_tables={'claims', 'services'})
                            enriched.append({
                                "code": code,
                                "details": {k: v for k, v in details.items() if k != 'created_at'} if details else "Not covered by NHIS"
                            })
                        claim_data[section] = enriched

                print("Enriched claim data:")
                print(json.dumps(claim_data, indent=2, default=str))

                gpt_response = send_to_chatgpt(claim_data)
                if gpt_response and 'claim_status' in gpt_response:
                    update_claim_status(conn, claim_encounter_token, gpt_response)
                    print("\nClaim processed successfully:")
                    print(json.dumps(gpt_response, indent=2))
                else:
                    print("\nFailed to get valid response from ChatGPT")
                    print(json.dumps({"error": "Invalid response from ChatGPT"}, indent=2))

    except Exception as e:
        print(json.dumps({"error": str(e)}, indent=2))

def send_to_chatgpt(claim_data):
    try:
        system_message = """
You are an NHIS claims processing assistant. Follow this strict 6-step validation policy to evaluate a medical claim:

Step 0: Check if diagnosis exists in the STG database.
Step 1: Validate that treatment and medications match the approved diagnosis-treatment pairs.
Step 2: Confirm that dosage, frequency, and duration are within STG limits.
Step 3: If overdose detected, compute approved quantity and flag excess.
Step 4: Sum up treatment, lab, and procedure costs.
Step 5: Compute approved total and flagged excess.
Step 6: Assign final decision:
  - "APPROVED" if all is within limits.
  - "REJECTED" if diagnosis/treatment mismatch or dosage is missing/invalid.
  - "ADJUSTMENT REQUIRED" if overdose is detected.

Return ONLY the following JSON object:

{
  "claim_status": "APPROVED | REJECTED | ADJUSTMENT REQUIRED",
  "approved_total": number,
  "flagged_excess": number,
  "reason": "Explain the reason for the decision and any uncovered items."
}

DO NOT include markdown, text, or headings. JSON object only.
"""

        user_message = json.dumps(claim_data)

        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_message.strip()},
                {"role": "user", "content": user_message}
            ],
            temperature=0.2
        )

        content = response['choices'][0]['message']['content'].strip()

        if content.startswith("```json"):
            content = content.replace("```json", "").replace("```", "").strip()

        parsed = json.loads(content)

        for field in ["claim_status", "approved_total", "flagged_excess", "reason"]:
            if field not in parsed:
                raise ValueError(f"Missing field: {field}")
        return parsed

    except Exception as e:
        print(f"ChatGPT JSON parsing error: {str(e)}")
        return {
            "claim_status": "ADJUSTMENT REQUIRED",
            "approved_total": 0,
            "flagged_excess": 0,
            "reason": f"Error processing claim: {str(e)}. Manual review required."
        }

def update_claim_status(conn, encounter_token, response):
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE claims
                SET 
                    status = %s,
                    total_payout = %s,
                    excess_amount = %s,
                    reason = %s
                WHERE encounter_token = %s
            """, (
                response["claim_status"].lower(),
                response["approved_total"],
                response["flagged_excess"],
                response["reason"],
                encounter_token
            ))
            conn.commit()
            print(f"Updated claim {encounter_token} → {response['claim_status']}")
    except Exception as e:
        conn.rollback()
        print(f"DB Update failed: {str(e)}")

if __name__ == "__main__":
    while True:
        process_pending_claims()
        print("Waiting for new pending claims...")
        time.sleep(10)
