from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional
from datetime import datetime
import logging

from db import Investigation
from schemas import InvestigationResponse
from dependencies import get_db

router = APIRouter(prefix="/investigations", tags=["Investigations"])
logger = logging.getLogger(__name__)

@router.get("/search", response_model=List[InvestigationResponse])
def search_investigations(
    query: Optional[str] = Query(None, description="Search by investigation code or name"),
    limit: int = Query(15, gt=0, le=100, description="Limit the number of results (max 100)"),
    db: Session = Depends(get_db)
):
    try:
        now = datetime.utcnow()

        if query:
            term = f"{query}%"
            investigations = db.query(Investigation).filter(
                or_(
                    Investigation.inv_code.ilike(term),
                    Investigation.name.ilike(term)
                )
            ).limit(limit).all()

            if not investigations:
                raise HTTPException(
                    status_code=404,
                    detail=f"No investigations found matching '{query}'"
                )

            # Update created_at to reflect recent search
            for item in investigations:
                item.created_at = now
            db.commit()

        else:
            # No query: return the most recently accessed records
            investigations = db.query(Investigation).order_by(
                Investigation.created_at.desc()
            ).limit(limit).all()

            if not investigations:
                raise HTTPException(
                    status_code=404,
                    detail="No investigations available in the database."
                )

        return investigations

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Error searching investigations: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while processing your request. Please try again later."
        )
