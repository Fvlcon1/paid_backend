from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional
from datetime import datetime
import logging

from db import OPDProcedure
from schemas import OPDProcedureResponse
from dependencies import get_db

router = APIRouter(prefix="/opd", tags=["OPD Procedures"])
logger = logging.getLogger(__name__)

@router.get("/search", response_model=List[OPDProcedureResponse])
def search_opd_procedures(
    query: Optional[str] = Query(None, description="Search by OPD code or name"),
    limit: int = Query(15, gt=0, le=100, description="Limit the number of results (max 100)"),
    db: Session = Depends(get_db)
):
    try:
        now = datetime.utcnow()

        if query:
            term = f"{query}%"
            results = db.query(OPDProcedure).filter(
                or_(
                    OPDProcedure.opd_code.ilike(term),
                    OPDProcedure.name.ilike(term)
                )
            ).limit(limit).all()

            if not results:
                raise HTTPException(
                    status_code=404,
                    detail=f"No OPD procedures found matching '{query}'"
                )

            for item in results:
                item.created_at = now
            db.commit()

        else:
            results = db.query(OPDProcedure).order_by(
                OPDProcedure.created_at.desc()
            ).limit(limit).all()

            if not results:
                raise HTTPException(
                    status_code=404,
                    detail="No OPD procedures found in the database."
                )

        return results

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Error searching OPD procedures: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while searching OPD procedures."
        )
