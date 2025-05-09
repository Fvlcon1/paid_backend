from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from datetime import datetime, date
from typing import List, Optional
import logging
import anyio
from websocket_manager import manager
from db import SessionLocal, Claim, VerificationToken, User
from schemas import ClaimCreate, ClaimResponse
from security import decode_access_token
from dependencies import get_current_user, get_db
import traceback
from decimal import Decimal

router = APIRouter(prefix="/claims", tags=["Claims"])
logger = logging.getLogger(__name__)

def calculate_age(dob):
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

@router.post("/submit", response_model=ClaimResponse)
def submit_claim(
    claim_data: ClaimCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        verification = (
            db.query(VerificationToken)
            .filter(VerificationToken.token == claim_data.encounter_token)
            .first()
        )
        if not verification:
            raise HTTPException(status_code=404, detail="Invalid encounter token")

        full_name = f"{verification.first_name} {verification.middle_name or ''} {verification.last_name}".strip()
        age = calculate_age(verification.date_of_birth)

        def get_tariff(table: str, select_column: str, code_column: str, code_value: str):
            query = text(f"SELECT {select_column} FROM {table} WHERE {code_column} = :code")
            result = db.execute(query, {"code": code_value}).fetchone()
            if result and isinstance(result[0], Decimal):
                return float(result[0])
            return result[0] if result else None

        def get_procedure_tariff(code: str):
            table_map = {
                "medi": ("medicine_procedures", "medi_code"),
                "opd": ("opd_procedures", "opd_code"),
                "dent": ("dent_procedures", "dent_code"),
                "paed": ("paediatric_procedures", "paed_code"),
                "surg": ("surgery_procedures", "surg_code"),
                "ent": ("ent_procedures", "ent_code"),
            }
            prefix = code.lower()[:4]
            table, col = table_map.get(prefix, (None, None))
            return get_tariff(table, "tariff", col, code) if table else None

        primary_grdg = None
        diagnosis_legend = []

        for diag in claim_data.diagnosis:
            gdrg_row = db.execute(
                text("SELECT gdrg_code FROM icd10_codes WHERE icd_code = :code"),
                {"code": diag.ICD10}
            ).fetchone()

            gdrg_code = gdrg_row[0] if gdrg_row else None
            tariff = None

            if gdrg_code:
                if getattr(diag, "primary", False):
                    primary_grdg = gdrg_code
                tariff_row = db.execute(
                    text("SELECT tariff FROM icd10_codes WHERE gdrg_code = :code"),
                    {"code": gdrg_code}
                ).fetchone()
                tariff = float(tariff_row[0]) if tariff_row and tariff_row[0] is not None else None


            diagnosis_legend.append({
                "code": diag.ICD10,
                "tariff": tariff
            })

        drugs_legend = []
        for drug in claim_data.drugs:
            price = get_tariff("medicines", "price", "code", drug.code)
            drugs_legend.append({
                "code": drug.code,
                "dosage": drug.dosage,
                "frequency": drug.frequency,
                "duration": drug.duration,
                "tariff": price if price else drug.tariff,
            })

        procedures_legend = []
        for proc in claim_data.medical_procedures:
            tariff = get_procedure_tariff(proc.code)
            procedures_legend.append({
                "code": proc.code,
                "tariff": tariff if tariff else proc.tariff
            })

        labs_legend = []
        for lab in claim_data.lab_tests or []:
            tariff = get_tariff("investigations", "tariff", "inv_code", lab.code)
            labs_legend.append({
                "code": lab.code,
                "tariff": tariff if tariff else lab.tariff
            })

        legend = {
            "primary_grdg": primary_grdg,
            "diagnosis": diagnosis_legend,
            "drugs": drugs_legend,
            "procedures": procedures_legend,
            "labs": labs_legend,
        }

        drugs_list = [
            {
                "code": drug.code,
                "generic_name": drug.generic_name,
                "dosage": drug.dosage,
                "date": drug.date.isoformat(),
                "frequency": drug.frequency,
                "duration": drug.duration,
                "tariff": drug.tariff,
                "unitOfPricing": drug.unitOfPricing,
                "levelOfPriscription": drug.levelOfPriscription,
                "quantity": drug.quantity,
                "total": drug.total,
            }
            for drug in claim_data.drugs
        ]

        new_claim = Claim(
            encounter_token=claim_data.encounter_token,
            diagnosis=[d.model_dump() for d in claim_data.diagnosis] if claim_data.diagnosis else [],
            service_type=claim_data.service_type,
            drugs=drugs_list,
            medical_procedures=[p.model_dump() for p in claim_data.medical_procedures],
            lab_tests=[l.model_dump() for l in claim_data.lab_tests] if claim_data.lab_tests else [],
            created_at=datetime.utcnow(),
            user_id=current_user.id,
            status="pending",
            age=age,
            reason=None,
            adjusted_amount=None,
            total_payout=None,
            expected_payout=claim_data.expectedPayout,
            medical_procedures_total=claim_data.medical_procedures_total,
            lab_tests_total=claim_data.lab_tests_total,
            drugs_total=claim_data.drugs_total,
            patient_name=full_name,
            hospital_name=current_user.hospital_name,
            location=current_user.location.get("address", "Unknown"),
            service_outcome=claim_data.service_outcome,
            service_type_1=claim_data.service_type_1,
            service_type_2=claim_data.service_type_2,
            specialties=claim_data.specialties,
            type_of_attendance=claim_data.type_of_attendance,
            pharmacy=claim_data.pharmacy or False,
            legend=legend,
        )

        db.add(new_claim)
        db.commit()
        db.refresh(new_claim)

        anyio.from_thread.run(manager.send_notification, "2")
        return new_claim

    except Exception:
        db.rollback()
        logger.error("Error submitting claim:\n" + traceback.format_exc())
        raise HTTPException(status_code=500, detail="Internal Server Error")

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
        claims = (
            query.order_by(Claim.created_at.desc()).offset(offset).limit(limit).all()
        )
        return claims
    except Exception as e:
        logger.error(f"Error retrieving claims: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Internal server error during claim retrieval"
        )

@router.get("/approved", response_model=List[ClaimResponse])
def get_approved_claims(db: Session = Depends(get_db)):
    anyio.from_thread.run(manager.reset_counter, "2", "approved")
    return get_claims_by_status(db, "approved")

@router.get("/rejected", response_model=List[ClaimResponse])
def get_rejected_claims(db: Session = Depends(get_db)):
    anyio.from_thread.run(manager.reset_counter, "2", "rejected")
    return get_claims_by_status(db, "rejected")

@router.get("/flagged", response_model=List[ClaimResponse])
def get_flagged_claims(db: Session = Depends(get_db)):
    anyio.from_thread.run(manager.reset_counter, "2", "flagged")
    return get_claims_by_status(db, "flagged")

@router.get("/pending", response_model=List[ClaimResponse])
def get_pending_claims(db: Session = Depends(get_db)):
    anyio.from_thread.run(manager.reset_counter, "2", "pending")
    return get_claims_by_status(db, "pending")

@router.get("/{token}", response_model=ClaimResponse)
def get_claim_by_token(
    token: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    claim = (
        db.query(Claim)
        .filter(Claim.encounter_token == token, Claim.user_id == current_user.id)
        .first()
    )
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    return claim

def get_claims_by_status(db: Session, status: str):
    stmt = (
        select(Claim, VerificationToken, User)
        .join(
            VerificationToken,
            Claim.encounter_token == VerificationToken.token,
            isouter=True,
        )
        .join(User, VerificationToken.user_id == User.id, isouter=True)
        .filter(Claim.status == status)
    )
    claims_with_details = db.execute(stmt).all()
    results = []
    for claim, verification, user in claims_with_details:
        first_name = getattr(verification, "first_name", "") if verification else ""
        middle_name = getattr(verification, "middle_name", "") if verification else ""
        last_name = getattr(verification, "last_name", "") if verification else ""
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
            "pharmacy": claim.pharmacy,
            "medical_procedures_total": claim.medical_procedures_total,
            "lab_tests_total": claim.lab_tests_total,
            "drugs_total": claim.drugs_total,
            "expected_payout": claim.expected_payout,
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
