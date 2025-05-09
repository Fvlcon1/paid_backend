# dependencies.py

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials  # ✅ IMPORT THIS
from sqlalchemy.orm import Session
from starlette import status

from db import SessionLocal, User
from security import decode_access_token

# ✅ Initialize security scheme
security = HTTPBearer()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_temp_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> str:
    token = credentials.credentials
    print("token", token)
    decoded_data = decode_access_token(token)

    if not decoded_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token. Please log in again.",
        )

    user_email = decoded_data.get("email")

    user = db.query(User).filter(User.email == user_email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return user_email


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    token = credentials.credentials
    decoded_data = decode_access_token(token)

    if not decoded_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token. Please log in again.",
        )

    user_email = decoded_data.get("email")
    is_2fa = decoded_data.get("is_2fa", False)

    user = db.query(User).filter(User.email == user_email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if is_2fa:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="2FA verification required. Complete verification first.",
        )

    return user
