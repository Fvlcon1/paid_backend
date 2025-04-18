from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional
import logging

from db import SessionLocal, Claim, VerificationToken, User
from schemas import ClaimCreate, ClaimResponse
from security import decode_access_token
from dependencies import get_current_user, get_db

router = APIRouter(prefix="/claims", tags=["Claims"])
logger = logging.getLogger(__name__)

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

    full_name = f"{verification.first_name} {verification.middle_name or ''} {verification.last_name}".strip()

    drugs_list = [{"code": drug.code, "frequency": drug.frequency, "duration": drug.duration} for drug in claim_data.drugs]

    new_claim = Claim(
        encounter_token=claim_data.encounter_token,
        diagnosis=claim_data.diagnosis,
        service_type=claim_data.service_type,
        drugs=drugs_list,
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
        location=current_user.location.get("address", "Unknown"),
        service_outcome=claim_data.service_outcome,
        service_type_1=claim_data.service_type_1,
        service_type_2=claim_data.service_type_2,
        specialties=claim_data.specialties,
        type_of_attendance=claim_data.type_of_attendance,
        pharmacy=claim_data.pharmacy or False
    )

    db.add(new_claim)
    db.commit()
    db.refresh(new_claim)

    return new_claim

@router.get("/", response_model=List[ClaimResponse])
def get_claims(
    user_id: Optional[int] = Query(None),
    encounter_token: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
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

@router.get("/{token}", response_model=ClaimResponse)
def get_claim_by_token(token: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    claim = db.query(Claim).filter(
        Claim.encounter_token == token,
        Claim.user_id == current_user.id
    ).first()

    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    return claim

@router.get("/approved", response_model=List[ClaimResponse])
def get_approved_claims(db: Session = Depends(get_db)):
    return get_claims_by_status(db, "approved")

@router.get("/rejected", response_model=List[ClaimResponse])
def get_rejected_claims(db: Session = Depends(get_db)):
    return get_claims_by_status(db, "rejected")

@router.get("/flagged", response_model=List[ClaimResponse])
def get_flagged_claims(db: Session = Depends(get_db)):
    return get_claims_by_status(db, "flagged")

@router.get("/pending", response_model=List[ClaimResponse])
def get_pending_claims(db: Session = Depends(get_db)):
    return get_claims_by_status(db, "pending")

def get_claims_by_status(db: Session, status: str):
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
            "patient_name": patient_name,
            "location": claim.location,
            "hospital_name": user.hospital_name if user else None,
            "service_outcome": claim.service_outcome,
            "service_type_1": claim.service_type_1,
            "service_type_2": claim.service_type_2,
            "specialties": claim.specialties,
            "type_of_attendance": claim.type_of_attendance,
            "pharmacy": claim.pharmacy
        }
        results.append(result)

    return results

@router.delete("/delete/{encounter_token}")
def delete_claim(encounter_token: str, db: Session = Depends(get_db)):
    try:
        claim = db.query(Claim).filter(Claim.encounter_token == encounter_token).first()
        if not claim:
            raise HTTPException(status_code=404, detail="Claim not found")

        db.delete(claim)
        db.commit()
        return {"message": "Claim deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting claim: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error deleting claim")
