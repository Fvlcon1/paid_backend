from datetime import datetime

def get_age_in_months(dob: datetime) -> int:
    today = datetime.today()
    years = today.year - dob.year
    months = today.month - dob.month
    days = today.day - dob.day

    total_months = years * 12 + months

    # If current day is less than birth day, subtract one month
    if days < 0:
        total_months -= 1

    return total_months
