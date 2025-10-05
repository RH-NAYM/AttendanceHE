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
import json

# --- Config ---
SERVICE_ACCOUNT_FILE = "service_account.json"
SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME", "AttendanceSystem")
MASTER_SHEET_NAME = os.getenv("MASTER_SHEET_NAME", "attendance_master")
EMPLOYEE_SHEET_NAME = os.getenv("EMPLOYEE_SHEET_NAME", "config_employees")
COMPANY_SHEET_NAME = os.getenv("COMPANY_SHEET_NAME", "config_companies")
ALLOWED_IPS = None  # Example: ["192.168.0.0/24"]
ENCRYPTED_CLIENT_ID_FILE = "client_id.enc"
FERNET_KEY = os.getenv("FERNET_KEY", "PeKU3K-rDOo8EeLrMxR3GjCDQgQCLiFP9fbktkHITgE=")
TIMEZONE = os.getenv("TIMEZONE", "Asia/Dhaka")
# ----------------

# Decrypt Google Client ID
try:
    fernet = Fernet(FERNET_KEY.encode())
    with open(ENCRYPTED_CLIENT_ID_FILE, "rb") as f:
        encrypted_client_id = f.read()
    CLIENT_ID = fernet.decrypt(encrypted_client_id).decode()
except Exception as e:
    raise RuntimeError(f"Failed to decrypt client ID: {e}")

# Initialize FastAPI
app = FastAPI(title="Attendance Hybrid API")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Google Sheets Auth
SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
try:
    creds = ServiceAccountCredentials.from_json_keyfile_name(SERVICE_ACCOUNT_FILE, SCOPE)
    gc = gspread.authorize(creds)
    sh = gc.open(SPREADSHEET_NAME)
    master_sheet = sh.worksheet(MASTER_SHEET_NAME)
    employee_sheet = sh.worksheet(EMPLOYEE_SHEET_NAME)
    company_sheet = sh.worksheet(COMPANY_SHEET_NAME)
except Exception as e:
    raise RuntimeError(f"Error initializing Google Sheets: {e}")



def create_service_account_from_env(output_path="service_account.json"):
    """Create service_account.json from environment variables"""

    # Fetch all required env variables
    required_vars = [
        'SERVICE_ACCOUNT_TYPE',
        'SERVICE_ACCOUNT_PROJECT_ID',
        'SERVICE_ACCOUNT_PRIVATE_KEY_ID',
        'SERVICE_ACCOUNT_PRIVATE_KEY',
        'SERVICE_ACCOUNT_CLIENT_EMAIL',
        'SERVICE_ACCOUNT_CLIENT_ID',
        'SERVICE_ACCOUNT_CLIENT_CERT_URL'
    ]

    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

    # Build service account dict
    service_account_data = {
        "type": os.getenv('SERVICE_ACCOUNT_TYPE'),
        "project_id": os.getenv('SERVICE_ACCOUNT_PROJECT_ID'),
        "private_key_id": os.getenv('SERVICE_ACCOUNT_PRIVATE_KEY_ID'),
        "private_key": os.getenv('SERVICE_ACCOUNT_PRIVATE_KEY').replace('\\n', '\n'),
        "client_email": os.getenv('SERVICE_ACCOUNT_CLIENT_EMAIL'),
        "client_id": os.getenv('SERVICE_ACCOUNT_CLIENT_ID'),
        "auth_uri": os.getenv('SERVICE_ACCOUNT_AUTH_URI', 'https://accounts.google.com/o/oauth2/auth'),
        "token_uri": os.getenv('SERVICE_ACCOUNT_TOKEN_URI', 'https://oauth2.googleapis.com/token'),
        "auth_provider_x509_cert_url": os.getenv(
            'SERVICE_ACCOUNT_AUTH_PROVIDER_CERT_URL', 
            'https://www.googleapis.com/oauth2/v1/certs'
        ),
        "client_x509_cert_url": os.getenv('SERVICE_ACCOUNT_CLIENT_CERT_URL')
    }

    # Write to file
    with open(output_path, "w") as f:
        json.dump(service_account_data, f, indent=2)

    print(f"Service account file created at {output_path}")
# Utility functions
def get_employees():
    try:
        rows = employee_sheet.get_all_records()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read employee sheet: {e}")
    return {
        str(r.get("E-mail", "")).strip().lower(): {
            "id": r.get("ID", ""),
            "full_name": r.get("Full Name", ""),
            "nickname": r.get("Nickname", ""),
            "office_email": str(r.get("Office mail", "")).strip()
        }
        for r in rows
    }

