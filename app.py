import gspread
from oauth2client.service_account import ServiceAccountCredentials
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List
from datetime import datetime
from ipaddress import ip_address, ip_network
from cryptography.fernet import Fernet
import os
import pytz
import json
import pytz
import uvicorn

def decrypt_service_account():
    """Decrypt encrypted_data.bin into a dict (not a file)."""
    try:
        with open("secret.key", "rb") as key_file:
            key = key_file.read()
    except FileNotFoundError:
        raise RuntimeError("Missing encryption key file: secret.key")

    cipher = Fernet(key)

    try:
        with open("encrypted_data.bin", "rb") as f:
            encrypted_data = f.read()
    except FileNotFoundError:
        raise RuntimeError("Missing encrypted data file: encrypted_data.bin")

    try:
        decrypted_data = cipher.decrypt(encrypted_data)
        return json.loads(decrypted_data.decode())
    except Exception as e:
        raise RuntimeError(f"Failed to decrypt service account: {e}")


# --- Config ---
SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME", "AttendanceSystem")
MASTER_SHEET_NAME = os.getenv("MASTER_SHEET_NAME", "attendance_master")
EMPLOYEE_SHEET_NAME = os.getenv("EMPLOYEE_SHEET_NAME", "config_employees")
COMPANY_SHEET_NAME = os.getenv("COMPANY_SHEET_NAME", "config_companies")
ALLOWED_IPS = None
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

# --- Google Sheets Auth (in-memory) ---
SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

try:
    service_account_dict = decrypt_service_account()  # in-memory dict
    creds = ServiceAccountCredentials.from_json_keyfile_dict(service_account_dict, SCOPE)
    gc = gspread.authorize(creds)
    sh = gc.open(SPREADSHEET_NAME)
    master_sheet = sh.worksheet(MASTER_SHEET_NAME)
    employee_sheet = sh.worksheet(EMPLOYEE_SHEET_NAME)
    company_sheet = sh.worksheet(COMPANY_SHEET_NAME)
except Exception as e:
    raise RuntimeError(f"Error initializing Google Sheets: {e}")


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
            "office_email": str(r.get("Office mail", "")).strip(),
            "score": int(r.get("Score",0))
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

# # OLD Logic
# def get_all_records():
#     try:
#         return master_sheet.get_all_records()
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Failed to fetch master records: {e}")


# # NEW Logic
def get_all_records():
    try:
        return master_sheet.get_all_records()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch master records: {e}")





# # OLD Logic
# def find_record_for_today(email: str, today: str, records: List[dict]):
#     for idx, r in enumerate(records):
#         if str(r.get("E-mail", "")).strip().lower() == email and str(r.get("Date", "")).strip() == today:
#             return r, idx + 2
#     return None, None


# # NEW Logic
def find_record_for_today(email: str, today: str, records: List[dict]):
    """Find the most recent record for today (searches from top to bottom)"""
    for idx, r in enumerate(records):
        if str(r.get("E-mail", "")).strip().lower() == email and str(r.get("Date", "")).strip() == today:
            # Add 2 because: +1 for 1-indexed sheets, +1 for header row
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


# --- API Endpoints ---
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
            "office_email": r.get("Office mail", ""),
            "score": int(r.get("Score", 0))
        }
        for r in rows
    ]


# NEW Lodic
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
    score = emp["score"]

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
            # Insert at row 2 (right after header) instead of appending to bottom
            master_sheet.insert_row(row, index=2)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to insert check-in: {e}")
        return {"status": "checked_in", "time": time_now, "ip": ip, "office_email": office_email}

    elif action == "checkout":
        if not existing_record or existing_record.get("Check In") != "Checked In":
            raise HTTPException(status_code=400, detail="Check-in required before checkout")
        if not payload.tasks or len(payload.tasks) == 0:
            raise HTTPException(status_code=400, detail="At least one task is required for checkout")

        try:
            checkin_ip = existing_record.get("Check in IP", existing_record.get("Check in IP", ""))
            first_task = payload.tasks[0]
            add_company(first_task.task_for)
            
            # Update the existing check-in row with checkout info
            master_sheet.update_cell(row_index, 9, time_now)
            master_sheet.update_cell(row_index, 10, "Checked Out")
            master_sheet.update_cell(row_index, 12, ip)
            master_sheet.update_cell(row_index, 13, first_task.task_for)
            master_sheet.update_cell(row_index, 14, first_task.task_name)
            master_sheet.update_cell(row_index, 15, first_task.task_details)
            master_sheet.update_cell(row_index, 16, first_task.my_role)

            # For additional tasks, insert them at the top (row 2)
            for task in payload.tasks[1:]:
                add_company(task.task_for)
                row = [
                    emp_id, nickname, full_name, email, office_email,
                    today, time_now, "Checked In", time_now, "Checked Out",
                    checkin_ip, ip,
                    task.task_for, task.task_name, task.task_details, task.my_role
                ]
                # Insert additional task rows at the top
                master_sheet.insert_row(row, index=2)

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to update checkout: {e}")

        return {"status": "checked_out", "time": time_now, "ip": ip, "office_email": office_email}

    else:
        raise HTTPException(status_code=400, detail="Invalid action (use 'checkin' or 'checkout')")

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
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host=host, port=port)