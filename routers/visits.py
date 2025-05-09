# routers/visits.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import logging
from fastapi.security import OAuth2PasswordBearer
from uuid import UUID

from db import RecentVisit, User, SessionLocal
from schemas import RecentVisit as RecentVisitSchema
from dependencies import get_db, get_current_user

from security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

router = APIRouter(prefix="/recent-visits", tags=["Recent Visits"])
logger = logging.getLogger(__name__)

@router.get("/my")
def get_my_recent_visits(
    skip: int = 0,
    limit: int = 15,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        query = db.query(RecentVisit).filter(RecentVisit.user_id == current_user.id)

        if from_date:
            query = query.filter(RecentVisit.visit_date >= from_date)
        if to_date:
            query = query.filter(RecentVisit.visit_date <= to_date)

        total_count = query.count()

        visits = (
            query.order_by(RecentVisit.visit_date.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        return {
            "total": total_count,
            "results": [
                {
                    "id": str(v.id),
                    "membership_id": v.membership_id,
                    "visit_date": v.visit_date.isoformat(),
                    "first_name": v.first_name,
                    "middle_name": v.middle_name,
                    "last_name": v.last_name,
                    "gender": v.gender,
                    "date_of_birth": v.date_of_birth.isoformat() if v.date_of_birth else None,
                    "nhis_number": v.nhis_number,
                }
                for v in visits
            ],
        }
    except Exception as e:
        logger.error(f"Error retrieving user visits: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error retrieving user visits")


@router.get("/")
def get_recent_visits(
    skip: int = 0,
    limit: int = 15,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        total_count = db.query(RecentVisit).count()

        visits = (
            db.query(RecentVisit)
            .order_by(RecentVisit.visit_date.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        return {
            "total": total_count,
            "results": [
                {
                    "id": str(v.id),
                    "membership_id": v.membership_id,
                    "visit_date": v.visit_date.isoformat(),
                    "first_name": v.first_name,
                    "middle_name": v.middle_name,
                    "last_name": v.last_name,
                    "gender": v.gender,
                    "date_of_birth": v.date_of_birth.isoformat() if v.date_of_birth else None,
                    "nhis_number": v.nhis_number,
                }
                for v in visits
            ],
        }
    except Exception as e:
        logger.error(f"Error retrieving visits: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error retrieving visits")


@router.get("/{visit_id}")
def get_recent_visit(
    visit_id: str,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    try:
        # Validate token
        user_email = decode_access_token(token)
        if not user_email:
            raise HTTPException(status_code=401, detail="Invalid token")

        try:
            visit_uuid = UUID(visit_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid UUID format")

        visit = db.query(RecentVisit).filter(RecentVisit.id == visit_uuid).first()
        if not visit:
            raise HTTPException(status_code=404, detail="Visit not found")

        return {
            "id": str(visit.id),
            "membership_id": visit.membership_id,
            "visit_date": visit.visit_date.isoformat(),
            "first_name": visit.first_name,
            "middle_name": visit.middle_name,
            "last_name": visit.last_name,
            "gender": visit.gender,
            "date_of_birth": visit.date_of_birth.isoformat() if visit.date_of_birth else None,
            "nhis_number": visit.nhis_number,
            "user_id": str(visit.user_id) if visit.user_id else None
        }
    except Exception as e:
        logger.error(f"Error retrieving visit: {str(e)}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=500,
            detail="Error retrieving visit"
        )

@router.delete("/{visit_id}")
def delete_recent_visit(
    visit_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        try:
            visit_uuid = UUID(visit_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid UUID format")

        visit = db.query(RecentVisit).filter(RecentVisit.id == visit_uuid).first()
        if not visit:
            raise HTTPException(status_code=404, detail="Visit not found")

        if visit.user_id and visit.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="You don't have permission to delete this visit")

        visit_data = {
            "id": str(visit.id),
            "membership_id": visit.membership_id,
            "visit_date": visit.visit_date.isoformat(),
            "first_name": visit.first_name,
            "last_name": visit.last_name,
        }

        db.delete(visit)
        db.commit()
        return visit_data
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting visit: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error deleting visit")
