# Updated main FastAPI `api.py` file for better structure, security, and modularity

from fastapi import FastAPI, Depends, HTTPException, File, UploadFile, Form, Query, Request, Header, BackgroundTasks
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer, HTTPBearer, HTTPAuthorizationCredentials, OAuth2PasswordRequestForm
from fastapi.routing import APIRouter
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette import status
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_, func, select
from dotenv import load_dotenv
from datetime import datetime, timedelta
from tempfile import SpooledTemporaryFile
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4, UUID
import logging
import asyncio
import string
import jwt
import boto3
import os
from db import Base, engine

from db import SessionLocal, Member, RecentVisit, User, VerificationToken, Disposition, Claim, Medicines, ServiceTariffs, EmailTwoFactor, ClaimDraft,ICD10Code, Investigation, ZoomCode, DentProcedure, OPDProcedure, ENTProcedure, MedicineProcedure, PaediatricProcedure, SurgeryProcedure
from schemas import (RecentVisit as RecentVisitSchema, UserCreate, UserLogin, UserResponse, Token, VerificationTokenSchema, VerificationTokenResponse,
                     TwoFactorSetup, TwoFactorVerification, EmailTwoFactorSetup, EmailTwoFactorVerification, SendOTPRequest, VerifyOTPRequest,
                     OTPVerification, VerificationRequest, InitializeVerificationRequest, Drug, ClaimCreate, ClaimResponse, ClaimStatusUpdate,
                     MedicineResponse, ServiceResponse, ClaimDraftCreate, ClaimDraftResponse, ClaimDraftUpdate, InvestigationResponse, ZoomCodeResponse, OPDProcedureResponse, DentProcedureResponse, ENTProcedureResponse, MedicineProcedureResponse, PaediatricProcedureResponse)
from utils import FaceComparisonSystem
from security import get_password_hash, verify_password, create_access_token, decode_access_token, SECRET_KEY, ALGORITHM
from sendd import generate_otp, send_otp_email
from totp import TwoFactorAuth, setup_2fa, enable_2fa, verify_2fa, disable_2fa, regenerate_backup_codes
from qr import generate_qr_code_base64
from routers import icd
from routers import investigations, dent, med, paediatrics, opd, ent
from routers import zoom


Base.metadata.create_all(bind=engine)


load_dotenv()

AWS_ACCESS_KEY = "AKIAU6GD2ASBDQBT4G6T"
AWS_SECRET_KEY = "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"
REGION_NAME = "us-east-1"
BUCKET_NAME = "national-health"


s3 = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
    region_name=REGION_NAME
)


app = FastAPI()
templates = Jinja2Templates(directory="templates")
security = HTTPBearer()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")
face_system = FaceComparisonSystem()
limiter = Limiter(key_func=get_remote_address)
executor = ThreadPoolExecutor()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


s3 = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
    region_name=REGION_NAME
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.middleware("http")
async def db_session_middleware(request: Request, call_next):
    try:
        response = await call_next(request)
        return response
    except RateLimitExceeded as e:
        return JSONResponse(status_code=429, content={"detail": "Too many requests"})
    except Exception as e:
        logger.error(f"Unhandled exception: {str(e)}")
        return JSONResponse(status_code=500, content={"detail": "Internal server error occurred."})


from routers import (
    auth, users, mfa, encounters, members, claims, drafts, medicines, services, visits, dispositions
)
from routers.ws_router import router as ws_router
from src.expert_system import controller as expert_system_controller

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(mfa.router)
app.include_router(encounters.router)
app.include_router(members.router)
app.include_router(claims.router)
app.include_router(drafts.router)
app.include_router(medicines.router)
app.include_router(services.router)
app.include_router(visits.router)
app.include_router(dispositions.router)
app.include_router(icd.router)
app.include_router(investigations.router)
app.include_router(zoom.router)
app.include_router(dent.router)
app.include_router(med.router)
app.include_router(ent.router)
app.include_router(paediatrics.router)
app.include_router(opd.router)
app.include_router(ws_router)

app.include_router(expert_system_controller.router)


def create_health_check(app: FastAPI):
    @app.get("/health")
    def health():
        return {"status": "ok"}

create_health_check(app)

