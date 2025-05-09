from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional
import logging

from db import ICD10Code
from schemas import ICD10Response
from dependencies import get_db

router = APIRouter(prefix="/icd10", tags=["ICD10 Codes"])
logger = logging.getLogger(__name__)

@router.get("/search", response_model=List[ICD10Response])
def search_icd_codes(
    query: Optional[str] = Query(None, description="Search by ICD code or diagnosis"),
    limit: int = Query(15, ge=1, le=100, description="Limit the number of results"),
    db: Session = Depends(get_db)
) -> List[ICD10Response]:
    try:
        if query:
            term = f"{query}%"
            results = db.query(ICD10Code).filter(
                or_(
                    ICD10Code.icd_code.ilike(term),
                    ICD10Code.diagnosis_description.ilike(term)
                )
            ).limit(limit).all()
        else:
            results = db.query(ICD10Code).order_by(ICD10Code.created_at.desc()).limit(limit).all()

        return results

    except Exception as e:
        logger.error(f"Error searching ICD-10 codes: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error searching ICD-10 codes")
