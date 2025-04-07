# routers/drafts.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
import logging

from db import ClaimDraft, SessionLocal
from schemas import ClaimDraftCreate, ClaimDraftUpdate, ClaimDraftResponse
from dependencies import get_db, get_current_user
from db import User

router = APIRouter(prefix="/claim-drafts", tags=["Claim Drafts"])
logger = logging.getLogger(__name__)

# --- Create Draft ---
@router.post("/", response_model=ClaimDraftResponse)
def create_draft(
    draft_data: ClaimDraftCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        new_draft = ClaimDraft(
            encounter_token=draft_data.encounter_token,
            diagnosis=draft_data.diagnosis,
            service_type=draft_data.service_type,
            drugs=draft_data.drugs,
            medical_procedures=draft_data.medical_procedures,
            lab_tests=draft_data.lab_tests,
            created_at=datetime.utcnow(),
            user_id=current_user.id,
            status=draft_data.status,
            reason=draft_data.reason,
            adjusted_amount=draft_data.adjusted_amount,
            total_payout=draft_data.total_payout,
            patient_name=draft_data.patient_name,
            hospital_name=draft_data.hospital_name,
            location=draft_data.location,
        )
        db.add(new_draft)
        db.commit()
        db.refresh(new_draft)
        return new_draft
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating claim draft: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error creating claim draft")

# --- Get All Drafts ---
@router.get("/", response_model=List[ClaimDraftResponse])
def get_drafts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        drafts = db.query(ClaimDraft).filter(ClaimDraft.user_id == current_user.id).all()
        return drafts
    except Exception as e:
        logger.error(f"Error fetching claim drafts: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error retrieving drafts")

# --- Get One Draft by Token ---
@router.get("/{draft_id}", response_model=ClaimDraftResponse)
def get_draft_by_id(
    draft_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    draft = db.query(ClaimDraft).filter(ClaimDraft.encounter_token == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Claim draft not found")
    if draft.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Unauthorized access to draft")
    return draft

# --- Update Draft ---
@router.put("/{draft_id}", response_model=ClaimDraftResponse)
def update_draft(
    draft_id: str,
    draft_data: ClaimDraftUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    draft = db.query(ClaimDraft).filter(ClaimDraft.encounter_token == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Claim draft not found")
    if draft.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Unauthorized access to update this draft")

    for field, value in draft_data.dict(exclude_unset=True).items():
        setattr(draft, field, value)

    db.commit()
    db.refresh(draft)
    return draft

# --- Delete Draft ---
@router.delete("/{draft_id}", response_model=dict)
def delete_draft(
    draft_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    draft = db.query(ClaimDraft).filter(ClaimDraft.encounter_token == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Claim draft not found")
    if draft.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Unauthorized to delete this draft")

    db.delete(draft)
    db.commit()
    return {"message": "Draft deleted successfully"}
