📊 Attendance Hybrid System ==>> dev Branch
https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi
https://img.shields.io/badge/Google%2520Sheets-34A853?style=for-the-badge&logo=google-sheets&logoColor=white
https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white

A modern, secure attendance tracking system that combines the power of FastAPI with the flexibility of Google Sheets. Featuring Google OAuth authentication, real-time logging, and a responsive UI.

✨ Key Features
🔐 Google OAuth2 Authentication - Secure employee sign-in

⏰ Check-in/Check-out Logging - Real-time attendance tracking

🏢 Dynamic Company Management - Add new companies on-the-fly

📱 Responsive Design - Works seamlessly on desktop and mobile

🔔 Toast Notifications - User-friendly feedback system

🌐 IP-Based Access Control - Restrict to office networks

📊 Google Sheets Backend - No database setup required

🛠️ Tech Stack
```bash
Backend:

FastAPI (Python 3.11+)

Uvicorn (ASGI server)

Frontend:

HTML5, CSS3, JavaScript

Google Sign-In API

Data Storage:

Google Sheets API

Service Account Authentication

Authentication:

Google OAuth 2.0

📋 Prerequisites
Before you begin, ensure you have:

Python 3.11 or higher installed

A Google Cloud Platform account

Access to Google Sheets API

Office network IP range (for access restrictions)
```

🚀 Installation & Setup
1. Clone the Repository
```bash
git clone https://github.com/your-username/attendance-hybrid-system.git
cd attendance-hybrid-system
```
2. Create Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```
3. Install Dependencies
```bash
pip install -r requirements.txt
```
4. Google Cloud Setup
Create a new project in Google Cloud Console

Enable Google Sheets API and Google Identity Services

Create OAuth 2.0 credentials (Web application type)

Create a service account and download the JSON credentials

5. Configuration
Rename the service account JSON file to service_account.json and place it in the root directory.

Update the allowed IP ranges in main.py:

python
ALLOWED_IPS = ["192.168.1.0/24", "127.0.0.1"]  # Your office network
6. Spreadsheet Setup
Create a Google Sheets spreadsheet with three sheets:

employees - For storing employee data

companies - For company information

attendance - For attendance records

Share the spreadsheet with your service account email.

7. Run the Application
bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
Visit http://localhost:8000 in your browser.

📁 Project Structure
text
attendance-hybrid-system/
│
├── main.py                 # FastAPI application
├── service_account.json    # Google Sheets credentials (gitignored)
├── requirements.txt        # Python dependencies
├── .gitignore             # Git ignore rules
│
├── static/
│   ├── index.html         # Frontend UI
│   ├── styles.css         # Custom styles
│   └── script.js          # Client-side functionality
│
└── README.md              # This file
🔧 Configuration Options
Environment Variables
Create a .env file for custom configuration:

ini
# Google OAuth Configuration
GOOGLE_CLIENT_ID=your_google_client_id
ALLOWED_DOMAINS=yourcompany.com

# Application Settings
HOST=0.0.0.0
PORT=8000
DEBUG=False

# IP Restrictions
ALLOWED_IPS=192.168.1.0/24,127.0.0.1
Spreadsheet Customization
Modify sheet names in main.py:

python
SPREADSHEET_NAME = "Attendance System"
EMPLOYEES_SHEET = "employees"
COMPANIES_SHEET = "companies"
ATTENDANCE_SHEET = "attendance"
🎨 Frontend Customization
Updating the Company Dropdown
Edit the updateCompanyDropdown() function in static/script.js:

javascript
function updateCompanyDropdown(companies) {
    const companySelect = document.getElementById('company');
    companySelect.innerHTML = '<option value="">Select Company</option>';
    
    companies.forEach(company => {
        const option = document.createElement('option');
        option.value = company;
        option.textContent = company;
        companySelect.appendChild(option);
    });
    
    // Add "Other" option
    const otherOption = document.createElement('option');
    otherOption.value = 'other';
    otherOption.textContent = 'Other (specify below)';
    companySelect.appendChild(otherOption);
}
Customizing Toast Messages
Modify the showToast() function in static/script.js:

javascript
function showToast(message, type = 'success') {
    // Toast implementation with custom styles
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.remove();
    }, 3000);
}
Google Sign-In Integration
Update the Google Sign-In configuration in static/index.html:

html
<script>
    function handleCredentialResponse(response) {
        // Verify the Google ID token with your backend
        fetch('/verify-token', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ token: response.credential })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showToast('Sign-in successful!', 'success');
            } else {
                showToast('Sign-in failed. Please try again.', 'error');
            }
        });
    }
</script>
🔒 Security Features
IP-based access restriction for office networks only

Google OAuth 2.0 authentication

Service account authentication for Google Sheets API

Input validation and sanitization

Secure token handling

📝 API Endpoints
Method	Endpoint	Description
GET	/	Serve the main application UI
POST	/checkin	Process employee check-in
POST	/checkout	Process employee check-out
GET	/companies	Retrieve list of companies
POST	/add-company	Add a new company to the system
🤝 Contributing
We welcome contributions! Please follow these steps:

Fork the repository

Create a feature branch: git checkout -b feature/amazing-feature

Commit your changes: git commit -m 'Add amazing feature'

Push to the branch: git push origin feature/amazing-feature

Open a pull request

📄 License
This project is licensed under the MIT License - see the LICENSE file for details.

🆘 Support
If you encounter any issues:

Check the browser console for errors

Verify your Google Sheets API credentials

Ensure your IP address is in the allowed list

Check that the Google Sheets spreadsheet is properly shared with the service account

For additional help, please open an issue on GitHub.

🔄 Version History
v1.0.0 (2023-10-15)

Initial release

Basic check-in/check-out functionality

Google OAuth integration

Google Sheets backend

⭐ Star this repo if you found it helpful!

<div align="center"> Made with ❤️ using FastAPI and Google Sheets </div>