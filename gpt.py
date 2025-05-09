import json
import os
import sys
import signal
import psycopg2
from datetime import datetime
import openai
from openai import OpenAIError
import anyio
import time
import logging
import psycopg2.extras
from typing import Dict, Any, Optional, Union

from websocket_manager import manager


OPENAI_API_KEY = ""
DATABASE_URL = "postgresql://neondb_owner:npg_Emq9gohbK8se@ep-ancient-smoke-a4h6qbnr-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require"
OPENAI_ASSISTANT_ID = "asst_fbnh9vuQ3TsMkPxtWpiFpjaE"
POLL_INTERVAL = 10

openai.api_key = OPENAI_API_KEY

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ClaimsProcessor:
    def __init__(self):
        self.db_conn = None
        self.running = True
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

    def _handle_shutdown(self, signum, frame):
        logger.info("Shutdown signal received, cleaning up...")
        self.running = False

    def _get_db_connection(self):
        try:
            if self.db_conn is None or self.db_conn.closed:
                self.db_conn = psycopg2.connect(DATABASE_URL)
                logger.info("Database connection established")
            return self.db_conn
        except psycopg2.Error as e:
            logger.error(f"Database connection error: {str(e)}")
            raise

    def _safe_json_load(self, value: Union[str, list]) -> list:
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return []
        elif isinstance(value, list):
            return value
        return []

    def _enrich_claim(self, claim: Dict[str, Any]) -> Dict[str, Any]:
        enriched_claim = {k: v for k, v in claim.items() if k != 'created_at'}
        for k, v in enriched_claim.items():
            if isinstance(v, datetime):
                enriched_claim[k] = v.isoformat()
        for section in ['drugs', 'medical_procedures', 'lab_tests']:
            enriched_claim[section] = self._safe_json_load(enriched_claim.get(section, []))
        if 'legend' in enriched_claim:
            enriched_claim['legend'] = self._safe_json_load(enriched_claim['legend'])
        return enriched_claim

    def _send_to_assistant(self, claim_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            thread = openai.beta.threads.create()
            openai.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content=json.dumps(claim_data)
            )
            run = openai.beta.threads.runs.create(
                assistant_id=OPENAI_ASSISTANT_ID,
                thread_id=thread.id
            )

            timeout = time.time() + 120
            while time.time() < timeout:
                run_status = openai.beta.threads.runs.retrieve(
                    thread_id=thread.id, run_id=run.id
                )
                if run_status.status == "completed":
                    break
                elif run_status.status in ["failed", "expired", "cancelled"]:
                    logger.error(f"Assistant run failed with status: {run_status.status}")
                    return None
                time.sleep(1)
            else:
                logger.error("Assistant run timed out")
                return None

            messages = openai.beta.threads.messages.list(thread_id=thread.id)
            assistant_message = next((m for m in reversed(messages.data) if m.role == "assistant"), None)

            if not assistant_message:
                logger.error("No assistant message found.")
                return None

            response_text = assistant_message.content[0].text.value.strip()
            if response_text.startswith("```json"):
                response_text = response_text.replace("```json", "").replace("```", "").strip()

            parsed = json.loads(response_text)
            return self._validate_assistant_response(parsed)

        except OpenAIError as e:
            logger.error(f"OpenAI API error: {str(e)}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse assistant response as JSON: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in send_to_assistant: {str(e)}")
            return None

    def _validate_assistant_response(self, response: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        required_fields = ["claim_status", "approved_total", "flagged_excess", "reason"]
        valid_statuses = {"approved", "rejected", "flagged"}
        for field in required_fields:
            if field not in response:
                logger.error(f"Assistant response missing required field: {field}")
                return None
        parsed_status = str(response["claim_status"]).strip().lower()
        if parsed_status not in valid_statuses:
            logger.error(f"Invalid claim_status: '{parsed_status}' - must be one of {valid_statuses}")
            return None
        try:
            response["approved_total"] = float(response["approved_total"])
        except (ValueError, TypeError):
            logger.error(f"Invalid approved_total: {response['approved_total']} - must be a number")
            return None
        response["claim_status"] = parsed_status
        return response

    def _update_claim_status(self, encounter_token: str, response: Dict[str, Any]) -> bool:
        conn = self._get_db_connection()
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
                    response["claim_status"],
                    response["approved_total"],
                    response["reason"],
                    encounter_token
                ))
                conn.commit()
                logger.info(f"Updated claim {encounter_token} → {response['claim_status']}")
                try:
                    await anyio.to_thread.run_sync(manager.send_notification, "2", response["claim_status"])
                except Exception as notify_error:
                    logger.warning(f"WebSocket notify failed: {notify_error}")
                return True
        except psycopg2.Error as e:
            conn.rollback()
            logger.error(f"DB Update failed for claim {encounter_token}: {str(e)}")
            return False

    def process_pending_claims(self):
        try:
            conn = self._get_db_connection()
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute("SELECT * FROM claims WHERE status = %s", ('pending',))
                pending_claims = cursor.fetchall()
                if not pending_claims:
                    logger.info("No pending claims found.")
                    return
                logger.info(f"Found {len(pending_claims)} pending claims to process")
                for claim in pending_claims:
                    encounter_token = claim['encounter_token']
                    enriched_claim = self._enrich_claim(claim)
                    logger.info(f"Processing claim {encounter_token}")
                    gpt_response = self._send_to_assistant(enriched_claim)
                    if gpt_response:
                        success = self._update_claim_status(encounter_token, gpt_response)
                        if success:
                            logger.info(f"Claim {encounter_token} processed successfully")
                        else:
                            logger.error(f"Failed to update claim {encounter_token} in database")
                    else:
                        logger.warning(f"No valid response received for claim {encounter_token}")
        except psycopg2.Error as e:
            logger.error(f"Database error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error processing claims: {str(e)}")

    def run(self):
        logger.info("Claims processor starting...")
        while self.running:
            try:
                self.process_pending_claims()
                logger.info(f"Waiting {POLL_INTERVAL} seconds for new pending claims...")
                for _ in range(POLL_INTERVAL):
                    if not self.running:
                        break
                    time.sleep(1)
            except Exception as e:
                logger.error(f"Error in main processing loop: {str(e)}")
                time.sleep(5)
        if self.db_conn and not self.db_conn.closed:
            self.db_conn.close()
            logger.info("Database connection closed")
        logger.info("Claims processor shutdown complete")


if __name__ == "__main__":
    processor = ClaimsProcessor()
    processor.run()
