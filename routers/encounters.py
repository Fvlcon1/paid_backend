# routers/encounters.py
from fastapi import APIRouter, Depends, HTTPException, Form, UploadFile, File, Request, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
import uuid
import logging
import time
from tempfile import SpooledTemporaryFile
from slowapi.middleware import SlowAPIMiddleware
import asyncio
from fastapi.security import OAuth2PasswordBearer
from slowapi import Limiter
from slowapi.util import get_remote_address


limiter = Limiter(key_func=get_remote_address)
from db import User, VerificationToken, RecentVisit, Disposition, Claim, Member
from schemas import InitializeVerificationRequest
from dependencies import get_db, get_current_user
from security import decode_access_token
from utils import FaceComparisonSystem
from storage import upload_to_s3, generate_s3_key

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

router = APIRouter(prefix="/encounter", tags=["Encounters"])
logger = logging.getLogger(__name__)
face_system = FaceComparisonSystem()

# --- Initialize Encounter ---
@router.post("/initiate")
def initialize_verification(
    request_data: InitializeVerificationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        member = db.query(VerificationToken).filter(
            VerificationToken.membership_id == request_data.membership_id
        ).order_by(VerificationToken.created_at.desc()).first()

        if not member:
            raise HTTPException(status_code=404, detail="Member not found")

        token_id = uuid.uuid4()
        token_string = str(uuid.uuid4())

        verification_token = VerificationToken(
            id=token_id,
            token=token_string,
            membership_id=member.membership_id,
            nhis_number=member.nhis_number,
            user_id=current_user.id,
            gender=member.gender,
            date_of_birth=member.date_of_birth,
            profile_image_url=member.profile_image_url,
            first_name=member.first_name,
            middle_name=member.middle_name,
            last_name=member.last_name,
            current_expiry_date=member.current_expiry_date,
            enrolment_status=member.enrolment_status,
            phone_number=member.phone_number,
            ghana_card_number=member.ghana_card_number,
            residential_address=member.residential_address,
            insurance_type=member.insurance_type,
        )

        visit = RecentVisit.create_from_member(member)
        visit.user_id = current_user.id

        db.add(verification_token)
        db.add(visit)
        db.commit()

        return {
            "status": "success",
            "token": token_string,
            "member_info": {
                "membership_id": member.membership_id,
                "name": f"{member.first_name} {member.last_name}",
                "nhis_number": member.nhis_number,
                "expiry_date": member.current_expiry_date
            }
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Error initializing verification: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error initializing encounter")

# --- Upload and Compare ---
@router.post("/compare")
@limiter.limit("10/minute")
async def compare_images(
    request: Request,
    webcam_image: UploadFile = File(...),
    verification_token_str: str = Form(...),
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    try:
        # Decode user token
        decoded_data = decode_access_token(token)
        user_email = decoded_data.get("email")
        if not user_email:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        # Fetch user ID
        user_id = db.query(User.id).filter(User.email == user_email).scalar()
        if not user_id:
            raise HTTPException(status_code=404, detail="User not found")
            
        
        verification_token = db.query(VerificationToken).filter(
            VerificationToken.token == verification_token_str
        ).order_by(VerificationToken.created_at.desc()).first()
        
        if not verification_token:
            raise HTTPException(status_code=404, detail="Invalid verification token.")
            
        # Fetch profile image URL
        profile_image_url = db.query(Member.profile_image_url).join(
            VerificationToken, VerificationToken.membership_id == Member.membership_id
        ).filter(VerificationToken.token == verification_token_str).scalar()
        
        if not profile_image_url:
            raise HTTPException(status_code=404, detail="Profile image not found")
        
        # Read the file content before using it
        file_content = await webcam_image.read()
        
        # Reset the file position for face comparison
        await webcam_image.seek(0)
        
        # Run face comparison
        comparison_result = await face_system.compare_blobs(profile_image_url, webcam_image)
        
        # Extract verification status
        is_verified = comparison_result["match_summary"]["is_match"]
        confidence_score = float(comparison_result["match_summary"]["confidence"])
        
        # Generate S3 key
        s3_key = generate_s3_key(str(user_id))
        
        # Create a new file-like object for S3 upload
        temp_file = SpooledTemporaryFile()
        temp_file.write(file_content)
        temp_file.seek(0)
        
        # Upload the image in the background
        # Pass the temporary file directly to the upload function
        
        compare_image_url = await upload_to_s3(temp_file, s3_key)
        # Update verification record
        verification_token.verification_status = is_verified
        verification_token.final_verification_status = is_verified
        verification_token.compare_image_url = compare_image_url
        db.commit()
        
        return {
            "status": "success",
            "message": "Face comparison completed",
            "data": comparison_result,
            "token": verification_token.token
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error in face comparison: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error in face comparison")

# --- Finalize Encounter ---
@router.post("/finalize")
async def finalize_encounter(
    token_id: str = Form(...),
    webcam_image: UploadFile = File(...),
    disposition_id: int = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        token = db.query(VerificationToken).filter(
            VerificationToken.token == token_id
        ).first()

        if not token:
            raise HTTPException(status_code=404, detail="Verification token not found")
        if token.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Unauthorized user")

        disposition = db.query(Disposition).filter(Disposition.id == disposition_id).first()
        if not disposition:
            raise HTTPException(status_code=400, detail="Invalid disposition ID")

        file_content = await webcam_image.read()
        await webcam_image.seek(0)

        comparison_result = await face_system.compare_blobs(
            token.profile_image_url, webcam_image
        )

        is_verified = comparison_result["match_summary"]["is_match"]
        s3_key = f"encounter/{current_user.id}/{int(time.time())}.jpg"
        temp_file = SpooledTemporaryFile()
        temp_file.write(file_content)
        temp_file.seek(0)

        image_url = await upload_to_s3(temp_file, s3_key)

        token.disposition_name = disposition.name
        token.final_verification_status = is_verified
        token.final_time = datetime.utcnow()
        token.encounter_image_url = image_url

        db.commit()
        db.refresh(token)

        return {
            "status": "success",
            "message": "Encounter finalized",
            "disposition": disposition.name,
            "verified": is_verified,
            "image_url": image_url
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Error finalizing encounter: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to finalize encounter")



@router.get("/my_verifications")
def get_my_verifications(
    skip: int = 0,
    limit: int = 20,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    status: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)  
):
    try:
        
        user = current_user  

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        
        query = db.query(VerificationToken).filter(VerificationToken.user_id == user.id)

        
        if from_date:
            query = query.filter(VerificationToken.verification_date >= from_date)
        if to_date:
            query = query.filter(VerificationToken.verification_date <= to_date)
        if status is not None:
            query = query.filter(VerificationToken.verification_status == status)

        
        total_count = query.count()

        
        tokens = query.order_by(VerificationToken.verification_date.desc()).offset(skip).limit(limit).all()

        
        result = [
            {
                "id": str(token.id),
                "token": token.token,
                "membership_id": token.membership_id,
                "nhis_number": token.nhis_number,
                "verification_date": token.verification_date.isoformat(),
                "verification_status": token.verification_status,
                "gender": token.gender,
                "date_of_birth": token.date_of_birth.isoformat() if token.date_of_birth else None,
                "profile_image_url": token.profile_image_url,
                "first_name": token.first_name,
                "middle_name": token.middle_name,
                "last_name": token.last_name,
                "current_expiry_date": token.current_expiry_date,
                "final_verification_status": token.final_verification_status,
                "disposition_name": token.disposition_name,
                "final_time": token.final_time,
                "residential_address": token.residential_address,  #  
                "phone_number": token.phone_number,  #  
                "ghana_card_number": token.ghana_card_number,  #  
                "insurance_type": token.insurance_type,  # 
                "compare_image_url": token.compare_image_url,
                "encounter_image_url": token.encounter_image_url
            }
            for token in tokens
        ]

        return {
            "total": total_count,
            "results": result
        }
    except Exception as e:
        logger.error(f"Error retrieving verifications: {str(e)}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail="Error retrieving verifications")



@router.get("/members/{token}")
async def get_related_verifications(
    token: str,
    limit: int = Query(10, ge=1),
    db: Session = Depends(get_db),
    auth_token: str = Depends(oauth2_scheme)
):
    try:
        # Authenticate user
        decoded_data = decode_access_token(auth_token)
        user_email = decoded_data.get("email")
        if not user_email:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        user = db.query(User).filter(User.email == user_email).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Fetch current verification record
        current_record = db.query(VerificationToken).filter(
            VerificationToken.token == token
        ).first()
        
        if not current_record:
            raise HTTPException(status_code=404, detail="Verification record not found")
        
        # Fetch related verifications excluding the current token
        related_verifications = db.query(VerificationToken).filter(
            VerificationToken.membership_id == current_record.membership_id,
            VerificationToken.token != token
        ).order_by(VerificationToken.created_at.desc()).limit(limit).all()
        
        return {"status": "success", "related_verifications": related_verifications}
    
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error retrieving related verification data: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error retrieving related verification data")


@router.get("/{token}")
async def get_verification_by_token(
    token: str,
    db: Session = Depends(get_db),
    auth_token: str = Depends(oauth2_scheme)
):
    try:
        # Authenticate user
        decoded_data = decode_access_token(auth_token)
        user_email = decoded_data.get("email")
        if not user_email:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        user = db.query(User).filter(User.email == user_email).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Fetch verification record
        verification_record = db.query(VerificationToken).filter(
            VerificationToken.token == token
        ).first()
        
        if not verification_record:
            raise HTTPException(status_code=404, detail="Verification record not found")
        
        # Fetch claim details
        claim = db.query(Claim).filter(Claim.encounter_token == token).first()
        
        return {
            "status": "success", 
            "verification_record": verification_record,
            "claim_submitted": claim is not None,
            "claim_submission_time": claim.created_at.isoformat() if claim and claim.created_at else None

        }
    
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error retrieving verification data: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error retrieving verification data")

