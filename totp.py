import pyotp
import secrets
import json
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from db import User  # Import the User model

class TwoFactorAuth:
    """Helper class for 2FA operations"""
    
    @staticmethod
    def generate_totp_secret() -> str:
        """Generate a new TOTP secret key"""
        return pyotp.random_base32()
    
    @staticmethod
    def generate_backup_codes(count: int = 10) -> List[str]:
        """Generate backup codes for 2FA recovery"""
        return [secrets.token_hex(5).upper() for _ in range(count)]
    
    @staticmethod
    def get_totp_uri(secret: str, email: str, issuer: str = "PAIV System") -> str:
        """Generate a TOTP URI for QR code generation"""
        return pyotp.totp.TOTP(secret).provisioning_uri(
            name=email,
            issuer_name=issuer
        )
    
    @staticmethod
    def verify_totp(secret: str, code: str) -> bool:
        """Verify a TOTP code against the secret"""
        totp = pyotp.TOTP(secret)
        return totp.verify(code)
    
    @staticmethod
    def verify_backup_code(user, code: str) -> bool:
        """Verify and consume a backup code"""
        if not user.backup_codes:
            return False
        
        backup_codes = json.loads(user.backup_codes) if isinstance(user.backup_codes, str) else user.backup_codes
        
        if code in backup_codes:
            # Remove the used backup code
            backup_codes.remove(code)
            user.backup_codes = backup_codes
            return True
        return False

def setup_2fa(db: Session, user_id: int) -> Dict:
    """Set up 2FA for a user"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValueError("User not found")
    
    # Generate TOTP secret and backup codes
    secret = TwoFactorAuth.generate_totp_secret()
    backup_codes = TwoFactorAuth.generate_backup_codes()
    
    # Update user with 2FA information
    user.totp_secret = secret
    user.backup_codes = backup_codes
    user.is_2fa_enabled = False  # Will be enabled after verification
    db.commit()
    
    # Generate URI for QR code
    totp_uri = TwoFactorAuth.get_totp_uri(secret, user.email)
    
    return {
        "secret": secret,
        "totp_uri": totp_uri,
        "backup_codes": backup_codes
    }

def enable_2fa(db: Session, user_id: int, code: str) -> bool:
    """Verify and enable 2FA for a user"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.totp_secret:
        return False
    
    # Verify the provided code
    if TwoFactorAuth.verify_totp(user.totp_secret, code):
        user.is_2fa_enabled = True
        db.commit()
        return True
    return False

def verify_2fa(db: Session, user_id: int, code: str) -> bool:
    """Verify a 2FA code during login"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_2fa_enabled:
        return False
    
    # Check if it's a valid TOTP code
    if TwoFactorAuth.verify_totp(user.totp_secret, code):
        return True
    
    # If not a TOTP code, try backup code
    if TwoFactorAuth.verify_backup_code(user, code):
        db.commit()  # Save the updated backup codes
        return True
    
    return False

def disable_2fa(db: Session, user_id: int) -> bool:
    """Disable 2FA for a user"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return False
    
    user.is_2fa_enabled = False
    user.totp_secret = None
    user.backup_codes = None
    db.commit()
    return True

def regenerate_backup_codes(db: Session, user_id: int) -> Optional[List[str]]:
    """Regenerate backup codes for a user"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_2fa_enabled:
        return None
    
    backup_codes = TwoFactorAuth.generate_backup_codes()
    user.backup_codes = backup_codes
    db.commit()
    return backup_codes