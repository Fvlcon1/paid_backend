# routers/claims.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select  # 👈 add this
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional
import uuid
import logging


from db import SessionLocal, Claim, VerificationToken, User
from schemas import ClaimCreate, ClaimResponse
from security import decode_access_token
from dependencies import get_current_user, get_db

router = APIRouter(prefix="/claims", tags=["Claims"])
logger = logging.getLogger(__name__)

# --- Create Claim ---
@router.post("/submit", response_model=ClaimResponse)
def submit_claim(
    claim_data: ClaimCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)  
):
    

    
    verification = db.query(VerificationToken).filter(
        VerificationToken.token == claim_data.encounter_token
    ).first()

    if not verification:
        raise HTTPException(status_code=404, detail="Invalid encounter token")

    # Construct the full name from the verification token
    full_name = f"{verification.first_name} {verification.middle_name or ''} {verification.last_name}".strip()

    # Convert drugs list into a proper JSON object
    drugs_list = [{"code": drug.code, "dosage": drug.dosage, "frequency": drug.frequency, "duration": drug.duration} for drug in claim_data.drugs]

    # Create a new claim
    new_claim = Claim(
        encounter_token=claim_data.encounter_token,
        diagnosis=claim_data.diagnosis,
        service_type=claim_data.service_type,
        drugs=drugs_list,  # Ensure JSON format
        medical_procedures=claim_data.medical_procedures,
        lab_tests=claim_data.lab_tests,
        created_at=datetime.utcnow(),
        user_id=current_user.id,  
        status="pending",
        reason=None,
        adjusted_amount=None,
        total_payout=None,
        patient_name=full_name,  
        hospital_name=current_user.hospital_name,  
        location=current_user.location.get("address", "Unknown")  # Add the location from the current user
    )

    # Add the claim to the database
    db.add(new_claim)
    db.commit()
    db.refresh(new_claim)

    return new_claim

# --- Get Claims ---
@router.get("/", response_model=List[ClaimResponse])
def get_claims(
    user_id: Optional[int] = Query(None),
    encounter_token: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        query = db.query(Claim)

        if user_id:
            query = query.filter(Claim.user_id == user_id)
        if encounter_token:
            query = query.filter(Claim.encounter_token == encounter_token)
        if start_date:
            query = query.filter(Claim.created_at >= start_date)
        if end_date:
            query = query.filter(Claim.created_at <= end_date)

        claims = query.order_by(Claim.created_at.desc()).offset(offset).limit(limit).all()
        return claims
    except Exception as e:
        logger.error(f"Error retrieving claims: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error during claim retrieval")


@router.get("/approved", response_model=List[ClaimResponse])
def get_approved_claims(db: Session = Depends(get_db)):
    """Get all approved claims"""
    return get_claims_by_status(db, "approved")

@router.get("/rejected", response_model=List[ClaimResponse])
def get_rejected_claims(db: Session = Depends(get_db)):
    """Get all rejected claims"""
    return get_claims_by_status(db, "rejected")

@router.get("/flagged", response_model=List[ClaimResponse])
def get_flagged_claims(db: Session = Depends(get_db)):
    """Get all flagged claims"""
    return get_claims_by_status(db, "flagged")

@router.get("/pending", response_model=List[ClaimResponse])
def get_pending_claims(db: Session = Depends(get_db)):
    """Get all pending claims"""
    return get_claims_by_status(db, "pending")





def get_claims_by_status(db: Session, status: str):
    """Generic function to get claims by status with all required details"""
    stmt = (
        select(Claim, VerificationToken, User)
        .join(VerificationToken, Claim.encounter_token == VerificationToken.token, isouter=True)
        .join(User, VerificationToken.user_id == User.id, isouter=True)
        .filter(Claim.status == status)
    )
    claims_with_details = db.execute(stmt).all()  

    results = []
    for claim, verification, user in claims_with_details:
        
        first_name = getattr(verification, 'first_name', '') if verification else ''
        middle_name = getattr(verification, 'middle_name', '') if verification else ''
        last_name = getattr(verification, 'last_name', '') if verification else ''
        patient_name = f"{first_name} {last_name}".strip() if verification else None

        
        
        
        result = {
            # Claim fields
            "encounter_token": claim.encounter_token,
            "diagnosis": claim.diagnosis,
            "service_type": claim.service_type,
            "drugs": claim.drugs,
            "medical_procedures": claim.medical_procedures,
            "lab_tests": claim.lab_tests,
            "created_at": claim.created_at,
            "status": claim.status,
            "reason": claim.reason,
            "adjusted_amount": claim.adjusted_amount,
            "total_payout": claim.total_payout,
            
            # Patient info from verification
            "patient_name": patient_name,
            "location": claim.location,            
            # Hospital info from user
            "hospital_name": user.hospital_name if user else None,
        }
        results.append(result)
    
    return results

