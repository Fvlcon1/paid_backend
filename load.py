from dotenv import load_dotenv
import os

load_dotenv()


RESEND_API_KEY = os.getenv("RESEND_API_KEY")
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
