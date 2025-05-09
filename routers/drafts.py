from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
import logging
import traceback


from db import ClaimDraft, VerificationToken, SessionLocal
from schemas import ClaimDraftCreate, ClaimDraftUpdate, ClaimDraftResponse
from dependencies import get_db, get_current_user
from db import User

router = APIRouter(prefix="/claim-drafts", tags=["Claim Drafts"])
logger = logging.getLogger(__name__)


def safe_model_dump(obj_list):
    def serialize_value(val):
        if isinstance(val, datetime):
            return val.isoformat()
        return val

    if not obj_list:
        return None

    return [
        {
            k: serialize_value(v)
            for k, v in (
                obj.model_dump(mode="json") if hasattr(obj, "model_dump") else obj
            ).items()
        }
        for obj in obj_list
    ]





@router.post("/", response_model=ClaimDraftResponse)
def create_draft(
    draft_data: ClaimDraftCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        verification = db.query(VerificationToken).filter(
            VerificationToken.token == draft_data.encounter_token
        ).first()

        draft = db.query(ClaimDraft).filter(ClaimDraft.encounter_token == draft_data.encounter_token).first()

        if draft:
            # Update existing draft
            draft.diagnosis = safe_model_dump(draft_data.diagnosis)
            draft.drugs = safe_model_dump(draft_data.drugs)
            draft.medical_procedures = safe_model_dump(draft_data.medical_procedures)
            draft.lab_tests = safe_model_dump(draft_data.lab_tests)
            draft.service_type = draft_data.service_type
            draft.status = draft_data.status or "draft"
            draft.reason = draft_data.reason
            draft.adjusted_amount = draft_data.adjusted_amount
            draft.total_payout = draft_data.total_payout
            draft.service_outcome = draft_data.service_outcome
            draft.service_type_1 = draft_data.service_type_1
            draft.service_type_2 = draft_data.service_type_2
            draft.specialties = draft_data.specialties
            draft.type_of_attendance = draft_data.type_of_attendance
            draft.pharmacy = draft_data.pharmacy
            draft.expected_payout = draft_data.expectedPayout
            draft.medical_procedures_total = draft_data.medical_procedures_total
            draft.lab_tests_total = draft_data.lab_tests_total
            draft.drugs_total = draft_data.drugs_total
            draft.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(draft)
            return draft

        if not verification:
            raise HTTPException(status_code=404, detail="Invalid encounter token")

        full_name = f"{verification.first_name} {verification.middle_name or ''} {verification.last_name}".strip()

        new_draft = ClaimDraft(
            encounter_token=draft_data.encounter_token,
            diagnosis=safe_model_dump(draft_data.diagnosis),
            drugs=safe_model_dump(draft_data.drugs),
            medical_procedures=safe_model_dump(draft_data.medical_procedures),
            lab_tests=safe_model_dump(draft_data.lab_tests),
            service_type=draft_data.service_type,
            created_at=datetime.utcnow(),
            user_id=current_user.id,
            status=draft_data.status or "draft",
            reason=draft_data.reason,
            adjusted_amount=draft_data.adjusted_amount,
            total_payout=draft_data.total_payout,
            patient_name=full_name,
            hospital_name=current_user.hospital_name,
            location=current_user.location.get("address", "Unknown"),
            service_outcome=draft_data.service_outcome,
            service_type_1=draft_data.service_type_1,
            service_type_2=draft_data.service_type_2,
            specialties=draft_data.specialties,
            type_of_attendance=draft_data.type_of_attendance,
            pharmacy=draft_data.pharmacy,
            expected_payout=draft_data.expectedPayout,
            medical_procedures_total=draft_data.medical_procedures_total,
            lab_tests_total=draft_data.lab_tests_total,
            drugs_total=draft_data.drugs_total
        )

        db.add(new_draft)
        db.commit()
        db.refresh(new_draft)
        return new_draft

    except Exception as e:
        db.rollback()
        tb = traceback.format_exc()
        logger.error(f"Error creating claim draft:\n{tb}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")




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

    update_data = draft_data.dict(exclude_unset=True, by_alias=True)

   
    if "diagnosis" in update_data:
        update_data["diagnosis"] = safe_model_dump(update_data["diagnosis"])
    if "drugs" in update_data:
        update_data["drugs"] = safe_model_dump(update_data["drugs"])
    if "medical_procedures" in update_data:
        update_data["medical_procedures"] = safe_model_dump(update_data["medical_procedures"])
    if "lab_tests" in update_data:
        update_data["lab_tests"] = safe_model_dump(update_data["lab_tests"])

    for field, value in update_data.items():
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
