import random
import resend
from fastapi import HTTPException
from datetime import datetime, timedelta
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set Resend API key
resend.api_key = "re_SQ1dsFZy_C1kNPfFvNX5zs7Mzr2JW2qjj"  

def generate_otp():
    return str(random.randint(100000, 999999))

def send_otp_email(email: str, otp: str):
    try:
        response = resend.Emails.send({
            "from": "Acme <noreply@fvlcon.org>",  
            "to": email,  
            "subject": "Your 2FA Code",
            "html": f"<p>Your 2FA code is: <strong>{otp}</strong></p>"
        })
        logger.info(f"Email sent successfully: {response}")
        return response
    except Exception as e:
        logger.error(f"Failed to send email: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to send 2FA email")
