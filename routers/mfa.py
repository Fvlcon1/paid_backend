# routers/mfa.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import logging

from db import User, EmailTwoFactor, SessionLocal
from schemas import OTPVerification, TwoFactorSetup
from sendd import generate_otp, send_otp_email
from qr import generate_qr_code_base64
from security import create_access_token
from totp import setup_2fa, enable_2fa, verify_2fa, disable_2fa, regenerate_backup_codes
from dependencies import get_temp_user, get_current_user, get_db

router = APIRouter(prefix="/mfa", tags=["Multi-Factor Authentication"])
logger = logging.getLogger(__name__)

# Send OTP to email
@router.post("/send-otp")
def send_otp_email_route(
    db: Session = Depends(get_db),
    email: str = Depends(get_temp_user)
):
    try:
        otp = generate_otp()
        expires_at = datetime.utcnow() + timedelta(minutes=2)

        existing = db.query(EmailTwoFactor).filter(EmailTwoFactor.email == email).first()
        if existing:
            existing.otp = otp
            existing.created_at = datetime.utcnow()
            existing.expires_at = expires_at
        else:
            new_otp = EmailTwoFactor(email=email, otp=otp, expires_at=expires_at)
            db.add(new_otp)

        db.commit()
        send_otp_email(email, otp)

        return {"message": "OTP sent successfully"}
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to send OTP: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to send OTP")

# Verify OTP and return long-lived token
@router.post("/verify-otp")
def verify_otp_code(
    otp_data: OTPVerification,
    email: str = Depends(get_temp_user),
    db: Session = Depends(get_db)
):
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        record = db.query(EmailTwoFactor).filter(EmailTwoFactor.email == email).first()
        if not record or record.otp != otp_data.otp or record.expires_at < datetime.utcnow():
            raise HTTPException(status_code=401, detail="Invalid or expired OTP")

        access_token = create_access_token(data={"email": user.email}, expires_delta=timedelta(hours=1))
        db.delete(record)
        db.commit()

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "message": "OTP verified successfully"
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"OTP verification error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal error during OTP verification")

# Check MFA status
@router.get("/check-status")
def check_mfa_status(
    db: Session = Depends(get_db),
    user_email: str = Depends(get_temp_user)
):
    try:
        user = db.query(User).filter(User.email == user_email).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return {
            "email_2fa_enabled": user.is_email_2fa_enabled,
            "totp_2fa_enabled": user.is_2fa_enabled
        }
    except Exception as e:
        logger.error(f"Error checking MFA status: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Could not check MFA status")

# Setup TOTP 2FA
@router.post("/totp/setup", response_model=TwoFactorSetup)
def setup_totp_2fa(
    current_user_email: str = Depends(get_temp_user),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == current_user_email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.is_2fa_enabled or user.is_email_2fa_enabled:
        raise HTTPException(status_code=400, detail="2FA already enabled")

    setup_data = setup_2fa(db, user.id)
    setup_data["qr_code"] = generate_qr_code_base64(setup_data["totp_uri"])
    return setup_data

# Enable TOTP 2FA after code is verified
@router.post("/totp/enable")
def enable_totp(
    verification: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    totp_code = verification.get("totp_code")
    if not totp_code:
        raise HTTPException(status_code=400, detail="TOTP code is required")

    if current_user.is_2fa_enabled or current_user.is_email_2fa_enabled:
        raise HTTPException(status_code=400, detail="Another 2FA method is already enabled")

    success = enable_2fa(db, current_user.id, totp_code)
    if not success:
        raise HTTPException(status_code=400, detail="Invalid verification code")

    return {"message": "TOTP 2FA enabled successfully"}

# Disable 2FA
@router.post("/disable")
def disable_totp(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        disable_2fa(db, current_user.id)
        return {"message": "2FA disabled successfully"}
    except Exception as e:
        logger.error(f"Error disabling 2FA: {str(e)}")
        raise HTTPException(status_code=500, detail="Error disabling 2FA")

# Generate new backup codes
@router.post("/backup-codes")
def generate_new_backup_codes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    codes = regenerate_backup_codes(db, current_user.id)
    if not codes:
        raise HTTPException(status_code=400, detail="Failed to generate backup codes")
    return {"backup_codes": codes}


@router.post("/email/enable")
def enable_email_2fa(
    user_email: str = Depends(get_temp_user),
    db: Session = Depends(get_db)
):
    """
    Enables email-based 2FA for the user who has a valid temp token.
    """
    try:
        user = db.query(User).filter(User.email == user_email).first()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if user.is_email_2fa_enabled:
            raise HTTPException(status_code=400, detail="Email 2FA is already enabled")

        user.is_2fa_enabled = True
        user.is_email_2fa_enabled = True
        db.commit()
        db.refresh(user)

        logger.info(f"Email 2FA enabled for user: {user.email}")
        return {"message": "Email 2FA enabled successfully"}

    except Exception as e:
        db.rollback()
        logger.error(f"Error enabling Email 2FA for {user_email}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to enable Email 2FA")

@router.post("/verify")
def verify_totp_or_backup(
    verification: dict,
    db: Session = Depends(get_db),
    current_user_email: str = Depends(get_temp_user)
):
    code = verification.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="Verification code is required")

    user = db.query(User).filter(User.email == current_user_email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    success = verify_2fa(db, user.id, code)
    if not success:
        raise HTTPException(status_code=400, detail="Invalid verification code")

    return {"message": "2FA verification successful"}