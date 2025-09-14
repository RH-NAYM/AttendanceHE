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
import uvicorn

# --- Config ---
SERVICE_ACCOUNT_FILE = "service_account.json"
SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME", "AttendanceSystem")
MASTER_SHEET_NAME = os.getenv("MASTER_SHEET_NAME", "attendance_master")
EMPLOYEE_SHEET_NAME = os.getenv("EMPLOYEE_SHEET_NAME", "config_employees")
COMPANY_SHEET_NAME = os.getenv("COMPANY_SHEET_NAME", "config_companies")
ALLOWED_IPS = ["192.168.1.0/24","127.0.0.1"]
ENCRYPTED_CLIENT_ID_FILE = "client_id.enc"  # your encrypted Google OAuth Client ID
FERNET_KEY =  "PeKU3K-rDOo8EeLrMxR3GjCDQgQCLiFP9fbktkHITgE="  # your Fernet key in environment variable
# ----------------

# Decrypt Google Client ID
fernet = Fernet(FERNET_KEY.encode())
with open(ENCRYPTED_CLIENT_ID_FILE, "rb") as f:
    encrypted_client_id = f.read()
CLIENT_ID = fernet.decrypt(encrypted_client_id).decode()

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
    return {r['E-mail'].strip().lower(): {'id': r['ID'], 'full_name': r['Full Name'], 'nickname': r['Nickname']} for r in rows}

def get_companies():
    rows = company_sheet.get_all_records()
    return [r['Company Name'] for r in rows]

def add_company(new_company: str):
    existing = [c.lower() for c in get_companies()]
    if new_company.lower() not in existing:
        company_sheet.append_row([new_company])

def get_all_records():
    return master_sheet.get_all_records()

def find_row_for_today(email: str, today: str, records: List[dict]):
    latest_row = None
    latest_idx = None
    for idx, r in enumerate(records):
        if r.get("E-mail","").strip().lower() == email.strip().lower() and r.get("Date","") == today:
            if r.get("Check In") == "CHECKIN" and r.get("Check Out") != "CHECKOUT":
                latest_row = r
                latest_idx = idx + 2
    return latest_row, latest_idx

def is_ip_allowed(ip: str):
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
    return [{"id": r['ID'], "full_name": r['Full Name'], "nickname": r['Nickname'], "email": r['E-mail']} for r in rows]

@app.post("/attendance")
def handle_attendance(payload: AttendanceIn, request: Request):
    ip = request.client.host
    if not is_ip_allowed(ip):
        raise HTTPException(status_code=403, detail=f"Access denied: not connected to allowed Wi-Fi. Your IP: {ip}")

    email = payload.email.strip().lower()
    action = payload.action.strip().lower()
    employees = get_employees()

    if email not in employees:
        raise HTTPException(status_code=403, detail="Email not registered")

    today = datetime.now().strftime("%Y-%m-%d")
    time_now = datetime.now().strftime("%H:%M:%S")
    emp = employees[email]
    emp_id = emp['id']
    full_name = emp['full_name']
    nickname = emp['nickname']

    records = get_all_records()
    existing_record, row_index = find_row_for_today(email, today, records)

    if action == "checkin":
        if existing_record:
            raise HTTPException(status_code=400, detail="Already checked in and pending checkout")
        row = [emp_id, nickname, full_name, email, today, time_now, "Checked In", "Pending", "Pending", "Pending", "Pending", ip, "Pending"]
        master_sheet.append_row(row)
        return {"status": "checked_in", "time": time_now, "ip": ip}

    elif action == "checkout":
        if not existing_record:
            raise HTTPException(status_code=400, detail="Check-in required before checkout")
        if not payload.companies or not payload.details:
            raise HTTPException(status_code=400, detail="companies and details required for checkout")

        for c in payload.companies:
            if c.strip().lower() != "other":
                add_company(c.strip())

        companies_str = ",".join(payload.companies)
        master_sheet.update_cell(row_index, 8, time_now)
        master_sheet.update_cell(row_index, 9, "Checked Out")
        master_sheet.update_cell(row_index, 10, companies_str)
        master_sheet.update_cell(row_index, 11, payload.details)
        master_sheet.update_cell(row_index, 13, ip)
        return {"status": "checked_out", "time": time_now, "ip": ip}

    else:
        raise HTTPException(status_code=400, detail="Invalid action")

# Serve HTML dynamically with decrypted CLIENT_ID
@app.get("/")
def read_index():
    html_file_path = "static/index.html"
    with open(html_file_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    # Inject CLIENT_ID dynamically
    html_content = html_content.replace("YOUR_CLIENT_ID_HERE", CLIENT_ID)
    return HTMLResponse(html_content)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8080)
