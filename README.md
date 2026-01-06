# 📧 EmailVerifierPro

A premium, glassmorphism-style web application for bulk email verification. This tool performs a 6-step verification pipeline to ensure maximum accuracy, including syntax checks, MX record lookups, provider intelligence, and catch-all detection.

## ✨ Features

- **Single & Bulk Verification**: Validate one or thousands of emails.
- **6-Step Pipeline**: Syntax ➔ Domain ➔ MX ➔ Provider ➔ Risk ➔ Confidence Score.
- **Provider Intelligence**: Identifies Google, Microsoft, Zoho, and other major providers.
- **Accuracy Boost**: Detects "Catch-All" domains that accept any address.
- **File Support**: Drag and drop `.csv` or `.txt` files to import lists.
- **Export Results**: Download detailed results in `.csv` format.
- **Premium UI**: Modern glassmorphism design with responsiveness.

---

## 🛠️ Installation & Setup

### 1. Prerequisites
- **Python 3.8+** installed on your system.
- Outbound access to **Port 25** (for SMTP Pinging). 
  > [!NOTE]
  > Some ISPs or cloud providers (AWS, Azure) block Port 25. If blocked, users will be marked as "Risky".

### 2. Clone the Repository
```bash
git clone https://github.com/bhatt8427/emailverify.github.io.git
cd email-verifier-pro
```

### 3. Install Backend Dependencies
```bash
pip install -r requirements.txt
```

---

## 🚀 Running the App

You need to run **two** separate servers: one for the backend API and one for the frontend UI.

### Step 1: Start the Backend (Flask)
```bash
python app.py
```
The backend will run on `http://localhost:5000`.

### Step 2: Start the Frontend
Since the app uses modern Web APIs, it should be served via a local server to avoid CORS/File-System issues.
```bash
python -m http.server 8000
```
Open your browser and navigate to:
👉 **[http://localhost:8000](http://localhost:8000)**

---

## 📊 Verification Logic (The 6 Stages)

1.  **Syntax Check**: Validates if the email follows standard RFC formatting.
2.  **Domain Check**: Ensures the domain exists and is active.
3.  **MX Record Check**: Verifies that the domain is configured to receive emails.
4.  **Provider Intelligence**: Detects the host (e.g., Google Workspace, O365).
5.  **Risk Analysis**: Detects disposable emails, role-based accounts, and SMTP blocks.
6.  **Confidence Score**: Assigns a 0-100% score based on the previous steps.

---

## 📄 License
MIT License. Created for educational and professional verification purposes.
