import json
import psycopg2
import psycopg2.extras
from datetime import datetime
import openai
import time  # Import the time module for sleep functionality

# Database and API connection strings
DATABASE_URL = "postgresql://neondb_owner:npg_Emq9gohbK8se@ep-yellow-dust-a45jsws7-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require"
OPENAI_API_KEY = "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"
ASSISTANT_ID = "asst_fbnh9vuQ3TsMkPxtWpiFpjaE"

# Initialize OpenAI client
openai.api_key = OPENAI_API_KEY

def process_pending_claims():
    time.sleep(20)
    """
    Retrieve a pending claim, send it to ChatGPT for assessment,
    and update the database with the standardized response.
    """
    try:
        with psycopg2.connect(DATABASE_URL) as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                # Query pending claim
                cursor.execute("""
                    SELECT * FROM claims 
                    WHERE status = %s 
                    LIMIT 1
                """, ('pending',))

                pending_claim = cursor.fetchone()
                if not pending_claim:
                    print(json.dumps({"message": "No pending claims found."}, indent=2))
                    return
                
                # Store encounter_token for later update
                claim_encounter_token = pending_claim['encounter_token']
                
                # Create a copy of the claim data excluding created_at
                claim_data_for_processing = {k: v for k, v in pending_claim.items() if k != 'created_at'}
                
                # Convert remaining datetime fields to strings
                for key, value in claim_data_for_processing.items():
                    if isinstance(value, datetime):
                        claim_data_for_processing[key] = value.isoformat()

                # Enrich drugs list with medicine details
                if 'drugs' in claim_data_for_processing and isinstance(claim_data_for_processing['drugs'], list):
                    enriched_drugs = []
                    for drug in claim_data_for_processing['drugs']:
                        drug_code = drug.get('code')
                        if drug_code:
                            cursor.execute("""
                                SELECT * FROM medicines WHERE code = %s
                            """, (drug_code,))
                            medicine_details = cursor.fetchone()
                            if medicine_details:
                                drug['details'] = {k: v for k, v in medicine_details.items() if k != 'created_at'}
                        enriched_drugs.append(drug)
                    claim_data_for_processing['drugs'] = enriched_drugs

                # Enrich medical procedures with service details
                if 'medical_procedures' in claim_data_for_processing and isinstance(claim_data_for_processing['medical_procedures'], list):
                    enriched_procedures = []
                    for procedure_code in claim_data_for_processing['medical_procedures']:
                        cursor.execute("""
                            SELECT * FROM service_tariffs WHERE code = %s
                        """, (procedure_code,))
                        procedure_details = cursor.fetchone()
                        if procedure_details:
                            enriched_procedures.append({k: v for k, v in procedure_details.items() if k != 'created_at'})
                        else:
                            enriched_procedures.append({"code": procedure_code, "details": "Not covered by NHIS"})
                    claim_data_for_processing['medical_procedures'] = enriched_procedures

                # Enrich lab tests with service details
                if 'lab_tests' in claim_data_for_processing and isinstance(claim_data_for_processing['lab_tests'], list):
                    enriched_tests = []
                    for test_code in claim_data_for_processing['lab_tests']:
                        cursor.execute("""
                            SELECT * FROM service_tariffs WHERE code = %s
                        """, (test_code,))
                        test_details = cursor.fetchone()
                        if test_details:
                            enriched_tests.append({k: v for k, v in test_details.items() if k != 'created_at'})
                        else:
                            enriched_tests.append({"code": test_code, "details": "Not covered by NHIS"})
                    claim_data_for_processing['lab_tests'] = enriched_tests

                print("Enriched claim data (excluding created_at):")
                print(json.dumps(claim_data_for_processing, indent=2, default=str))
                
                # Send to ChatGPT for assessment and wait for response
                gpt_response = send_to_chatgpt(claim_data_for_processing)
                
                # Only proceed if we got a valid response
                if gpt_response and 'status' in gpt_response:
                    # Update the database with the response
                    update_claim_status(conn, claim_encounter_token, gpt_response)
                    
                    print("\nClaim processed successfully:")
                    print(json.dumps(gpt_response, indent=2))
                else:
                    print("\nFailed to get valid response from ChatGPT")
                    print(json.dumps({"error": "Invalid response from ChatGPT"}, indent=2))

    except Exception as e:
        print(json.dumps({"error": str(e)}, indent=2))
def send_to_chatgpt(claim_data):
    """
    Send the claim data to ChatGPT and get a standardized response back.
    """
    try:
        # Create system message to enforce standardized response format
        system_message = """
        You are a medical insurance claim processor. Analyze the provided claim data and return a JSON response with exactly these fields:
        1. status: Must be one of "Approved", "Flagged", or "Rejected"
        2. final_payout: Numerical value representing the approved payout amount.
        3. reason: Detailed explanation for your decision also state the drugs or medical treatments that arent covered by nhis.
        
        Base your decision on factors such as:
        - Whether the procedures and medications are appropriate for the diagnosis
        - Whether the charges appear reasonable
        - Any potential fraud indicators or policy violations
        - Whether all required documentation is present
        
        Your response MUST be a valid JSON object with only these three fields and nothing else.
        """
        
        # Convert claim data to string if needed
        claim_json = json.dumps(claim_data) if not isinstance(claim_data, str) else claim_data
        
        # Send to ChatGPT API
        response = openai.chat.completions.create(
            model="gpt-4-turbo",  # Or whichever model you prefer
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": f"Please analyze this medical claim:\n{claim_json}"}
            ],
            response_format={"type": "json_object"}
        )
        
        # Parse the response
        response_content = response.choices[0].message.content
        standardized_response = json.loads(response_content)
        
        # Validate response format
        required_keys = ["status", "final_payout", "reason"]
        valid_statuses = ["Approved", "Flagged", "Rejected"]
        
        for key in required_keys:
            if key not in standardized_response:
                raise ValueError(f"Response missing required field: {key}")
        
        if standardized_response["status"] not in valid_statuses:
            raise ValueError(f"Invalid status value. Must be one of: {valid_statuses}")
        
        return standardized_response
        
    except Exception as e:
        print(f"Error sending to ChatGPT: {str(e)}")
        # Return a fallback response if there's an error
        return {
            "status": "Flagged",
            "final_payout": 0,
            "reason": f"Error processing claim with AI: {str(e)}. Manual review required."
        }

def update_claim_status(conn, claim_encounter_token, gpt_response):
    """
    Update the claim in the database with the assessment from ChatGPT.
    Maps the standardized response fields to the correct database column names.
    """
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE claims
                SET 
                    status = %s,
                    total_payout = %s,
                    reason = %s
                WHERE encounter_token = %s
            """, (
                gpt_response["status"].lower(),  # Convert to lowercase to match your schema
                gpt_response["final_payout"],
                gpt_response["reason"],
                claim_encounter_token
            ))
            
            conn.commit()
            print(f"Successfully updated claim with encounter_token {claim_encounter_token} status to {gpt_response['status']}")
            
    except Exception as e:
        conn.rollback()
        print(f"Error updating claim status: {str(e)}")


if __name__ == "__main__":
    while True:  # Infinite loop to keep the script running
        process_pending_claims()  # Process one claim at a time
        print("Waiting for new pending claims...")
        time.sleep(0)  # Wait for 10 seconds before checking again