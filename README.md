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

### Option 1: Docker (Recommended)

Run the application in an isolated container without local restrictions (solves ISP Port 25 blocking).

**Prerequisites:** [Docker Desktop](https://www.docker.com/products/docker-desktop) installed and running.

1. **Clone the Repository**
   ```bash
   git clone https://github.com/bhatt8427/emailverify.github.io.git
   cd emailverify.github.io
   ```

2. **Run with Docker Compose**
   ```bash
   docker-compose up -d
   ```

3. **Access the App**
   Open **[http://localhost:5000](http://localhost:5000)**

**Useful Commands:**
- View logs: `docker-compose logs -f`
- Stop app: `docker-compose down`
- Rebuild: `docker-compose up -d --build`

---

### Option 2: Manual Installation (Python)

**Prerequisites:** Python 3.8+ and outbound access to Port 25.

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Start Backend**
   ```bash
   python app.py
   ```

3. **Start Frontend (Optional if running locally)**
   The backend now serves the frontend automatically at `http://localhost:5000`.

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
