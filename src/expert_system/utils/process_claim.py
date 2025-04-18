from sqlalchemy.orm import Session
from db import Claim, VerificationToken
from src.expert_system.models import Diagnosis
from .get_age_in_months import get_age_in_months
import json, math, logging

logger = logging.getLogger(__name__)

def process_claim(claim: Claim, db: Session):
    reasons : list[str] = []
    total_payout = 0
    approved_drug_count = 0

    try:
        # Step 1: Fetch the actual claim from DB
        claim = db.query(Claim).filter(Claim.encounter_token == claim.encounter_token).first()
        if not claim:
            logger.warning("Claim not found")
            return None

        # Step 2: Get diagnosis
        diagnosis = db.query(Diagnosis).filter(Diagnosis.diagnosis_icd10 == claim.diagnosis).first()
        if not diagnosis:
            reasons.append("Invalid diagnosis code")
            claim.reason = json.dumps(reasons)
            claim.status = "rejected"
            db.commit()
            print(json.dumps(reasons))
            print("claim:", claim.reason)
            return None

        # Step 3: Get NHIS member via verification token
        member = db.query(VerificationToken).filter(VerificationToken.token == claim.encounter_token).first()
        if not member:
            reasons.append("Verification token not found")
            claim.reason = json.dumps(reasons)
            claim.status = "rejected"
            db.commit()
            return None

        # Step 4: Build treatment lookup for diagnosis
        valid_treatments = {t.drug_icd10: t for t in diagnosis.treatments}

        # Step 5: Check each drug in claim
        for drug in claim.drugs:
            drug_code = drug.get("code")
            if not drug_code or drug_code not in valid_treatments:
                reasons.append(f"Drug '{drug_code}' is not covered")
                continue

            treatment = valid_treatments[drug_code]
            frequency = drug.get("frequency", 0)
            duration = drug.get("duration", 0)
            pricing = treatment.pricing  # from DB

            age_in_months = get_age_in_months(member.date_of_birth)

            # Validate age
            if treatment.max_age_months and age_in_months > treatment.max_age_months:
                reasons.append(f"{drug_code}: Patient is {(math.floor((age_in_months / 12) * 10) / 10):.0f} years, exceeds age limit")
                continue

            # Validate frequency and duration
            if frequency > treatment.frequency:
                reasons.append(f"{drug_code}: Frequency {frequency} exceeds allowed {treatment.frequency}")
                frequency = treatment.frequency
            if treatment.duration and duration > treatment.duration:
                reasons.append(f"{drug_code}: Duration {duration} exceeds allowed {treatment.duration}")
                duration = treatment.duration

            total_payout += (24/frequency) * duration * pricing
            print("pay:", total_payout)
            approved_drug_count += 1

        # Step 6: Final decision
        claim.status = "approved" if approved_drug_count > 0 else "rejected"
        claim.total_payout = f"{total_payout:.2f}"

        claim.reason = json.dumps(reasons)
        db.commit()
        db.refresh(claim)

    except Exception as e:
        logger.error(f"Error processing claim: {e}", exc_info=True)
        claim.reason = ["Internal processing error"]
        claim.status = "rejected"
        db.commit()
        db.refresh(claim)
