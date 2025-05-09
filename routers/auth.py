# routers/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import timedelta
from typing import Dict
import logging

from schemas import UserCreate, UserLogin, UserResponse
from db import SessionLocal, User
from security import get_password_hash, verify_password, create_access_token

router = APIRouter(prefix="/auth", tags=["Auth"])
logger = logging.getLogger(__name__)

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Signup Route ---
@router.post("/signup", response_model=UserResponse)
def signup(user: UserCreate, db: Session = Depends(get_db)):
    try:
        existing_user = db.query(User).filter(User.email == user.email).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already registered")

        hashed_password = get_password_hash(user.password)
        new_user = User(
            hospital_name=user.hospital_name,
            email=user.email,
            password=hashed_password,
            location=user.location.dict()
        )

        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        return UserResponse(
            id=new_user.id,
            hospital_name=new_user.hospital_name,
            email=new_user.email
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        db.rollback()
        logger.error(f"Signup error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error during signup: {str(e)}")


# --- Login Route ---
@router.post("/login", response_model=Dict)
def login(login_data: UserLogin, db: Session = Depends(get_db)):
    try:
        user = db.query(User).filter(User.email == login_data.email).first()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not verify_password(login_data.password, user.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # If 2FA enabled, send short-lived token
        if user.is_email_2fa_enabled:
            short_lived_token = create_access_token(
                data={"email": user.email, "is_2fa": True},
                expires_delta=timedelta(minutes=5)
            )
            return {
                "require_2fa": True,
                "user_id": user.id,
                "temp_token": short_lived_token,
                "message": "2FA verification required"
            }

        # Otherwise issue access token
        access_token = create_access_token(
            data={"email": user.email},
            expires_delta=timedelta(hours=1)
        )
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "require_2fa": False
        }

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Login error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Unexpected login error: {str(e)}")


