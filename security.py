from passlib.context import CryptContext
from datetime import datetime, timedelta
from typing import Optional, Union, Any
import jwt
from fastapi import HTTPException, status
from pydantic import ValidationError

# Configuration
SECRET_KEY = "48ba9a7adf6f501264981c22897d74b375c4d1b97bd59776bc755e7dc640c6aa62529ef470e2360fc9c124bc31365a58136cb3c73e7b9c55c2400d9d520f62ea10fc264e508aedd379a850b384f2a475485fcb154189ccc9be2f6ccf0ff241f9dc99cd22be77e05fa000b569e59c8a381697d645a397753719e4acc840afaa5a"  # Replace with a secure key in production
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60  # 1 hour

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    """
    Hash a password using bcrypt
    """
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against a hash
    """
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token
    
    Args:
        data: The data to encode in the token
        expires_delta: Optional custom expiration time
        
    Returns:
        Encoded JWT token as string
    """
    to_encode = data.copy()
    
    # Set expiration time
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
    to_encode.update({"exp": expire})
    
    # Encode the JWT
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Union[dict, None]:
    """
    Decode and validate a JWT token
    
    Args:
        token: The JWT token to decode
        
    Returns:
        The full payload if valid, None otherwise
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload  # Return the full payload instead of just payload.get("sub")
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def create_short_lived_access_token(data: dict) -> str:
    """
    Create a JWT access token that expires in 2 minutes
    
    Args:
        data: The data to encode in the token
        
    Returns:
        Encoded JWT token as a string
    """
    expire = datetime.utcnow() + timedelta(minutes=2)
    to_encode = data.copy()
    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt



def verify_token(token: str) -> dict:
    """
    Verify token and return payload if valid, raise exception if invalid
    
    Args:
        token: The JWT token to verify
        
    Returns:
        The decoded token payload
        
    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except (jwt.JWTError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

def get_token_data(token: str) -> dict:
    """
    Get token data without validation
    Used for debugging or when validation is handled elsewhere
    
    Args:
        token: The JWT token
        
    Returns:
        The decoded token payload or empty dict if invalid
    """
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], options={"verify_signature": False})
    except:
        return {}