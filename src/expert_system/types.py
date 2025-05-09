from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from fastapi import Query


class ITreatment(BaseModel):
    min_age_months: Optional[int] = None
    max_age_months: Optional[int] = None
    drug_icd10: str
    frequency: int
    duration: Optional[int] = None
    pricing: Optional[float] = None
    prescribing_level: Optional[str] = None


class IDiagnosis(BaseModel):
    diagnosis_icd10: str
    description: str
    # investigations: Optional[List[str]]
    treatments: List[ITreatment]

class IPagination(BaseModel):
    skip: Optional[int] = Query(default=0, ge=0)
    limit: int = Query(default=15, ge=1)
    from_date: Optional[datetime] = Query(default=None)
    to_date: Optional[datetime] = Query(default=None)
