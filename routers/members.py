# routers/members.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from typing import Optional
import logging

from db import Member, RecentVisit, VerificationToken
from schemas import MemberResponse
from dependencies import get_db

router = APIRouter(prefix="/members", tags=["Members"])
logger = logging.getLogger(__name__)

# --- Autocomplete members by search query ---
@router.get("/autocomplete")
def autocomplete_memberships(
    query: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    try:
        subquery = (
            db.query(
                VerificationToken.membership_id,
                VerificationToken.final_verification_status,
                VerificationToken.disposition_name,
                func.max(VerificationToken.verification_date).label("latest_verification_date")
            )
            .group_by(
                VerificationToken.membership_id,
                VerificationToken.final_verification_status,
                VerificationToken.disposition_name
            )
            .subquery()
        )

        results = (
            db.query(
                Member,
                RecentVisit.visit_date,
                subquery.c.final_verification_status,
                subquery.c.disposition_name
            )
            .outerjoin(RecentVisit, RecentVisit.membership_id == Member.membership_id)
            .outerjoin(subquery, subquery.c.membership_id == Member.membership_id)
            .filter(
                or_(
                    Member.membership_id.ilike(f"%{query}%"),
                    Member.first_name.ilike(f"%{query}%"),
                    Member.middle_name.ilike(f"%{query}%"),
                    Member.last_name.ilike(f"%{query}%"),
                    Member.nhis_number.ilike(f"%{query}%")
                )
            )
            .order_by(Member.last_name, RecentVisit.visit_date.desc(), subquery.c.latest_verification_date.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        members = []
        seen_ids = set()

        for member, visit_date, status, disposition in results:
            if str(member.id) in seen_ids:
                continue

            seen_ids.add(str(member.id))
            members.append({
                "membership_id": member.membership_id,
                "first_name": member.first_name,
                "middle_name": member.middle_name,
                "last_name": member.last_name,
                "date_of_birth": member.date_of_birth.isoformat(),
                "gender": member.gender,
                "marital_status": member.marital_status,
                "nhis_number": member.nhis_number,
                "insurance_type": member.insurance_type,
                "issue_date": member.issue_date.isoformat(),
                "enrolment_status": member.enrolment_status,
                "current_expiry_date": member.current_expiry_date.isoformat(),
                "phone_number": member.mobile_phone_number,
                "residential_address": member.residential_address,
                "ghana_card_number": member.ghana_card_number,
                "profile_image_url": member.profile_image_url,
                "last_visit": visit_date.isoformat() if visit_date else None,
                "final_verification_status": status,
                "disposition_name": disposition,
            })

        return {"results": members}
    except Exception as e:
        logger.error(f"Error during member autocomplete: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch members")

# --- Get single member by membership_id ---
@router.get("/{membership_id}", response_model=MemberResponse)
def get_member(
    membership_id: str,
    db: Session = Depends(get_db)
):
    try:
        member = db.query(Member).filter(Member.membership_id == membership_id).first()
        if not member:
            raise HTTPException(status_code=404, detail="Member not found")

        return MemberResponse(
            id=str(member.id),
            membership_id=member.membership_id,
            first_name=member.first_name,
            middle_name=member.middle_name,
            last_name=member.last_name,
            date_of_birth=member.date_of_birth,
            gender=member.gender,
            marital_status=member.marital_status,
            nhis_number=member.nhis_number,
            insurance_type=member.insurance_type,
            issue_date=member.issue_date,
            enrolment_status=member.enrolment_status,
            current_expiry_date=member.current_expiry_date,
            mobile_phone_number=member.mobile_phone_number,
            residential_address=member.residential_address,
            ghana_card_number=member.ghana_card_number,
            profile_image_url=member.profile_image_url
        )
    except Exception as e:
        logger.error(f"Error fetching member by ID: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error retrieving member details")
