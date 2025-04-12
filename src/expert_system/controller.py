from fastapi import APIRouter, Depends, HTTPException, Query
import logging
from .types import IDiagnosis, IPagination
from sqlalchemy.orm import Session
from dependencies import get_db, get_current_user
from .models import Diagnosis, DiagnosisTreatment
from typing import Optional
from sqlalchemy import or_
from db import Claim
from .utils.process_claim import process_claim

router = APIRouter(prefix="/expert-system", tags=["Expert System"])
logger = logging.getLogger(__name__)

@router.post("/diagnoses/create")
def add_diagnosis(
    params: IDiagnosis, 
    db: Session = Depends(get_db),
):
    try:
        # Create the Diagnosis
        new_diagnosis = Diagnosis(
            diagnosis_icd10=params.diagnosis_icd10,
            description=params.description
        )

        # Add treatments
        for treatment_data in params.treatments:
            treatment = DiagnosisTreatment(
                drug_icd10=treatment_data.drug_icd10,
                frequency=treatment_data.frequency,
                duration=treatment_data.duration,
                pricing=treatment_data.pricing,
                prescribing_level=treatment_data.prescribing_level,
                min_age_months=treatment_data.min_age_months,
                max_age_months=treatment_data.max_age_months
            )
            new_diagnosis.treatments.append(treatment)

        db.add(new_diagnosis)
        db.commit()
        db.refresh(new_diagnosis)

        return {
            "message": "Diagnosis and treatments added successfully",
            "data": {
                "diagnosis_id": new_diagnosis.id,
                "diagnosis_icd10": new_diagnosis.diagnosis_icd10,
                "description": new_diagnosis.description,
                "treatments": [t.__dict__ for t in new_diagnosis.treatments]
            }
        }

    except Exception as e:
        logger.error(f"Error adding diagnosis: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error adding diagnosis and treatments")


@router.get("/diagnoses/fetch")
def get_diagnosis(
    pagination: IPagination = Depends(),
    diagnosis_icd10: Optional[str] = Query(None),
    description: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    try:
        query = db.query(Diagnosis)

        # Apply filters
        if diagnosis_icd10:
            query = query.filter(Diagnosis.diagnosis_icd10.ilike(f"%{diagnosis_icd10}%"))
        if description:
            query = query.filter(Diagnosis.description.ilike(f"%{description}%"))

        # Apply pagination
        diagnoses = query.offset(pagination.skip).limit(pagination.limit).all()

        return diagnoses

    except Exception as e:
        logger.error(f"Error retrieving diagnosis: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error retrieving diagnosis")
    

@router.get("/diagnoses/fetch/{diagnosis_id}")
def get_single_diagnosis(
    diagnosis_id: int,
    db: Session = Depends(get_db),
):
    try:
        diagnosis = db.query(Diagnosis).filter(Diagnosis.id == diagnosis_id).first()
        if not diagnosis:
            raise HTTPException(status_code=404, detail="Diagnosis not found")
        return diagnosis
    except Exception as e:
        logger.error(f"Error retrieving diagnosis: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error retrieving diagnosis")

    

@router.put("/diagnoses/update/{diagnosis_id}")
def update_diagnosis(
    diagnosis_id: int,
    params: IDiagnosis,
    db: Session = Depends(get_db)
):
    try:
        diagnosis = db.query(Diagnosis).filter(Diagnosis.id == diagnosis_id).first()

        if not diagnosis:
            raise HTTPException(status_code=404, detail="Diagnosis not found")

        diagnosis.diagnosis_icd10 = params.diagnosis_icd10
        diagnosis.description = params.description

        diagnosis.treatments.clear()

        # Add new treatments
        for treatment_data in params.treatments:
            treatment = DiagnosisTreatment(
                drug_icd10=treatment_data.drug_icd10,
                frequency=treatment_data.frequency,
                duration=treatment_data.duration,
                pricing=treatment_data.pricing,
                prescribing_level=treatment_data.prescribing_level,
                min_age_months=treatment_data.min_age_months,
                max_age_months=treatment_data.max_age_months
            )
            diagnosis.treatments.append(treatment)

        db.commit()
        db.refresh(diagnosis)

        return {
            "message": "Diagnosis updated successfully",
            "data": {
                "id": diagnosis.id,
                "diagnosis_icd10": diagnosis.diagnosis_icd10,
                "description": diagnosis.description
            }
        }

    except Exception as e:
        logger.error(f"Error updating diagnosis: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error updating diagnosis")


@router.delete("/diagnoses/delete/{diagnosis_id}")
def delete_diagnosis(
    diagnosis_id: int,
    db: Session = Depends(get_db)
):
    try:
        diagnosis = db.query(Diagnosis).filter(Diagnosis.id == diagnosis_id).first()

        if not diagnosis:
            raise HTTPException(status_code=404, detail="Diagnosis not found")

        db.delete(diagnosis)
        db.commit()

        return {"message": "Diagnosis deleted successfully"}

    except Exception as e:
        logger.error(f"Error deleting diagnosis: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error deleting diagnosis")

@router.get("/process_claim")
def process_nhia_claim(
    db: Session = Depends(get_db)
):
    try:
        claim = db.query(Claim).filter(Claim.status == "pending").first()
        process_claim(claim, db)
    except Exception as e:
        logger.error(f"Error processing claim: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error processing claim")