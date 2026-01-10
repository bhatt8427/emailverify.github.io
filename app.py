import re
import smtplib
import socket
import dns.resolver
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor
import time
import logging

# Configure logging
logging.basicConfig(
    filename='email_verification.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Database imports
import sqlite3
from datetime import datetime, timedelta

# Rate limiting
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Initialize rate limiter
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per hour", "50 per minute"],
    storage_uri="memory://"
)

# Database helper functions
DB_PATH = 'email_verification.db'
CACHE_DURATION_DAYS = 30

def get_cached_result(email):
    """Retrieve cached verification result if not expired."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT status, reason, score, provider, risk_level, checks
            FROM verification_cache
            WHERE email = ? AND expires_at > datetime('now')
        ''', (email,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            import json
            return {
                'email': email,
                'status': result[0],
                'reason': result[1],
                'score': result[2],
                'provider': result[3],
                'risk_level': result[4],
                'checks': json.loads(result[5]) if result[5] else {},
                'cached': True
            }
    except Exception as e:
        logging.error(f"Cache read error: {e}")
    return None

def cache_result(email, result):
    """Cache verification result with expiration."""
    try:
        import json
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        expires_at = (datetime.now() + timedelta(days=CACHE_DURATION_DAYS)).isoformat()
        
        cursor.execute('''
            INSERT OR REPLACE INTO verification_cache
            (email, status, reason, score, provider, risk_level, checks, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            email,
            result.get('status'),
            result.get('reason'),
            result.get('score'),
            result.get('provider'),
            result.get('risk_level'),
            json.dumps(result.get('checks', {})),
            expires_at
        ))
        
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"Cache write error: {e}")

# List of common disposable email domains (for demo purposes)
DISPOSABLE_DOMAINS = {
    "mailinator.com", "guerrillamail.com", "yopmail.com", "10minutemail.com",
    "sharklasers.com", "tempmail.com", "throwawaymail.com"
}

def verify_syntax(email):
    """Regex validation for email syntax."""
    regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(regex, email) is not None

@lru_cache(maxsize=128)
def get_mx_records(domain):
    """Fetch MX records for a domain (Cached)."""
    try:
        records = dns.resolver.resolve(domain, 'MX')
        mx_records = sorted([(r.preference, str(r.exchange)) for r in records])
        return mx_records
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.resolver.NoNameservers, Exception):
        return None

def verify_smtp(email, mx_record):
    """
    Attempt to connect to the SMTP server and verify the existence of the email.
    Tries ports 25, 587, and 2525 to bypass ISP blocking.
    """
    hostname = mx_record
    ports = [25, 587, 2525]
    
    last_error = None
    
    for port in ports:
        try:
            # Create SMTP connection
            server = smtplib.SMTP(timeout=3) # Short timeout for fail-fast
            server.set_debuglevel(0)
            
            # Connect to server
            try:
                code, message = server.connect(hostname, port)
                if code != 220:
                    last_error = f"Connection refused by {hostname} on port {port}"
                    server.quit()
                    continue # Try next port
            except (socket.timeout, ConnectionRefusedError, socket.error) as e:
                last_error = f"Connection failed on port {port}: {str(e)}"
                continue # Try next port

            # Use local FQDN for HELO
            local_hostname = socket.getfqdn()
            server.helo(local_hostname)
            
            # Try TLS if supported (important for 587)
            try:
                server.starttls()
                server.helo(local_hostname)
            except smtplib.SMTPNotSupportedError:
                pass 

            server.mail('test@example.com')
            code, message = server.rcpt(email)
            server.quit()

            if code == 250:
                return 'valid', "SMTP OK"
            elif code == 550:
                msg_lower = str(message).lower()
                # Check for IP blocks, policy rejections, OR Sender Verification failures
                if any(k in msg_lower for k in ["block", "denied", "policy", "spam", "sender", "verify", "verification"]):
                     return 'unknown_block', f"Server Blocked/Rejected (550 on port {port}): {message}"
                else:
                     return 'invalid', "User does not exist (550)"
            elif code == 450 or code == 451 or code == 452:
                 return 'unknown', "Greylisted / Rate Limited"
            elif code == 530 or "authentication required" in str(message).lower():
                 # Valid connection but requires auth - proves domain is alive but can't verify user
                 return 'unknown_auth', f"Authentication Required (Port {port} Open)"
            else:
                return 'unknown', f"Server returned code {code} on port {port}"

        except (socket.timeout, smtplib.SMTPException, socket.error) as e:
            last_error = f"Error on port {port}: {str(e)}"
            continue

    # If we exhaust all ports
    if last_error:
        if "timeout" in str(last_error).lower():
            return 'unknown_timeout', "Connection Timeout (All ports blocked)"
        return 'unknown', f"Validation Failed: {last_error}"
    
    return 'unknown', "No connection could be established"

def identify_provider(mx_records):
    """Identify email provider based on MX records."""
    if not mx_records:
        return "Unknown"
    
    mx_str = str(mx_records).lower()
    if "google" in mx_str or "gmail" in mx_str:
        return "Google Workspace"
    elif "outlook" in mx_str or "microsoft" in mx_str or "hotmail" in mx_str:
        return "Microsoft Office 365"
    elif "pp.hosted" in mx_str or "proofpoint" in mx_str:
        return "Proofpoint (Enterprise)"
    elif "mimecast" in mx_str:
        return "Mimecast (Enterprise)"
    elif "yandex" in mx_str:
        return "Yandex"
    elif "zoho" in mx_str:
        return "Zoho Mail"
    elif "yahoo" in mx_str:
        return "Yahoo/AOL"
    elif "icloud" in mx_str or "apple" in mx_str:
        return "Apple iCloud"
    elif "proton" in mx_str:
        return "ProtonMail"
    elif "fastmail" in mx_str:
        return "FastMail"
    elif "gmx" in mx_str:
        return "GMX Mail"
    elif "mail.ru" in mx_str or "mailru" in mx_str:
        return "Mail.ru"
    elif "mailgun" in mx_str:
        return "Mailgun"
    elif "sendgrid" in mx_str:
        return "SendGrid"
    elif "rackspace" in mx_str:
        return "Rackspace Email"
    elif "1and1" in mx_str or "ionos" in mx_str:
        return "IONOS (1&1)"
    elif "godaddy" in mx_str:
        return "GoDaddy"
    else:
        return "Custom/Private Server"

def calculate_score(checks, status):
    """Calculate confidence score (0-100)."""
    if status == 'invalid':
        return 0
    
    score = 0
    # Base score steps
    if checks.get('syntax'): score += 20
    if checks.get('mx'): score += 30
    
    # Risk penalties
    if checks.get('disposable'): 
        return 0 # Override to 0 for disposable
    
    # SMTP verification bonuses
    smtp = checks.get('smtp_status')
    if status == 'valid':
        score += 50 # Max confidence
    elif status == 'catch-all':
        score += 30 # Valid domain, but user unverified
    elif status == 'risky':
        score += 25 # Valid domain but blocked, reasonable confidence it's a real server
    elif status == 'unknown':
        score += 10 # Some uncertainty
        
    return min(score, 100)

def process_email_data(email):
    """Core logic to verify a single email address."""
    email = email.strip()
    if not email:
        return {"error": "Email is required", "status": "invalid"}

    domain = email.split('@')[-1] if '@' in email else ''
    
    # --- Step 1: Syntax Check ---
    is_syntax_valid = verify_syntax(email)
    if not is_syntax_valid:
        return {
            "email": email,
            "status": "invalid",
            "reason": "Syntax Error",
            "score": 0,
            "provider": "Unknown",
            "checks": {"syntax": False, "domain": False, "mx": False, "risk": "High"}
        }

    # --- Step 2: Domain Check (Implicit in MX) & Step 3: MX Record Check ---
    mx_records = get_mx_records(domain)
    is_mx_valid = mx_records is not None and len(mx_records) > 0
    
    if not is_mx_valid:
         return {
            "email": email,
            "status": "invalid",
            "reason": "Invalid Domain (No MX)",
            "score": 10, # 20 for syntax - 10 penalty
            "provider": "Unknown",
            "checks": {"syntax": True, "domain": False, "mx": False, "risk": "High"}
        }

    # --- Step 4: Provider Intelligence ---
    provider_name = identify_provider(mx_records)

    # --- Step 5: Risk Analysis (Disposable, Role-based, SMTP Block) & Step 6: Final Verification ---
    is_disposable = domain in DISPOSABLE_DOMAINS
    
    checks = {
        "syntax": True,
        "domain": True,
        "mx": True,
        "disposable": is_disposable,
        "smtp_status": "skipped",
        "catch_all": False
    }

    if is_disposable:
        final_status = "invalid"
        final_reason = "Disposable Domain"
        risk_level = "Critical"
    else:
        # Proceed to SMTP ping for Risk Analysis
        priority_mx = mx_records[0][1]
        if priority_mx.endswith('.'): priority_mx = priority_mx[:-1]
        
        # 1. Verify the specific user
        # Initialize default values in case of crash/timeout
        smtp_status = 'skipped'
        smtp_message = 'Not checked'
        
        try:
             smtp_status, smtp_message = verify_smtp(email, priority_mx)
        except Exception as e:
             smtp_status = 'error'
             smtp_message = f"Internal Error: {str(e)}"

        checks['smtp_status'] = smtp_status
        
        final_status = 'valid' if smtp_status == 'valid' else ('invalid' if smtp_status == 'invalid' else 'unknown')
        final_reason = smtp_message if smtp_status != 'valid' else "Deliverable"
        
        # 2. Check for Catch-All (If status is Valid or Unknown/Risky)
        # Only check catch-all if we actually got a response, otherwise it will just timeout again
        if final_status == 'valid': 
            import uuid
            random_user = f"verify_{uuid.uuid4().hex[:8]}"
            catch_all_status, _ = verify_smtp(f"{random_user}@{domain}", priority_mx)
            
            if catch_all_status == 'valid':
                checks['catch_all'] = True
                final_status = 'catch-all'
                final_reason = "Accept-All Domain (Cannot verify specific user)"
                risk_level = "Medium" 
            else:
                checks['catch_all'] = False
        
        if final_status == 'unknown':
            # Better categorization of unknown states
            if 'timeout' in smtp_status or 'refused' in smtp_status or 'connect' in smtp_status:
                final_status = 'blocked'
                final_reason = f"Network Blocked: {smtp_message}"
            elif 'block' in smtp_status or 'unknown_block' in smtp_status:
                final_status = 'blocked'
                final_reason = f"Server Blocked: {smtp_message}"
            elif 'auth' in smtp_status:
                final_status = 'risky'
                final_reason = f"Authentication Required: {smtp_message}"
            elif smtp_status in ['unknown', 'error']:
                final_status = 'unknown'
                # Keep the original message
        
        # Risk Level Assessment
        if final_status == 'valid': risk_level = "Low"
        elif final_status == 'catch-all': risk_level = "Medium"
        elif final_status == 'risky': risk_level = "Medium"
        elif final_status == 'blocked': risk_level = "High"
        else: risk_level = "High"

    # --- Step 7: Final Confidence Score ---
    score = calculate_score(checks, final_status)
    
    return {
        "email": email,
        "status": final_status,
        "reason": final_reason,
        "score": score,
        "provider": provider_name,
        "risk_level": risk_level,
        "checks": checks
    }

@app.route('/verify', methods=['POST'])
@limiter.limit("30 per minute")
def verify_email():
    data = request.json
    email = data.get('email', '').strip()

    if not email:
        logging.warning("Verification attempt with empty email")
        return jsonify({"error": "Email is required"}), 400
    
    # Check cache first
    cached = get_cached_result(email)
    if cached:
        logging.info(f"Cache hit for {email}")
        return jsonify(cached)
    
    logging.info(f"Verifying email: {email}")
    result = process_email_data(email)
    logging.info(f"Verification result for {email}: {result.get('status')}")
    
    # Cache the result
    cache_result(email, result)
    
    return jsonify(result)

@app.route('/bulk-verify', methods=['POST'])
@limiter.limit("10 per minute")
def bulk_verify():
    data = request.json
    emails = data.get('emails', [])
    
    if not emails or not isinstance(emails, list):
         return jsonify({"error": "List of 'emails' is required"}), 400

    results = []
    # Use ThreadPoolExecutor for parallel processing
    # Limit max_workers to avoid killing the network or getting banned
    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(process_email_data, emails))
        
    return jsonify({"results": results, "count": len(results)})

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('.', path)

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', debug=True, port=port)
