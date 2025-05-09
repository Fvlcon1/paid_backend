# otp_utils.py
import secrets
import string
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from .models import EmailTwoFactor  # Adjust the import based on your project structure

def generate_otp(length=6):
    """Generate a random numeric OTP of the specified length."""
    digits = string.digits
    return ''.join(secrets.choice(digits) for _ in range(length))

def is_otp_valid(db: Session, email: str, user_otp: str) -> bool:
    """
    Check if the OTP is valid and not expired.
    If the OTP is expired, delete the row from the database.
    """
    # Retrieve the latest OTP for the email
    db_otp = db.query(EmailTwoFactor).filter(EmailTwoFactor.email == email).order_by(EmailTwoFactor.created_at.desc()).first()

    if not db_otp:
        return False  # OTP not found

    # Check if the OTP has expired
    expiration_time = db_otp.created_at + timedelta(minutes=2)  # OTP expires after 2 minutes
    if datetime.utcnow() > expiration_time:
        # Delete the expird
    expiration_time = db_otp.created_at + timedelta(minutes=2)  # OTP expires after 2 minutes
    if datetime.utcnow() > expiration_time:
        # Delete the expired OTP row
        db.delete(db_otp)
        db.commit()
        return False  # OTP has expired

    # Check if the OTP matches
    if user_otp == db_otp.email_otp_secret:
        # Delete the OTP row after successful verification
        db.delete(db_otp)
        db.commit()
        return True  # OTP is valid

    return False  # OTP does not match

