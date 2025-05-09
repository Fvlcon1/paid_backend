# routers/services.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional
from datetime import datetime
import logging

from db import SessionLocal, ServiceTariffs
from schemas import ServiceResponse
from dependencies import get_db

router = APIRouter(prefix="/services", tags=["Services"])
logger = logging.getLogger(__name__)

# --- Search services ---
@router.get("/search", response_model=List[ServiceResponse])
def search_services(
    query: Optional[str] = Query(None, description="Search by code or service name"),
    limit: int = Query(15, description="Limit results"),
    db: Session = Depends(get_db)
):
    try:
        if query:
            term = f"{query}%"
            services = db.query(ServiceTariffs).filter(
                or_(
                    ServiceTariffs.code.ilike(term),
                    ServiceTariffs.service.ilike(term)
                )
            ).limit(limit).all()

            for s in services:
                s.created_at = datetime.utcnow()
            db.commit()
        else:
            services = db.query(ServiceTariffs).order_by(ServiceTariffs.created_at.desc()).limit(limit).all()

        return services
    except Exception as e:
        logger.error(f"Error searching services: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error searching services")
