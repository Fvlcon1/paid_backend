from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional, Dict, List, Union
from uuid import UUID
from fastapi import Form


from pydantic import BaseModel

class OTPVerification(BaseModel):
    otp: str

class MemberResponse(BaseModel):
    id: UUID
    membership_id: str
    first_name: str
    middle_name: Optional[str] = None
    last_name: str
    date_of_birth: datetime
    gender: str
    marital_status: Optional[str] = None
    nhis_number: str
    insurance_type: Optional[str] = None
    issue_date: datetime
    enrolment_status: str
    current_expiry_date: datetime
    mobile_phone_number: Optional[str] = None
    residential_address: Optional[str] = None
    ghana_card_number: Optional[str] = None
    profile_image_url: Optional[str] = None

    class Config:
        from_attributes = True  # or orm_mode = True if you're using Pydantic v1


class EmailTwoFactorSetup(BaseModel):
    email: EmailStr  # The email address to which the OTP will be sent
    email_otp_backup_codes: Optional[List[str]] = Field(default=None)  # Backup codes for 2FA

class EmailTwoFactorVerification(BaseModel):
    email: EmailStr  # The email address to verify
    otp: str  # The OTP sent to the email

class SendOTPRequest(BaseModel):
    email: str

class VerifyOTPRequest(BaseModel):
    email: str
    otp: str

class OAuth2PasswordRequestFormWithCoordinates(BaseModel):
    email: str = Field(..., alias="username")  # Maps "username" to "email"
    password: str
    coordinates: Dict[str, float] = Field(..., example={"lat": 0.0, "lng": 0.0})

class TwoFactorSetup(BaseModel):
    secret: str
    totp_uri: str
    backup_codes: List[str]
    qr_code: str

class TwoFactorVerification(BaseModel):
    user_id: int
    totp_code: str


class VerificationTokenSchema(BaseModel):
    id: str
    token: str
    membership_id: str
    nhis_number: str
    first_name: str
    middle_name: Optional[str] = None
    last_name: str
    date_of_birth: datetime  # Added
    profile_image_url: str  # Added
    gender: str  # Added
    enrolment_status: str  # Added
    current_expiry_date: datetime
    verification_date: datetime
    created_at: datetime
    verification_status: bool
    user_id: int  # Added
    final_time: datetime

    class Config:
        from_attributes = True  # Pydantic v2 update


class InitializeVerificationRequest(BaseModel):
    membership_id: str


class VerificationTokenResponse(BaseModel):
    id: str
    token: str
    membership_id: str
    nhis_number: str
    full_name: str
    date_of_birth: datetime  # Added
    profile_image_url: str  # Added
    gender: str  # Added
    enrolment_status: str  # Added
    current_expiry_date: datetime
    verification_date: datetime
    verification_status: bool
    user_email: Optional[str] = None
    user_full_name: Optional[str] = None
    

class VerificationRequest(BaseModel):
    membership_id: str


class Location(BaseModel):
    place_name: Optional[str] = None
    address: Optional[str] = None
    coordinates: Dict[str, float] = Field(..., example={"lat": 0.0, "lng": 0.0})


class UserCreate(BaseModel):
    hospital_name: str
    email: EmailStr
    password: str
    location: Location


class UserLogin(BaseModel):
    hospital_id: str
    email: EmailStr
    password: str
    coordinates: Dict[str, float] = Field(..., example={"lat": 0.0, "lng": 0.0})
    totp_code: Optional[str] = None 


class UserResponse(BaseModel):
    id: int
    hospital_name: str
    email: EmailStr

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str
    require_2fa: bool = False
    user_id: Optional[int] = None 

class RecentVisitBase(BaseModel):
    membership_id: str
    nhis_number: str
    first_name: str
    middle_name: Optional[str] = None
    last_name: str
    date_of_birth: datetime
    profile_image_url: str
    visit_date: datetime
    gender: str
    enrolment_status: str
    user_id: Optional[int] = None  # Added user_id


class RecentVisitCreate(RecentVisitBase):
    pass


class RecentVisit(RecentVisitBase):
    id: UUID

    class Config:
        from_attributes = True  # Pydantic v2 update

    @classmethod
    def from_orm(cls, db_visit):
        """
        Convert SQLAlchemy object to Pydantic schema.
        """
        db_dict = {
            "id": db_visit.id,
            "membership_id": db_visit.membership_id,
            "nhis_number": db_visit.nhis_number,
            "first_name": db_visit.first_name,
            "middle_name": db_visit.middle_name,
            "last_name": db_visit.last_name,
            "date_of_birth": db_visit.date_of_birth,
            "profile_image_url": db_visit.profile_image_url,
            "visit_date": db_visit.visit_date,
            "gender": db_visit.gender,
            "enrolment_status": db_visit.enrolment_status,
            "user_id": db_visit.user_id,
        }
        return cls(**db_dict)



class MedicineResponse(BaseModel):
    code: str
    generic_name: str
    unit_of_pricing: str
    price: Optional[float] = None
    level_of_prescribing: Optional[str] = None
    created_at: datetime

    class Config:
        orm_mode = True


class OPDProcedureResponse(BaseModel):
    id: int
    opd_code: str
    description: str
    level_of_care: Optional[List[str]] = None
    tariff: Optional[float] = None
    created_at: datetime

    class Config:
        orm_mode = True


