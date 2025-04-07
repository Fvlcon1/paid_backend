from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional
from datetime import datetime
import logging

from db import PaediatricProcedure
from schemas import PaediatricProcedureResponse
from dependencies import get_db

router = APIRouter(prefix="/paediatrics", tags=["Paediatric Procedures"])
logger = logging.getLogger(__name__)

@router.get("/search", response_model=List[PaediatricProcedureResponse])
def search_paediatric_procedures(
    query: Optional[str] = Query(None, description="Search by paediatric code or description"),
    limit: int = Query(15, gt=0, le=100),
    db: Session = Depends(get_db)
):
    try:
        now = datetime.utcnow()

        if query:
            term = f"{query}%"
            results = db.query(PaediatricProcedure).filter(
                or_(
                    PaediatricProcedure.paed_code.ilike(term),
                    PaediatricProcedure.description.ilike(term)
                )
            ).limit(limit).all()

            if not results:
                raise HTTPException(status_code=404, detail=f"No paediatric procedures found for '{query}'")

            for item in results:
                item.created_at = now
            db.commit()
        else:
            results = db.query(PaediatricProcedure).order_by(PaediatricProcedure.created_at.desc()).limit(limit).all()

            if not results:
                raise HTTPException(status_code=404, detail="No paediatric procedures found.")

        return results

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching paediatric procedures: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error.")
