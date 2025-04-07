# routers/users.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import logging

from db import User, SessionLocal
from schemas import UserCreate, UserResponse
from security import get_password_hash, decode_access_token
from dependencies import get_current_user, get_db

router = APIRouter(prefix="/user", tags=["User"])
logger = logging.getLogger(__name__)

# --- Get User Profile ---
@router.get("/profile", response_model=UserResponse)
def get_user_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        if not current_user:
            raise HTTPException(status_code=404, detail="User not found")

        return UserResponse(
            id=current_user.id,
            hospital_name=current_user.hospital_name,
            email=current_user.email,
            location=current_user.location
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error retrieving user profile: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error while retrieving profile")

# --- Update User Profile ---
@router.put("/profile", response_model=UserResponse)
def update_user_profile(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        if not current_user:
            raise HTTPException(status_code=404, detail="User not found")

        current_user.hospital_name = user_data.hospital_name
        current_user.location = user_data.location.dict()

        if user_data.password:
            current_user.password = get_password_hash(user_data.password)

        db.commit()
        db.refresh(current_user)

        return UserResponse(
            id=current_user.id,
            hospital_name=current_user.hospital_name,
            email=current_user.email,
            location=current_user.location
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating user profile: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error while updating profile")
