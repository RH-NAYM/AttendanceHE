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
ALLOWED_IPS = None
ENCRYPTED_CLIENT_ID_FILE = "client_id.enc"
FERNET_KEY = os.getenv("FERNET_KEY", "PeKU3K-rDOo8EeLrMxR3GjCDQgQCLiFP9fbktkHITgE=")
TIMEZONE = "Asia/Dhaka"
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
        str(r.get('E-mail', "")).strip().lower(): {
            'id': r.get('ID', ""),
            'full_name': r.get('Full Name', ""),
            'nickname': r.get('Nickname', ""),
            'office_email': str(r.get('Office mail', "")).strip()
        }
        for r in rows
    }

def get_companies():
    rows = company_sheet.get_all_records()
    return [r['Company Name'] for r in rows]

def add_company(new_company: str):
    new_company = new_company.strip()
    if not new_company:
        return
    existing = [c.lower() for c in get_companies()]
    if new_company.lower() not in existing:
        company_sheet.append_row([new_company])

def get_all_records():
    return master_sheet.get_all_records()

def find_record_for_today(email: str, today: str, records: List[dict]):
    """Returns check-in/out record for today if exists"""
    for idx, r in enumerate(records):
        record_email = str(r.get("E-mail", "")).strip().lower()
        record_date = str(r.get("Date", "")).strip()
        if record_email == email.strip().lower() and record_date == today:
            return r, idx + 2
    return None, None

def is_ip_allowed(ip: str):
    if ALLOWED_IPS is None:
        return True
    try:
        ip_obj = ip_address(ip)
        for allowed in ALLOWED_IPS:
            if ip_obj in ip_network(allowed, strict=False):
                return True
        return False
    except ValueError:
        return False

# Pydantic model
class AttendanceIn(BaseModel):
    email: str
    action: str
    task_for: Optional[str] = None
    task_name: Optional[str] = None
    task_details: Optional[str] = None
    my_role: Optional[str] = None

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
        raise HTTPException(status_code=403, detail=f"Access Denied: Your IP: {ip}")

    email = payload.email.strip().lower()
    action = payload.action.strip().lower()
    employees = get_employees()

    if email not in employees:
        raise HTTPException(status_code=403, detail="Email not registered")

    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    today = now.strftime("%Y-%m-%d")
    time_now = now.strftime("%I:%M:%S %p")

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
            emp_id, nickname, full_name, email, office_email,
            today, time_now, "Checked In", "", "", ip, "", "", "", "", ""
        ]
        master_sheet.append_row(row)
        return {"status": "checked_in", "time": time_now, "ip": ip, "office_email": office_email}

    elif action == "checkout":
        if not existing_record or existing_record.get("Check In") != "Checked In":
            raise HTTPException(status_code=400, detail="Check-in required before checkout")
        if existing_record.get("Check Out") == "Checked Out":
            raise HTTPException(status_code=400, detail="Already checked out today")

        task_for = (payload.task_for or "").strip()
        task_name = (payload.task_name or "").strip()
        task_details = (payload.task_details or "").strip()
        my_role = (payload.my_role or "").strip()

        if not task_for or not task_name or not task_details or not my_role:
            raise HTTPException(status_code=400, detail="Task For, Task Name, Task Details, and My Role are required for checkout")

        add_company(task_for)

        master_sheet.update_cell(row_index, 9, time_now)
        master_sheet.update_cell(row_index, 10, "Checked Out")
        master_sheet.update_cell(row_index, 13, task_for)
        master_sheet.update_cell(row_index, 14, task_name)
        master_sheet.update_cell(row_index, 15, task_details)
        master_sheet.update_cell(row_index, 16, my_role)
        master_sheet.update_cell(row_index, 12, ip)

        return {"status": "checked_out", "time": time_now, "ip": ip, "office_email": office_email}

    else:
        raise HTTPException(status_code=400, detail="Invalid action")

# Serve HTML dynamically
@app.get("/")
def read_index():
    html_file_path = "static/index.html"
    with open(html_file_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    html_content = html_content.replace("YOUR_CLIENT_ID_HERE", CLIENT_ID)
    return HTMLResponse(html_content)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8080)
