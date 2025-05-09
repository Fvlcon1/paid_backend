# models/treatments.py

from sqlalchemy import Column, Integer, String, Float, ForeignKey, TIMESTAMP
from sqlalchemy.orm import relationship
from db import Base 
import datetime

class DiagnosisTreatment(Base):
    __tablename__ = "diagnosis_treatments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    diagnosis_id = Column(Integer, ForeignKey("diagnoses.id"), nullable=False)

    min_age_months = Column(Integer, nullable=True)
    max_age_months = Column(Integer, nullable=True)

    drug_icd10 = Column(String(20), nullable=False)
    frequency = Column(Integer, nullable=False)
    duration = Column(Integer, nullable=True, default=0)
    pricing = Column(Float, nullable=True)
    prescribing_level = Column(String(10), nullable=True)

    # Relationship back to Diagnosis
    diagnosis = relationship("Diagnosis", back_populates="treatments")


class Diagnosis(Base):
    __tablename__ = "diagnoses"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    diagnosis_icd10 = Column(String(30), unique=True, nullable=False, index=True)
    description = Column(String, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), default=datetime.datetime.utcnow)

    treatments = relationship("DiagnosisTreatment", back_populates="diagnosis", cascade="all, delete-orphan")
    # investigations = relationship("DiagnosisInvestigation", back_populates="diagnosis", cascade="all, delete-orphan")