class DentProcedureResponse(BaseModel):
    id: int
    dent_code: str
    description: str
    level_of_care: Optional[List[str]]
    tariff: Optional[float]
    created_at: datetime

    class Config:
        orm_mode = True


class ENTProcedureResponse(BaseModel):
    id: int
    opd_code: str
    description: str
    level_of_care: Optional[List[str]] = None
    tariff: Optional[float] = None
    created_at: datetime

    class Config:
        orm_mode = True


class MedicineProcedureResponse(BaseModel):
    id: int
    opd_code: str
    description: str
    level_of_care: Optional[List[str]] = None
    tariff: Optional[float] = None
    created_at: datetime

    class Config:
        orm_mode = True



class PaediatricProcedureResponse(BaseModel):
    id: int
    opd_code: str
    description: str
    level_of_care: Optional[List[str]] = None
    tariff: Optional[float] = None
    created_at: datetime

    class Config:
        orm_mode = True





class ServiceResponse(BaseModel):
    code: str
    service: str
    tariff: float
    created_at: datetime

    class Config:
        orm_mode = True

class ICD10Response(BaseModel):
    id: int
    icd_code: str
    diagnosis_description: str
    gdrg_code: str | None
    gdrg_name: str | None
    level_of_care: List[str] | None
    created_at: datetime


    class Config:
        orm_mode = True


class ZoomCodeResponse(BaseModel):
    id: int
    zoom_code: str
    description: str
    level_of_care: Optional[List[str]] = None
    tariff: Optional[float]
    created_at: datetime

    class Config:
        orm_mode = True

class InvestigationResponse(BaseModel):
    id: int
    inv_code: str
    name: str
    tariff: Optional[float] = None
    created_at: datetime

    class Config:
        orm_mode = True






class DiagnosisItem(BaseModel):
    GRDG: str
    description: str
    ICD10: str
    primary: Optional[bool] = False


class Drug(BaseModel):
    code: str
    generic_name: str
    dosage: str
    date: datetime
    frequency: int 
    duration: str 
    tariff: float
    unitOfPricing: str
    levelOfPriscription: str
    quantity: int
    total: float


class MedicalProcedure(BaseModel):
    code: str
    service: str
    tariff: float


class LabTest(BaseModel):
    code: str
    service: str
    tariff: float


class ClaimCreate(BaseModel):
    encounter_token: str
    diagnosis: Optional[List[DiagnosisItem]] = None
    service_type: List[str]
    drugs: List[Drug]
    medical_procedures: List[MedicalProcedure]
    lab_tests: Optional[List[LabTest]] = None

    service_outcome: Optional[str] = None
    service_type_1: Optional[str] = None
    service_type_2: Optional[str] = None
    specialties: Optional[List[str]] = None
    type_of_attendance: Optional[str] = None
    pharmacy: bool = False  
    expectedPayout: float = Field(..., alias="expected_payout")
    medical_procedures_total: Optional[float] = None
    lab_tests_total: Optional[float] = None
    drugs_total: Optional[float] = None




class ClaimResponse(BaseModel):
    encounter_token: str
    diagnosis: Optional[List[DiagnosisItem]] = None
    service_type: List[str]
    drugs: List[Drug]
    medical_procedures: List[MedicalProcedure]
    lab_tests: Optional[List[LabTest]] = None

    created_at: datetime
    status: str  
    reason: Optional[str] = None  
    adjusted_amount: Optional[float] = None  
    total_payout: Optional[float] = None  
       
    patient_name: str  
    hospital_name: str  
    location: str
    age: int

    service_outcome: Optional[str] = None
    service_type_1: Optional[str] = None
    service_type_2: Optional[str] = None
    specialties: Optional[List[str]] = None
    type_of_attendance: Optional[str] = None
    pharmacy: bool = False  
    medical_procedures_total: Optional[float] = None
    lab_tests_total: Optional[float] = None
    drugs_total: Optional[float] = None
    expectedPayout: float = Field(..., alias="expected_payout")
    





class ClaimDraftBase(BaseModel):
    encounter_token: str  # Required

    diagnosis: Optional[List[DiagnosisItem]] = None
    service_type: Optional[List[str]] = None
    drugs: Optional[List[Drug]] = None
    medical_procedures: Optional[List[MedicalProcedure]] = None
    lab_tests: Optional[List[LabTest]] = None

    service_outcome: Optional[str] = None
    service_type_1: Optional[str] = None
    service_type_2: Optional[str] = None
    specialties: Optional[List[str]] = None
    type_of_attendance: Optional[str] = None
    pharmacy: Optional[bool] = False
    expectedPayout: Optional[float] = None
    medical_procedures_total: Optional[float] = None
    lab_tests_total: Optional[float] = None
    drugs_total: Optional[float] = None

   
    patient_name: Optional[str] = None
    hospital_name: Optional[str] = None
    location: Optional[str] = None

    status: Optional[str] = "draft"
    reason: Optional[str] = None
    adjusted_amount: Optional[float] = None
    total_payout: Optional[float] = None

    class Config:
        orm_mode = True
        allow_population_by_field_name = True  


class ClaimDraftCreate(ClaimDraftBase):
    pass

class ClaimDraftUpdate(ClaimDraftBase):
    encounter_token: Optional[str] = None  

class ClaimDraftResponse(ClaimDraftBase):
    created_at: datetime


# Schema for status updates
class ClaimStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(approved|rejected|flagged)$")
    reason: Optional[str] = None
 