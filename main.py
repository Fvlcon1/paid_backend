from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from db import SessionLocal, Member

app = FastAPI()

# Dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Define Pydantic model for request validation
class MemberCreate(BaseModel):
    membership_id: str
    first_name: str
    middle_name: str | None = None
    last_name: str
    date_of_birth: str
    gender: str
    marital_status: str
    nhis_number: str
    insurance_type: str
    issue_date: str
    enrolment_status: str
    current_expiry_date: str
    mobile_phone_number: str
    residential_address: str
    ghana_card_number: str
    profile_image_url: str

# Endpoint to add a new member
@app.post("/members")
def create_member(member: MemberCreate, db: Session = Depends(get_db)):
    # Check if membership_id already exists
    existing_member = db.query(Member).filter(Member.membership_id == member.membership_id).first()
    if existing_member:
        raise HTTPException(status_code=400, detail="Membership ID already exists")

    new_member = Member(
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

    db.add(new_member)
    db.commit()
    db.refresh(new_member)

    return {"message": "Member created successfully", "membership_id": new_member.membership_id}
