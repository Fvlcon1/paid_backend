from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional
from datetime import datetime
import logging

from db import ZoomCode
from schemas import ZoomCodeResponse
from dependencies import get_db

router = APIRouter(prefix="/zoom", tags=["Zoom Codes"])
logger = logging.getLogger(__name__)

@router.get("/search", response_model=List[ZoomCodeResponse])
def search_zoom_codes(
    query: Optional[str] = Query(None, description="Search by Zoom code or description"),
    limit: int = Query(15, gt=0, le=100, description="Limit the number of results (max 100)"),
    db: Session = Depends(get_db)
):
    try:
        now = datetime.utcnow()

        if query:
            term = f"{query}%"
            results = db.query(ZoomCode).filter(
                or_(
                    ZoomCode.zoom_code.ilike(term),
                    ZoomCode.description.ilike(term)
                )
            ).limit(limit).all()

            if not results:
                raise HTTPException(
                    status_code=404,
                    detail=f"No Zoom codes found matching '{query}'"
                )

            for item in results:
                item.created_at = now
            db.commit()

        else:
            results = db.query(ZoomCode).order_by(
                ZoomCode.created_at.desc()
            ).limit(limit).all()

            if not results:
                raise HTTPException(
                    status_code=404,
                    detail="No Zoom codes found in the database."
                )

        return results

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Error searching Zoom codes: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while searching Zoom codes."
        )
