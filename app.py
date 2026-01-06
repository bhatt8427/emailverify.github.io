import re
import smtplib
import socket
import dns.resolver
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# List of common disposable email domains (for demo purposes)
DISPOSABLE_DOMAINS = {
    "mailinator.com", "guerrillamail.com", "yopmail.com", "10minutemail.com",
    "sharklasers.com", "tempmail.com", "throwawaymail.com"
}

def verify_syntax(email):
    """Regex validation for email syntax."""
    regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(regex, email) is not None

def get_mx_records(domain):
    """Fetch MX records for a domain."""
    try:
        records = dns.resolver.resolve(domain, 'MX')
        mx_records = sorted([(r.preference, str(r.exchange)) for r in records])
        return mx_records
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.resolver.NoNameservers, Exception):
        return None

def verify_smtp(email, mx_record):
    """
    Attempt to connect to the SMTP server and verify the existence of the email.
    Note: This is often blocked by ISPs on port 25.
    """
    hostname = mx_record
    try:
        # Create SMTP connection
        server = smtplib.SMTP(timeout=5) # Increased timeout slightly
        server.set_debuglevel(0)
        
        # Connect to server
        code, message = server.connect(hostname, 25)
        if code != 220:
            return 'failed_connect', f"Connection refused by {hostname}"

        # Use local FQDN for HELO to be more polite, or a generic placeholder
        local_hostname = socket.getfqdn()
        server.helo(local_hostname)
        
        # Try TLS if supported
        try:
            server.starttls()
            server.helo(local_hostname) # HELO again after TLS
        except smtplib.SMTPNotSupportedError:
            pass # Server doesn't support TLS, continue in cleartext

        server.mail('test@example.com') # Use a more generic, neutral sender
        code, message = server.rcpt(email)
        server.quit()

        if code == 250:
            return 'valid', "SMTP OK"
        elif code == 550:
            # Distinguish between "User unknown" and "IP blocked" (both often 550)
            msg_lower = str(message).lower()
            if "block" in msg_lower or "denied" in msg_lower or "policy" in msg_lower or "spamtRAP" in msg_lower:
                 return 'unknown_block', f"Server Blocked IP (550): {message}"
            else:
                 return 'invalid', "User does not exist (550)"
        elif code == 450 or code == 451 or code == 452:
             return 'unknown', "Greylisted / Rate Limited"
        else:
            return 'unknown', f"Server returned code {code}"

    except socket.timeout:
        return 'unknown_timeout', "Connection Timeout"
    except ConnectionRefusedError:
        return 'unknown_refused', "Connection Refused"
    except smtplib.SMTPConnectError:
        return 'unknown_connect', "Handshake Failed"
    except (socket.error, smtplib.SMTPException) as e:
        return 'unknown', f"SMTP Error: {str(e)}"

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
    elif "proton" in mx_str:
        return "ProtonMail"
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

@app.route('/verify', methods=['POST'])
def verify_email():
    data = request.json
    email = data.get('email', '').strip()

    if not email:
        return jsonify({"error": "Email is required"}), 400

    domain = email.split('@')[-1] if '@' in email else ''
    
    # --- Step 1: Syntax Check ---
    is_syntax_valid = verify_syntax(email)
    if not is_syntax_valid:
        return jsonify({
            "email": email,
            "status": "invalid",
            "reason": "Syntax Error",
            "score": 0,
            "provider": "Unknown",
            "checks": {"syntax": False, "domain": False, "mx": False, "risk": "High"}
        })

    # --- Step 2: Domain Check (Implicit in MX) & Step 3: MX Record Check ---
    mx_records = get_mx_records(domain)
    is_mx_valid = mx_records is not None and len(mx_records) > 0
    
    if not is_mx_valid:
         return jsonify({
            "email": email,
            "status": "invalid",
            "reason": "Invalid Domain (No MX)",
            "score": 10, # 20 for syntax - 10 penalty
            "provider": "Unknown",
            "checks": {"syntax": True, "domain": False, "mx": False, "risk": "High"}
        })

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
        smtp_status, smtp_message = verify_smtp(email, priority_mx)
        checks['smtp_status'] = smtp_status
        
        final_status = 'valid' if smtp_status == 'valid' else ('invalid' if smtp_status == 'invalid' else 'unknown')
        final_reason = smtp_message if smtp_status != 'valid' else "Deliverable"
        
        # 2. Check for Catch-All (If status is Valid or Unknown/Risky)
        # If the specific user was valid, we must ensure it's not simply because the server accepts EVERYTHING.
        if final_status == 'valid' or final_status == 'unknown':
            import uuid
            random_user = f"verify_{uuid.uuid4().hex[:8]}"
            catch_all_status, _ = verify_smtp(f"{random_user}@{domain}", priority_mx)
            
            if catch_all_status == 'valid':
                checks['catch_all'] = True
                final_status = 'catch-all'
                final_reason = "Accept-All Domain (Cannot verify specific user)"
                risk_level = "Medium" # Catch-alls are risky because we don't know if the user acts on it
            else:
                checks['catch_all'] = False
        
        if final_status == 'unknown':
            if 'timeout' in smtp_status or 'refused' in smtp_status or 'connect' in smtp_status or 'block' in smtp_status:
                final_status = 'risky'
                final_reason = f"Valid Domain (Blocked: {smtp_message})"
        
        # Risk Level Assessment
        if final_status == 'valid': risk_level = "Low"
        elif final_status == 'catch-all': risk_level = "Medium"
        elif final_status == 'risky': risk_level = "Medium"
        else: risk_level = "High"

    # --- Step 7: Final Confidence Score ---
    score = calculate_score(checks, final_status)
    
    return jsonify({
        "email": email,
        "status": final_status,
        "reason": final_reason,
        "score": score,
        "provider": provider_name,
        "risk_level": risk_level,
        "checks": checks
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)
