from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional
from datetime import datetime
import logging

from db import ENTProcedure
from schemas import ENTProcedureResponse
from dependencies import get_db

router = APIRouter(prefix="/ent", tags=["ENT Procedures"])
logger = logging.getLogger(__name__)

@router.get("/search", response_model=List[ENTProcedureResponse])
def search_ent_procedures(
    query: Optional[str] = Query(None, description="Search by ENT code or description"),
    limit: int = Query(15, gt=0, le=100),
    db: Session = Depends(get_db)
):
    try:
        now = datetime.utcnow()

        if query:
            term = f"{query}%"
            results = db.query(ENTProcedure).filter(
                or_(
                    ENTProcedure.ent_code.ilike(term),
                    ENTProcedure.description.ilike(term)
                )
            ).limit(limit).all()

            if not results:
                raise HTTPException(status_code=404, detail=f"No ENT procedures found for '{query}'")

            for item in results:
                item.created_at = now
            db.commit()
        else:
            results = db.query(ENTProcedure).order_by(ENTProcedure.created_at.desc()).limit(limit).all()

            if not results:
                raise HTTPException(status_code=404, detail="No ENT procedures found.")

        return results

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching ENT procedures: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error.")
