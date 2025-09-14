import gspread
from oauth2client.service_account import ServiceAccountCredentials
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from ipaddress import ip_address, ip_network
from cryptography.fernet import Fernet
import os
import pytz
import uvicorn

# --- Config ---
SERVICE_ACCOUNT_FILE = "service_account.json"
SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME", "AttendanceSystem")
MASTER_SHEET_NAME = os.getenv("MASTER_SHEET_NAME", "attendance_master")
EMPLOYEE_SHEET_NAME = os.getenv("EMPLOYEE_SHEET_NAME", "config_employees")
COMPANY_SHEET_NAME = os.getenv("COMPANY_SHEET_NAME", "config_companies")
ALLOWED_IPS = None  # allow all IPs
ENCRYPTED_CLIENT_ID_FILE = "client_id.enc"
FERNET_KEY = os.getenv("FERNET_KEY", "PeKU3K-rDOo8EeLrMxR3GjCDQgQCLiFP9fbktkHITgE=")
TIMEZONE = "Asia/Dhaka"  # Bangladesh timezone
# ----------------

# Decrypt Google Client ID
fernet = Fernet(FERNET_KEY.encode())
with open(ENCRYPTED_CLIENT_ID_FILE, "rb") as f:
    encrypted_client_id = f.read()
CLIENT_ID = fernet.decrypt(encrypted_client_id).decode()

# Initialize FastAPI
app = FastAPI(title="Attendance Hybrid API")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Google Sheets Auth
SCOPE = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(SERVICE_ACCOUNT_FILE, SCOPE)
gc = gspread.authorize(creds)

# Open sheets
try:
    sh = gc.open(SPREADSHEET_NAME)
    master_sheet = sh.worksheet(MASTER_SHEET_NAME)
    employee_sheet = sh.worksheet(EMPLOYEE_SHEET_NAME)
    company_sheet = sh.worksheet(COMPANY_SHEET_NAME)
except Exception as e:
    raise RuntimeError(f"Error opening spreadsheet/workbook: {e}")

# Utility functions
def get_employees():
    rows = employee_sheet.get_all_records()
    return {
        r['E-mail'].strip().lower(): {
            'id': r['ID'],
            'full_name': r['Full Name'],
            'nickname': r['Nickname'],
            'office_email': r.get('Office mail', "").strip()
        }
        for r in rows
    }

def get_companies():
    rows = company_sheet.get_all_records()
    return [r['Company Name'] for r in rows]

def add_company(new_company: str):
    existing = [c.lower() for c in get_companies()]
    if new_company.lower() not in existing:
        company_sheet.append_row([new_company])

def get_all_records():
    return master_sheet.get_all_records()

def find_record_for_today(email: str, today: str, records: List[dict]):
    """Returns check-in/out record for today if exists"""
    for idx, r in enumerate(records):
        if r.get("E-mail", "").strip().lower() == email.strip().lower() and r.get("Date", "") == today:
            return r, idx + 2  # gspread is 1-indexed including header row
    return None, None

def is_ip_allowed(ip: str):
    if ALLOWED_IPS is None:
        return True  # allow any IP
    try:
        ip_obj = ip_address(ip)
        for allowed in ALLOWED_IPS:
            if ip_obj in ip_network(allowed, strict=False):
                return True
        return False
    except ValueError:
        return False


class AttendanceIn(BaseModel):
    email: str
    action: str
    companies: Optional[List[str]] = None
    details: Optional[str] = None


# API endpoints
@app.get("/config/companies")
def api_get_companies():
    return {"companies": get_companies()}

@app.get("/config/employees")
def api_get_employees():
    rows = employee_sheet.get_all_records()
    return [
        {
            "id": r['ID'],
            "full_name": r['Full Name'],
            "nickname": r['Nickname'],
            "email": r['E-mail'],
            "office_email": r.get('Office mail', "")
        }
        for r in rows
    ]


@app.post("/attendance")
def handle_attendance(payload: AttendanceIn, request: Request):
    ip = request.client.host
    if not is_ip_allowed(ip):
        raise HTTPException(status_code=403, detail=f"Access Denied: not connected to allowed Wi-Fi. Your IP: {ip}")

    email = payload.email.strip().lower()
    action = payload.action.strip().lower()
    employees = get_employees()

    if email not in employees:
        raise HTTPException(status_code=403, detail="Email not registered")

    # Get Bangladesh time
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    today = now.strftime("%Y-%m-%d")
    time_now = now.strftime("%I:%M:%S %p")  # 12-hour format AM/PM

    emp = employees[email]
    emp_id = emp['id']
    full_name = emp['full_name']
    nickname = emp['nickname']
    office_email = emp['office_email']

    records = get_all_records()
    existing_record, row_index = find_record_for_today(email, today, records)

    if action == "checkin":
        if existing_record and existing_record.get("Check In") == "Checked In":
            raise HTTPException(status_code=400, detail="Already checked in today")

        row = [
            emp_id,           # ID
            nickname,         # Nickname
            full_name,        # Full Name
            email,            # E-mail
            office_email,     # Office mail
            today,            # Date
            time_now,         # Check In Time
            "Checked In",     # Check In
            "",               # Check Out Time
            "",               # Check Out
            "",               # Company
            "",               # Details
            ip,               # Check in IP
            ""                # Check Out IP
        ]
        master_sheet.append_row(row)
        return {
            "status": "checked_in",
            "time": time_now,
            "ip": ip,
            "office_email": office_email
        }

    elif action == "checkout":
        if not existing_record or existing_record.get("Check In") != "Checked In":
            raise HTTPException(status_code=400, detail="Check-in required before checkout")
        if existing_record.get("Check Out") == "Checked Out":
            raise HTTPException(status_code=400, detail="Already checked out today")
        if not payload.companies or not payload.details:
            raise HTTPException(status_code=400, detail="Companies and Details required for checkout")

        for c in payload.companies:
            if c.strip().lower() != "other":
                add_company(c.strip())

        companies_str = ",".join(payload.companies)

        # Correct column mapping
        master_sheet.update_cell(row_index, 9, time_now)           # Check Out Time
        master_sheet.update_cell(row_index, 10, "Checked Out")     # Check Out
        master_sheet.update_cell(row_index, 11, companies_str)     # Company
        master_sheet.update_cell(row_index, 12, payload.details)   # Details
        master_sheet.update_cell(row_index, 14, ip)                # Check Out IP

        return {
            "status": "checked_out",
            "time": time_now,
            "ip": ip,
            "office_email": office_email
        }


    else:
        raise HTTPException(status_code=400, detail="Invalid action")


# Serve HTML dynamically with decrypted CLIENT_ID
@app.get("/")
def read_index():
    html_file_path = "static/index.html"
    with open(html_file_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    html_content = html_content.replace("YOUR_CLIENT_ID_HERE", CLIENT_ID)
    return HTMLResponse(html_content)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8080)