def get_companies():
    try:
        rows = company_sheet.get_all_records()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read company sheet: {e}")
    return [r["Company Name"] for r in rows if r.get("Company Name")]

def add_company(new_company: str):
    new_company = (new_company or "").strip()
    if not new_company:
        return
    existing = [c.lower() for c in get_companies()]
    if new_company.lower() not in existing:
        try:
            company_sheet.append_row([new_company])
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to add company: {e}")

def get_all_records():
    try:
        return master_sheet.get_all_records()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch master records: {e}")

def find_record_for_today(email: str, today: str, records: List[dict]):
    for idx, r in enumerate(records):
        if str(r.get("E-mail", "")).strip().lower() == email and str(r.get("Date", "")).strip() == today:
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
    except ValueError:
        return False
    return False

# Pydantic models
class TaskItem(BaseModel):
    task_for: str
    task_name: str
    task_details: str
    my_role: str

class AttendanceIn(BaseModel):
    email: str
    action: str
    tasks: List[TaskItem] = []
    
    


# API endpoints
@app.get("/config/companies")
def api_get_companies():
    return {"companies": get_companies()}

@app.get("/config/employees")
def api_get_employees():
    try:
        rows = employee_sheet.get_all_records()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read employee sheet: {e}")
    return [
        {
            "id": r.get("ID", ""),
            "full_name": r.get("Full Name", ""),
            "nickname": r.get("Nickname", ""),
            "email": r.get("E-mail", ""),
            "office_email": r.get("Office mail", "")
        }
        for r in rows
    ]

@app.post("/attendance")
def handle_attendance(payload: AttendanceIn, request: Request):
    ip = request.client.host
    if not is_ip_allowed(ip):
        raise HTTPException(status_code=403, detail=f"Access denied for IP: {ip}")

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
    emp_id = emp["id"]
    full_name = emp["full_name"]
    nickname = emp["nickname"]
    office_email = emp["office_email"]

    records = get_all_records()
    existing_record, row_index = find_record_for_today(email, today, records)

    if action == "checkin":
        if existing_record and existing_record.get("Check In") == "Checked In":
            raise HTTPException(status_code=400, detail="Already checked in today")
        row = [
            emp_id, nickname, full_name, email, office_email,
            today, time_now, "Checked In", "", "", ip, "", "", "", "", ""
        ]
        try:
            master_sheet.append_row(row)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to append check-in: {e}")
        return {"status": "checked_in", "time": time_now, "ip": ip, "office_email": office_email}

    elif action == "checkout":
        if not existing_record or existing_record.get("Check In") != "Checked In":
            raise HTTPException(status_code=400, detail="Check-in required before checkout")
        if not payload.tasks or len(payload.tasks) == 0:
            raise HTTPException(status_code=400, detail="At least one task is required for checkout")

        try:
            # Get the check-in IP from the existing record
            # The exact column name might need adjustment based on your Google Sheet
            checkin_ip = existing_record.get("Check in IP", existing_record.get("Check in IP", ""))
            
            # update original check-in row with first task
            first_task = payload.tasks[0]
            add_company(first_task.task_for)
            master_sheet.update_cell(row_index, 9, time_now)        # Time Out
            master_sheet.update_cell(row_index, 10, "Checked Out")
            master_sheet.update_cell(row_index, 12, ip)  # Set checkout IP for first task
            master_sheet.update_cell(row_index, 13, first_task.task_for)
            master_sheet.update_cell(row_index, 14, first_task.task_name)
            master_sheet.update_cell(row_index, 15, first_task.task_details)
            master_sheet.update_cell(row_index, 16, first_task.my_role)

            # append additional tasks as new rows with both check-in and checkout IPs
            for task in payload.tasks[1:]:
                add_company(task.task_for)
                row = [
                    emp_id, nickname, full_name, email, office_email,
                    today, time_now, "Checked In", time_now, "Checked Out",
                    checkin_ip,  # Copy check-in IP from the original record
                    ip,  # Checkout IP
                    task.task_for, task.task_name, task.task_details, task.my_role
                ]
                master_sheet.append_row(row)

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to update checkout: {e}")

        return {"status": "checked_out", "time": time_now, "ip": ip, "office_email": office_email}

    else:
        raise HTTPException(status_code=400, detail="Invalid action (use 'checkin' or 'checkout')")

# Serve HTML dynamically
@app.get("/")
def read_index():
    html_file_path = "static/index.html"
    try:
        with open(html_file_path, "r", encoding="utf-8") as f:
            html_content = f.read()
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="index.html not found")
    return HTMLResponse(html_content.replace("YOUR_CLIENT_ID_HERE", CLIENT_ID))


if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host=host, port=port)