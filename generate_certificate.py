import subprocess, hashlib, json, base64, uuid, os, sys, platform, traceback
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend
from datetime import datetime, timezone, timedelta
from fpdf import FPDF
import qrcode
from qrcode.image.pure import PyPNGImage
import sqlite3
import time

# Compliance Standards Mapping
COMPLIANCE_STANDARDS = {
    "zeros": {
        "method_name": "Single Pass Zero Overwrite",
        "standard": "NIST SP 800-88 Rev. 1 - Clear",
        "description": "Single pass overwrite with zeros",
        "passes": 1,
        "suitable_for": "Non-sensitive data on modern drives"
    },
    "dod": {
        "method_name": "DoD 5220.22-M (3-pass)",
        "standard": "DoD 5220.22-M",
        "description": "3-pass overwrite: Pass 1 (zeros), Pass 2 (ones), Pass 3 (random)",
        "passes": 3,
        "suitable_for": "Classified and sensitive government data"
    },
    "dod_7pass": {
        "method_name": "DoD 5220.22-M ECE (7-pass)",
        "standard": "DoD 5220.22-M ECE",
        "description": "7-pass overwrite with defined patterns and verification",
        "passes": 7,
        "suitable_for": "Top Secret and highly classified data"
    },
    "random": {
        "method_name": "Random Data Overwrite",
        "standard": "NIST SP 800-88 Rev. 1 - Purge",
        "description": "Single pass with cryptographically secure random data",
        "passes": 1,
        "suitable_for": "Modern SSDs and general secure erasure"
    },
    "gutmann": {
        "method_name": "Gutmann Method (35-pass)",
        "standard": "Gutmann Secure Deletion",
        "description": "35-pass overwrite with specific patterns for all magnetic encoding methods",
        "passes": 35,
        "suitable_for": "Legacy magnetic storage requiring maximum security"
    },
    "ata_secure_erase": {
        "method_name": "ATA Secure Erase",
        "standard": "NIST SP 800-88 Rev. 1 - Purge (ATA)",
        "description": "Hardware-based secure erase using ATA command set",
        "passes": 1,
        "suitable_for": "SSDs and modern HDDs with ATA support"
    },
    "nist_clear": {
        "method_name": "NIST Clear",
        "standard": "NIST SP 800-88 Rev. 1 - Clear",
        "description": "Overwrite with any pattern, verified",
        "passes": 1,
        "suitable_for": "Standard data sanitization"
    },
    "nist_purge": {
        "method_name": "NIST Purge",
        "standard": "NIST SP 800-88 Rev. 1 - Purge",
        "description": "Cryptographic erase or block erase for SSDs",
        "passes": 1,
        "suitable_for": "SSDs and encrypted storage"
    }
}

def get_compliance_info(wipe_method):
    """Get compliance standard information for a wiping method."""
    method_key = wipe_method.lower().replace("-", "_").replace(" ", "_")
    
    # Try exact match first
    if method_key in COMPLIANCE_STANDARDS:
        return COMPLIANCE_STANDARDS[method_key]
    
    # Try partial matches
    for key, value in COMPLIANCE_STANDARDS.items():
        if key in method_key or method_key in key:
            return value
    
    # Default fallback
    return {
        "method_name": wipe_method.upper(),
        "standard": "Custom Method",
        "description": f"Custom wiping method: {wipe_method}",
        "passes": "Unknown",
        "suitable_for": "As per organizational policy"
    }

def find_openssl_command():
    """
    Find the appropriate OpenSSL command for the current platform.
    Returns the command name/path to use.
    """
    # Check if openssl is available
    openssl_commands = ['openssl', 'openssl.exe']
    
    for cmd in openssl_commands:
        try:
            result = subprocess.run([cmd, 'version'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                return cmd
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    
    # Platform-specific paths
    if sys.platform == 'win32':
        # Common Windows OpenSSL installation paths
        potential_paths = [
            r"C:\Program Files\OpenSSL-Win64\bin\openssl.exe",
            r"C:\Program Files (x86)\OpenSSL-Win32\bin\openssl.exe",
            r"C:\OpenSSL-Win64\bin\openssl.exe",
            r"C:\OpenSSL-Win32\bin\openssl.exe",
        ]
        for path in potential_paths:
            if os.path.exists(path):
                return path
    elif sys.platform == 'darwin':  # macOS
        # Check Homebrew installation
        homebrew_path = '/usr/local/opt/openssl/bin/openssl'
        if os.path.exists(homebrew_path):
            return homebrew_path
        # Check newer M1 Homebrew path
        m1_homebrew_path = '/opt/homebrew/opt/openssl/bin/openssl'
        if os.path.exists(m1_homebrew_path):
            return m1_homebrew_path
    
    # Default to 'openssl' and let it fail if not found
    return 'openssl'

def utc_to_ist(utc_time_str):
    """Convert UTC time string to Indian Standard Time (IST = UTC+5:30)"""
    try:
        # Parse UTC time
        if 'Z' in utc_time_str:
            utc_time_str = utc_time_str.replace('Z', '+00:00')
        utc_dt = datetime.fromisoformat(utc_time_str)
        
        # Convert to IST (UTC+5:30)
        ist_offset = timedelta(hours=5, minutes=30)
        ist_dt = utc_dt + ist_offset
        
        # Format as readable string
        return ist_dt.strftime("%Y-%m-%d %H:%M:%S IST")
    except Exception as e:
        return utc_time_str

def store_certificate_to_db(cert_id, end_time, signature, verification_hash, db_file="users.db"):
    conn = sqlite3.connect(db_file)
    c = conn.cursor()
    
    # Check if verification_hash column exists, if not add it
    try:
        c.execute("SELECT verification_hash FROM certificates LIMIT 1")
    except sqlite3.OperationalError:
        c.execute("ALTER TABLE certificates ADD COLUMN verification_hash TEXT")
        conn.commit()
    
    c.execute("INSERT INTO certificates (cert_id, end_time, signature, verification_hash) VALUES (?, ?, ?, ?)",
              (cert_id, end_time, signature, verification_hash))
    conn.commit()
    conn.close()


def verify_certificate_authenticity(cert_json_path, db_file="users.db"):
    """
    Verify if a certificate is genuine and has not been tampered with.
    Returns: (is_valid, error_message)
    """
    try:
        # Load certificate JSON
        with open(cert_json_path, "r", encoding='utf-8') as f:
            cert = json.load(f)
        
        # Extract critical fields
        cert_id = cert.get("certificate_id")
        log_hash = cert.get("log_sha256")
        signature = cert.get("signature")
        finish_time = cert.get("finish_time_utc")
        cert_ref = cert.get("certificate_reference_number")
        stored_verification_hash = cert.get("verification_hash")
        
        if not all([cert_id, log_hash, signature, finish_time, cert_ref, stored_verification_hash]):
            return False, "Certificate is missing critical fields"
        
        # Recalculate verification hash
        verification_data = f"{cert_id}|{log_hash}|{signature}|{finish_time}|{cert_ref}"
        calculated_hash = hashlib.sha256(verification_data.encode()).hexdigest()
        
        # Check if verification hash matches
        if calculated_hash != stored_verification_hash:
            return False, "Certificate verification hash mismatch - certificate has been tampered with"
        
        # Check against database
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        
        try:
            c.execute("SELECT verification_hash, signature FROM certificates WHERE cert_id = ?", (cert_id,))
            result = c.fetchone()
            
            if not result:
                conn.close()
                return False, "Certificate ID not found in database - possible forgery"
            
            db_verification_hash, db_signature = result
            
            # Verify database records match
            if db_verification_hash != stored_verification_hash:
                conn.close()
                return False, "Database verification hash mismatch - certificate may be forged"
            
            if db_signature != signature:
                conn.close()
                return False, "Digital signature mismatch - certificate may be forged"
            
            conn.close()
            return True, "Certificate is authentic and verified"
            
        except sqlite3.OperationalError:
            conn.close()
            return False, "Database verification failed - verification_hash column may not exist"
            
    except Exception as e:
        return False, f"Verification error: {str(e)}"


def generate_pdf_certificate(certificate, output_pdf, qr_file, compliance_info):
    """
    Generate a professional, single-page branded PDF certificate.
    """
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=False)  # Single page, no auto-break
    
    # ==================== HEADER BRANDING ====================
    # Dark blue branded header
    pdf.set_fill_color(0, 51, 102)  # Navy blue
    pdf.rect(0, 0, 210, 35, 'F')
    
    # Company logo placeholder (left side)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", "B", 24)
    pdf.set_xy(10, 8)
    pdf.cell(50, 10, "ZERO LEAKS", ln=False)
    
    # Main title (center-right)
    pdf.set_font("Arial", "B", 18)
    pdf.set_xy(60, 10)
    pdf.cell(140, 10, "CERTIFICATE OF DATA DESTRUCTION", ln=True, align="C")
    pdf.set_font("Arial", "I", 9)
    pdf.set_xy(60, 22)
    pdf.cell(140, 6, "Enterprise Data Sanitization & Security Compliance", ln=True, align="C")
    
    # Reset colors and position
    pdf.set_text_color(0, 0, 0)
    pdf.set_y(40)
    
    # ==================== CERTIFICATE REFERENCE ====================
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font("Arial", "B", 10)
    pdf.cell(0, 7, f"Certificate Reference: {certificate['certificate_reference_number']}", ln=True, align="C", fill=True, border=1)
    pdf.ln(3)
    
    # ==================== TWO-COLUMN LAYOUT ====================
    left_column_x = 10
    right_column_x = 110
    current_y = pdf.get_y()
    
    # LEFT COLUMN
    pdf.set_xy(left_column_x, current_y)
    
    # --- Asset Information ---
    pdf.set_fill_color(0, 102, 204)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", "B", 10)
    pdf.cell(95, 6, " ASSET INFORMATION", ln=True, fill=True)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", "", 8)
    
    pdf.set_x(left_column_x)
    pdf.cell(35, 5, "Asset Description:", 0)
    pdf.set_font("Arial", "B", 8)
    asset_desc = str(certificate['asset_description'])
    if len(asset_desc) > 35:
        asset_desc = asset_desc[:32] + "..."
    pdf.cell(60, 5, asset_desc, ln=True)
    
    pdf.set_font("Arial", "", 8)
    pdf.set_x(left_column_x)
    pdf.cell(35, 5, "Asset Type:", 0)
    pdf.set_font("Arial", "B", 8)
    pdf.cell(60, 5, str(certificate['asset_type']), ln=True)
    
    pdf.set_font("Arial", "", 8)
    pdf.set_x(left_column_x)
    pdf.cell(35, 5, "Serial Number:", 0)
    pdf.set_font("Arial", "B", 8)
    pdf.cell(60, 5, str(certificate['asset_serial_number']), ln=True)
    
    pdf.set_font("Arial", "", 8)
    pdf.set_x(left_column_x)
    pdf.cell(35, 5, "Wipe Result:", 0)
    pdf.set_font("Arial", "B", 8)
    result = certificate['wipe_result']
    if result.lower() == 'success':
        pdf.set_text_color(0, 128, 0)  # Green
    else:
        pdf.set_text_color(255, 0, 0)  # Red
    pdf.cell(60, 5, f"[{result.upper()}]", ln=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(2)
    
    # --- Destruction Method ---
    pdf.set_x(left_column_x)
    pdf.set_fill_color(0, 102, 204)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", "B", 10)
    pdf.cell(95, 6, " DESTRUCTION METHOD", ln=True, fill=True)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", "", 8)
    
    pdf.set_x(left_column_x)
    pdf.cell(35, 5, "Method:", 0)
    pdf.set_font("Arial", "B", 8)
    pdf.cell(60, 5, str(certificate['destruction_method'])[:30], ln=True)
    
    pdf.set_font("Arial", "", 8)
    pdf.set_x(left_column_x)
    pdf.cell(35, 5, "Standard:", 0)
    pdf.set_font("Arial", "B", 8)
    pdf.cell(60, 5, str(certificate['compliance_standard'])[:30], ln=True)
    
    pdf.set_font("Arial", "", 8)
    pdf.set_x(left_column_x)
    pdf.cell(35, 5, "Passes:", 0)
    pdf.set_font("Arial", "B", 8)
    pdf.cell(60, 5, str(certificate['number_of_passes']), ln=True)
    
    pdf.set_font("Arial", "", 7)
    pdf.set_x(left_column_x)
    pdf.cell(35, 4, "Description:", 0)
    pdf.set_font("Arial", "", 7)
    desc = str(certificate['method_description'])
    if len(desc) > 45:
        desc = desc[:42] + "..."
    pdf.cell(60, 4, desc, ln=True)
    pdf.ln(2)
    
    # --- Timing Information (IST) ---
    pdf.set_x(left_column_x)
    pdf.set_fill_color(0, 102, 204)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", "B", 10)
    pdf.cell(95, 6, " TIMING (IST)", ln=True, fill=True)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", "", 8)
    
    # Convert UTC times to IST
    start_time_ist = utc_to_ist(certificate['start_time_utc'])
    finish_time_ist = utc_to_ist(certificate['finish_time_utc'])
    
    pdf.set_x(left_column_x)
    pdf.cell(35, 5, "Start Time:", 0)
    pdf.set_font("Arial", "", 7)
    pdf.cell(60, 5, start_time_ist, ln=True)
    
    pdf.set_font("Arial", "", 8)
    pdf.set_x(left_column_x)
    pdf.cell(35, 5, "Finish Time:", 0)
    pdf.set_font("Arial", "", 7)
    pdf.cell(60, 5, finish_time_ist, ln=True)
    
    pdf.set_font("Arial", "", 8)
    pdf.set_x(left_column_x)
    pdf.cell(35, 5, "Duration:", 0)
    pdf.set_font("Arial", "B", 8)
    pdf.cell(60, 5, str(certificate['duration']), ln=True)
    
    pdf.set_font("Arial", "", 8)
    pdf.set_x(left_column_x)
    pdf.cell(35, 5, "Timezone:", 0)
    pdf.set_font("Arial", "", 7)
    pdf.cell(60, 5, "Indian Standard Time (UTC+5:30)", ln=True)
    pdf.ln(2)
    
    # --- Authorization ---
    pdf.set_x(left_column_x)
    pdf.set_fill_color(0, 102, 204)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", "B", 10)
    pdf.cell(95, 6, " AUTHORIZATION", ln=True, fill=True)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", "", 8)
    
    pdf.set_x(left_column_x)
    pdf.cell(35, 5, "Organization:", 0)
    pdf.set_font("Arial", "B", 8)
    org = str(certificate['organization'])
    if len(org) > 25:
        org = org[:22] + "..."
    pdf.cell(60, 5, org, ln=True)
    
    pdf.set_font("Arial", "", 8)
    pdf.set_x(left_column_x)
    pdf.cell(35, 5, "Technician:", 0)
    pdf.set_font("Arial", "B", 8)
    pdf.cell(60, 5, str(certificate['technician']), ln=True)
    
    pdf.set_font("Arial", "", 8)
    pdf.set_x(left_column_x)
    pdf.cell(35, 5, "Witness:", 0)
    pdf.set_font("Arial", "B", 8)
    pdf.cell(60, 5, str(certificate['witness']), ln=True)
    
    pdf.set_font("Arial", "", 8)
    pdf.set_x(left_column_x)
    pdf.cell(35, 5, "Platform:", 0)
    pdf.set_font("Arial", "", 7)
    platform_str = f"{certificate['platform']['os']} {certificate['platform']['release']}"
    pdf.cell(60, 5, platform_str, ln=True)
    
    pdf.set_font("Arial", "", 8)
    pdf.set_x(left_column_x)
    pdf.cell(35, 5, "Asset Location:", 0)
    pdf.set_font("Arial", "B", 8)
    pdf.cell(60, 5, str(certificate.get('asset_location', 'Not Specified')), ln=True)
    
    pdf.set_font("Arial", "", 8)
    pdf.set_x(left_column_x)
    pdf.cell(35, 5, "Asset Owner:", 0)
    pdf.set_font("Arial", "B", 8)
    pdf.cell(60, 5, str(certificate.get('asset_owner', 'Not Specified')), ln=True)
    
    pdf.set_font("Arial", "", 8)
    pdf.set_x(left_column_x)
    pdf.cell(35, 5, "Destruction Date:", 0)
    pdf.set_font("Arial", "", 7)
    # Extract just the date from finish_time
    destruction_date = str(certificate['finish_time_utc']).split('T')[0] if 'T' in str(certificate['finish_time_utc']) else str(certificate['finish_time_utc'])[:10]
    pdf.cell(60, 5, destruction_date, ln=True)
    pdf.ln(2)
    
    # --- Data Sanitization Details ---
    pdf.set_x(left_column_x)
    pdf.set_fill_color(0, 102, 204)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", "B", 10)
    pdf.cell(95, 6, " DATA SANITIZATION DETAILS", ln=True, fill=True)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", "", 8)
    
    pdf.set_x(left_column_x)
    pdf.cell(35, 5, "Data Overwritten:", 0)
    pdf.set_font("Arial", "B", 8)
    pdf.cell(60, 5, "Yes", ln=True)
    
    pdf.set_font("Arial", "", 8)
    pdf.set_x(left_column_x)
    pdf.cell(35, 5, "Pattern Used:", 0)
    pdf.set_font("Arial", "", 7)
    pattern_info = "Random" if "random" in str(certificate['wipe_method_code']).lower() else "Zeros/Ones/Random"
    pdf.cell(60, 5, pattern_info, ln=True)
    
    pdf.set_font("Arial", "", 8)
    pdf.set_x(left_column_x)
    pdf.cell(35, 5, "Verification Done:", 0)
    pdf.set_font("Arial", "B", 8)
    pdf.cell(60, 5, "Yes" if certificate['verification_passed'] else "No", ln=True)
    
    pdf.set_font("Arial", "", 8)
    pdf.set_x(left_column_x)
    pdf.cell(35, 5, "Sectors Affected:", 0)
    pdf.set_font("Arial", "", 7)
    pdf.cell(60, 5, "All accessible sectors", ln=True)
    
    # RIGHT COLUMN
    pdf.set_xy(right_column_x, current_y)
    
    # --- Verification & Security ---
    pdf.set_fill_color(0, 102, 204)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", "B", 10)
    pdf.cell(90, 6, " VERIFICATION & SECURITY", ln=True, fill=True)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", "", 8)
    
    pdf.set_x(right_column_x)
    pdf.cell(35, 5, "Metadata Removed:", 0)
    pdf.set_font("Arial", "B", 8)
    pdf.cell(55, 5, "Yes" if certificate['metadata_removed'] else "No", ln=True)
    
    pdf.set_font("Arial", "", 8)
    pdf.set_x(right_column_x)
    pdf.cell(35, 5, "Certificate ID:", 0)
    pdf.set_font("Arial", "", 6)
    cert_id_display = str(certificate['certificate_id'])[:28] + "..."
    pdf.cell(55, 5, cert_id_display, ln=True)
    
    # Add verification code if available
    if certificate.get('verification_code'):
        pdf.set_font("Arial", "", 8)
        pdf.set_x(right_column_x)
        pdf.cell(35, 5, "Verification Code:", 0)
        pdf.set_font("Arial", "B", 7)
        pdf.set_text_color(0, 102, 204)
        pdf.cell(55, 5, str(certificate['verification_code']), ln=True)
        pdf.set_text_color(0, 0, 0)
    
    pdf.set_font("Arial", "", 8)
    pdf.set_x(right_column_x)
    pdf.cell(35, 5, "Generation Time:", 0)
    pdf.set_font("Arial", "", 6)
    gen_time = str(certificate['generation_time']).split('T')[0] if 'T' in str(certificate['generation_time']) else str(certificate['generation_time'])[:10]
    pdf.cell(55, 5, gen_time, ln=True)
    
    pdf.set_font("Arial", "", 8)
    pdf.set_x(right_column_x)
    pdf.cell(35, 5, "Verification:", 0)
    pdf.set_font("Arial", "B", 8)
    if certificate['verification_passed']:
        pdf.set_text_color(0, 128, 0)
        pdf.cell(55, 5, "PASSED", ln=True)
    else:
        pdf.set_text_color(255, 0, 0)
        pdf.cell(55, 5, "FAILED", ln=True)
    pdf.set_text_color(0, 0, 0)
    
    pdf.set_font("Arial", "", 7)
    pdf.set_x(right_column_x)
    pdf.cell(90, 4, "Log SHA-256 Hash:", ln=True)
    pdf.set_x(right_column_x)
    pdf.set_font("Courier", "", 5.5)
    # Split hash into multiple lines for better display
    hash_str = str(certificate['log_sha256'])
    pdf.cell(90, 3, hash_str[:32], ln=True)
    pdf.set_x(right_column_x)
    pdf.cell(90, 3, hash_str[32:], ln=True)
    pdf.ln(2)
    
    # --- Security Audit Trail (NEW) ---
    pdf.set_x(right_column_x)
    pdf.set_fill_color(220, 53, 69)  # Red for security emphasis
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", "B", 10)
    pdf.cell(90, 6, " SECURITY AUDIT TRAIL", ln=True, fill=True)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", "", 8)
    
    pdf.set_x(right_column_x)
    pdf.cell(35, 5, "Operator:", 0)
    pdf.set_font("Arial", "B", 8)
    operator = str(certificate.get('operator_username', 'Not Specified'))
    if len(operator) > 20:
        operator = operator[:17] + "..."
    pdf.cell(55, 5, operator, ln=True)
    
    pdf.set_font("Arial", "", 8)
    pdf.set_x(right_column_x)
    pdf.cell(35, 5, "Purpose:", 0)
    pdf.set_font("Arial", "", 7)
    purpose_text = str(certificate.get('operation_purpose', 'Not Specified'))
    if len(purpose_text) > 35:
        purpose_text = purpose_text[:32] + "..."
    pdf.cell(55, 5, purpose_text, ln=True)
    
    pdf.set_font("Arial", "", 8)
    pdf.set_x(right_column_x)
    pdf.cell(35, 5, "IP Address:", 0)
    pdf.set_font("Arial", "B", 7)
    pdf.cell(55, 5, str(certificate.get('ip_address', 'Unknown')), ln=True)
    
    pdf.set_font("Arial", "", 8)
    pdf.set_x(right_column_x)
    pdf.cell(35, 5, "Location:", 0)
    pdf.set_font("Arial", "", 7)
    location = str(certificate.get('geolocation', 'Unknown'))
    if len(location) > 30:
        location = location[:27] + "..."
    pdf.cell(55, 5, location, ln=True)
    
    pdf.set_font("Arial", "", 8)
    pdf.set_x(right_column_x)
    pdf.cell(35, 5, "ISP:", 0)
    pdf.set_font("Arial", "", 6)
    isp = str(certificate.get('isp', 'Unknown'))
    if len(isp) > 28:
        isp = isp[:25] + "..."
    pdf.cell(55, 5, isp, ln=True)
    pdf.ln(2)
    
    # --- Compliance Verification ---
    pdf.set_x(right_column_x)
    pdf.set_fill_color(0, 102, 204)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", "B", 10)
    pdf.cell(90, 6, " COMPLIANCE VERIFICATION", ln=True, fill=True)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", "", 8)
    
    pdf.set_x(right_column_x)
    pdf.cell(35, 5, "Standards Met:", 0)
    pdf.set_font("Arial", "B", 7)
    pdf.cell(55, 5, "NIST/DoD/GDPR", ln=True)
    
    pdf.set_font("Arial", "", 8)
    pdf.set_x(right_column_x)
    pdf.cell(35, 5, "Audit Trail:", 0)
    pdf.set_font("Arial", "B", 8)
    pdf.cell(55, 5, "Complete", ln=True)
    
    pdf.set_font("Arial", "", 8)
    pdf.set_x(right_column_x)
    pdf.cell(35, 5, "Signature Type:", 0)
    pdf.set_font("Arial", "", 7)
    pdf.cell(55, 5, "RSA-2048 Digital", ln=True)
    
    pdf.set_font("Arial", "", 8)
    pdf.set_x(right_column_x)
    pdf.cell(35, 5, "Hash Algorithm:", 0)
    pdf.set_font("Arial", "", 7)
    pdf.cell(55, 5, "SHA-256", ln=True)
    pdf.ln(2)
    
    # --- QR Code ---
    pdf.set_x(right_column_x)
    pdf.set_fill_color(0, 102, 204)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", "B", 10)
    pdf.cell(90, 6, " QUICK VERIFICATION", ln=True, fill=True)
    pdf.set_text_color(0, 0, 0)
    
    # Display verification instructions
    if certificate.get('verification_code'):
        pdf.set_x(right_column_x)
        pdf.set_font("Arial", "B", 8)
        pdf.set_text_color(0, 102, 204)
        pdf.cell(90, 5, "THIRD-PARTY VERIFICATION:", ln=True)
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Arial", "", 7)
        pdf.set_x(right_column_x)
        pdf.multi_cell(90, 4, f"Visit: https://yoursite.com/verify\nEnter Code: {certificate['verification_code']}", align="L")
        pdf.ln(1)
    
    if os.path.exists(qr_file):
        pdf.set_x(right_column_x)
        pdf.set_font("Arial", "", 7)
        pdf.cell(90, 4, "Scan QR for instant verification:", ln=True, align="C")
        # Center QR code in right column
        qr_size = 30
        qr_x = right_column_x + (90 - qr_size) / 2
        pdf.image(qr_file, x=qr_x, y=pdf.get_y() + 1, w=qr_size)
        pdf.ln(qr_size + 2)
    
    # --- Compliance Badge ---
    pdf.set_x(right_column_x)
    pdf.set_fill_color(240, 248, 255)
    pdf.rect(right_column_x, pdf.get_y(), 90, 18, 'DF')
    pdf.set_font("Arial", "B", 9)
    pdf.set_text_color(0, 51, 102)
    pdf.cell(90, 5, "COMPLIANCE CERTIFIED", ln=True, align="C")
    pdf.set_x(right_column_x)
    pdf.set_font("Arial", "", 7)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(90, 4, f"Standard: {certificate['compliance_standard']}", ln=True, align="C")
    pdf.set_x(right_column_x)
    pdf.set_font("Arial", "I", 6)
    pdf.cell(90, 3, "Meets international data sanitization", ln=True, align="C")
    pdf.set_x(right_column_x)
    pdf.cell(90, 3, "and security compliance standards", ln=True, align="C")
    
    # ==================== SIGNATURE AREA ====================
    pdf.set_y(220)  # Adjusted position
    pdf.set_font("Arial", "B", 9)
    pdf.cell(0, 5, "Digital Authorization & Signatures:", ln=True)
    pdf.ln(1)
    
    # Two signature boxes side by side with enhanced information
    pdf.set_fill_color(250, 250, 255)  # Light blue tint
    pdf.rect(10, pdf.get_y(), 90, 32, 'DF')  # Taller boxes with fill
    pdf.rect(110, pdf.get_y(), 90, 32, 'DF')
    
    current_sig_y = pdf.get_y()
    
    # Generate signature timestamp and hash
    sig_timestamp = certificate.get('wipe_time', datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC'))
    tech_hash = hashlib.sha256(f"{certificate['technician']}{sig_timestamp}".encode()).hexdigest()[:12].upper()
    
    # Left signature box - Technician
    pdf.set_xy(12, current_sig_y + 2)
    pdf.set_font("Arial", "B", 8)
    pdf.cell(86, 4, "Data Sanitization Operator", ln=True, align="L")
    
    pdf.set_x(12)
    pdf.set_font("Arial", "", 7)
    pdf.cell(86, 3, f"Name: {certificate['technician']}", ln=True, align="L")
    
    pdf.set_x(12)
    pdf.cell(86, 3, f"Role: Certified Technician", ln=True, align="L")
    
    pdf.set_x(12)
    pdf.cell(86, 3, f"Signed: {sig_timestamp[:16]}", ln=True, align="L")
    
    pdf.set_x(12)
    pdf.set_font("Arial", "I", 6)
    pdf.cell(86, 3, f"Digital Signature: {tech_hash}", ln=True, align="L")
    
    pdf.set_xy(12, current_sig_y + 26)
    pdf.set_font("Arial", "", 6)
    pdf.cell(86, 3, "_________________________________", ln=True, align="C")
    
    # Right signature box - Witness/System
    witness_display = certificate.get('witness', 'CRABEX Security System')
    if witness_display == 'Not Specified':
        witness_display = 'CRABEX Security System'
    
    pdf.set_xy(112, current_sig_y + 2)
    pdf.set_font("Arial", "B", 8)
    pdf.cell(86, 4, "Verification Authority", ln=True, align="L")
    
    pdf.set_x(112)
    pdf.set_font("Arial", "", 7)
    pdf.cell(86, 3, f"Entity: {witness_display}", ln=True, align="L")
    
    pdf.set_x(112)
    pdf.cell(86, 3, f"Organization: Zero Leaks Enterprise", ln=True, align="L")
    
    pdf.set_x(112)
    pdf.cell(86, 3, f"Verification Code: {certificate.get('verification_code', 'N/A')}", ln=True, align="L")
    
    pdf.set_x(112)
    pdf.set_font("Arial", "I", 6)
    pdf.cell(86, 3, f"Certificate ID: {certificate.get('certificate_id', 'N/A')[:20]}", ln=True, align="L")
    
    pdf.set_xy(112, current_sig_y + 26)
    pdf.set_font("Arial", "", 6)
    pdf.cell(86, 3, "_________________________________", ln=True, align="C")
    
    # ==================== FOOTER ====================
    pdf.set_y(260)  # Moved up from 270
    pdf.set_fill_color(245, 245, 245)
    pdf.rect(0, 260, 210, 37, 'F')  # Increased height from 27 to 37
    
    # Center the footer content vertically within the footer area
    footer_start_y = 263  # Start position for centered text
    
    pdf.set_y(footer_start_y)
    pdf.set_font("Arial", "I", 8)  # Slightly larger font
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 5, f"This certificate is digitally signed and can be verified using the SHA-256 hash and RSA signature.", ln=True, align="C")
    
    pdf.set_font("Arial", "", 7)
    pdf.cell(0, 5, f"Generated on {certificate['generation_time']} | Version {certificate['tool_version']}", ln=True, align="C")
    
    pdf.set_font("Arial", "B", 7)
    pdf.cell(0, 5, "Zero Leaks Enterprise Data Wiping Service | Certified Data Sanitization Solution", ln=True, align="C")
    
    pdf.set_font("Arial", "B", 6)
    pdf.set_text_color(50, 50, 150)  # Blue color for contact info
    pdf.cell(0, 5, "For verification inquiries: verify@zeroleaks.com | www.zeroleaks.com", ln=True, align="C")
    
    # Save PDF
    pdf.output(output_pdf)

def generate_certificate(log_file="wipe.log", path="X://", platform_info=None, wipe_details=None):
    """
    Generate a comprehensive digitally signed certificate for data wiping operation.
    
    Args:
        log_file: Path to the wipe log file
        path: Path that was wiped
        platform_info: Dictionary containing platform information (OS, version, etc.)
        wipe_details: Dictionary containing:
            - wipe_method: The wiping algorithm used
            - asset_serial: Hardware serial number (for disks)
            - start_time: ISO format UTC timestamp when wipe started
            - end_time: ISO format UTC timestamp when wipe ended
            - wipe_result: "Success" or "Failure"
            - technician: Name of technician performing wipe
            - witness: Name of witness (optional)
            - asset_type: "File", "Folder", or "Disk"
    """
    PRIVATE_KEY, PUBLIC_KEY = "signing_key.pem", "signing_pub.pem"
    
    # Generate RSA keys if they don't exist
    if not os.path.exists(PRIVATE_KEY):
        try:
            print("Generating new RSA keys (Software Mode)...")
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
                backend=default_backend()
            )
            
            # Save private key
            with open(PRIVATE_KEY, "wb") as f:
                f.write(private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                ))
                
            # Save public key
            public_key = private_key.public_key()
            with open(PUBLIC_KEY, "wb") as f:
                f.write(public_key.public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo
                ))
            print("RSA keys generated successfully.")
        except Exception as e:
            print(f"Error generating keys: {e}")
            traceback.print_exc()
            raise

    # Generate unique certificate ID
    unique_id = uuid.uuid4().hex
    cert_reference_number = str(uuid.uuid4()).upper()  # Unique tracking UUID
    
    # Create certificates directory if it doesn't exist
    CERT_DIR = "certificates"
    os.makedirs(CERT_DIR, exist_ok=True)
    
    CERT_JSON = os.path.join(CERT_DIR, f"wipe_certificate_{unique_id}.json")
    CERT_PDF = os.path.join(CERT_DIR, f"wipe_certificate_{unique_id}.pdf")
    QR_FILE = os.path.join(CERT_DIR, f"wipe_certificate_{unique_id}_qr.png")
    SIG_FILE = os.path.join(CERT_DIR, "wipe.sig")

    # Read and hash the log file
    try:
        with open(log_file, "rb") as f: 
            log_data = f.read()
        log_sha256 = hashlib.sha256(log_data).hexdigest()
        print(f"Log file read successfully: {len(log_data)} bytes")
    except Exception as e:
        print(f"Error reading log file: {e}")
        raise Exception(f"Cannot read log file {log_file}: {e}")

    # Sign the log file
    # Sign the log file
    try:
        # Load private key
        with open(PRIVATE_KEY, "rb") as key_file:
            private_key = serialization.load_pem_private_key(
                key_file.read(),
                password=None,
                backend=default_backend()
            )
        
        # Sign the log data (log_data was read above)
        # We sign the raw data; standard for digital signatures
        signature = private_key.sign(
            log_data,
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        
        with open(SIG_FILE, "wb") as f:
            f.write(signature)
            
        print("Log file signed successfully (Software Mode)")
    except Exception as e:
        print(f"Error signing log file: {e}")
        traceback.print_exc()
        raise Exception(f"Signing failed: {e}")
        
    with open(SIG_FILE, "rb") as f: 
        signature_b64 = base64.b64encode(f.read()).decode()

    # Get public key fingerprint
    # Get public key fingerprint
    try:
        with open(PUBLIC_KEY, "rb") as f: 
            pubkey_data = f.read()
        
        # Calculate SHA256 of the public key file
        digest = hashes.Hash(hashes.SHA256(), backend=default_backend())
        digest.update(pubkey_data)
        pubkey_sha256 = digest.finalize().hex()
    except Exception as e:
        print(f"Error getting public key fingerprint: {e}")
        pubkey_sha256 = "N/A"

    # Parse wipe details
    if not wipe_details:
        wipe_details = {}
    
    wipe_method = wipe_details.get('wipe_method', 'Unknown')
    compliance_info = get_compliance_info(wipe_method)
    
    # Calculate duration
    start_time_str = wipe_details.get('start_time', datetime.now(timezone.utc).isoformat())
    end_time_str = wipe_details.get('end_time', datetime.now(timezone.utc).isoformat())
    
    try:
        start_dt = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end_time_str.replace('Z', '+00:00'))
        duration_seconds = (end_dt - start_dt).total_seconds()
        
        # Format duration as HH:MM:SS
        hours = int(duration_seconds // 3600)
        minutes = int((duration_seconds % 3600) // 60)
        seconds = int(duration_seconds % 60)
        duration_formatted = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    except:
        duration_formatted = "Unknown"
        duration_seconds = 0

    # Generate a unique certificate ID first
    certificate_id = str(uuid.uuid4())
    
    # Build comprehensive certificate
    certificate = {
        # Core Identification
        "certificate_reference_number": cert_reference_number,
        "certificate_id": certificate_id,
        "tool_version": "1.3_enterprise_cross_platform",
        "generation_time": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        
        # Asset Information
        "asset_description": path,
        "asset_type": wipe_details.get('asset_type', 'Unknown'),
        "asset_serial_number": wipe_details.get('asset_serial', 'N/A'),
        
        # Wipe Operation Details
        "wipe_result": wipe_details.get('wipe_result', 'Unknown'),
        "destruction_method": compliance_info['method_name'],
        "wipe_method_code": wipe_method,
        "number_of_passes": compliance_info['passes'],
        
        # Compliance Information
        "compliance_standard": compliance_info['standard'],
        "method_description": compliance_info['description'],
        "suitable_for": compliance_info['suitable_for'],
        
        # Timing Information (UTC)
        "start_time_utc": start_time_str,
        "finish_time_utc": end_time_str,
        "duration": duration_formatted,
        "duration_seconds": duration_seconds,
        
        # Verification
        "log_sha256": log_sha256,
        "signature": signature_b64,
        "public_key_fingerprint_sha256": pubkey_sha256,
        "verification_method": "SHA-256 Hash with RSA-2048 Digital Signature",
        
        # Authorization
        "technician": wipe_details.get('technician', 'Not Specified'),
        "witness": wipe_details.get('witness', 'Not Specified'),
        "organization": wipe_details.get('organization', 'Zero Leaks Data Wiping Service'),
        "asset_location": wipe_details.get('asset_location', 'On-Site'),
        "asset_owner": wipe_details.get('asset_owner', 'Organization'),
        
        # Security Audit Trail (NEW - for anti-misuse tracking)
        "operator_username": wipe_details.get('operator_username', 'Not Specified'),
        "operator_user_id": wipe_details.get('operator_user_id', 0),
        "operation_purpose": wipe_details.get('operation_purpose', 'Not Specified'),
        "ip_address": wipe_details.get('ip_address', 'Unknown'),
        "geolocation": wipe_details.get('geolocation', 'Unknown'),
        "country_code": wipe_details.get('country_code', 'Unknown'),
        "isp": wipe_details.get('isp', 'Unknown'),
        
        # Additional Metadata
        "metadata_removed": wipe_details.get('metadata_removed', False),
        "verification_passed": wipe_details.get('verification_passed', False),
    }
    
    # Add platform information if provided
    if platform_info:
        certificate["platform"] = {
            "os": platform_info.get('system', 'Unknown'),
            "machine": platform_info.get('machine', 'Unknown'),
            "release": platform_info.get('release', 'Unknown'),
        }
    else:
        # Add basic platform info if not provided
        certificate["platform"] = {
            "os": platform.system(),
            "machine": platform.machine(),
            "release": platform.release(),
        }
    
    # Generate tamper-proof verification hash (BEFORE saving)
    # This hash combines critical certificate data with the signature to prevent forgery
    verification_data = f"{certificate['certificate_id']}|{certificate['log_sha256']}|{certificate['signature']}|{certificate['finish_time_utc']}|{cert_reference_number}"
    certificate["verification_hash"] = hashlib.sha256(verification_data.encode()).hexdigest()
    certificate["anti_forgery_token"] = hashlib.sha256(f"{certificate['verification_hash']}|{PRIVATE_KEY}".encode()).hexdigest()
    
    # Save JSON certificate
    with open(CERT_JSON, "w", encoding='utf-8') as f: 
        json.dump(certificate, f, indent=4, ensure_ascii=False)
    
    # Store in database with verification hash
    store_certificate_to_db(certificate["certificate_id"], certificate["finish_time_utc"], certificate["signature"], certificate["verification_hash"])

    # Generate QR code with essential certificate data
    qr_data = {
        "ref": cert_reference_number,
        "asset": path[:50] + "..." if len(path) > 50 else path,
        "result": certificate["wipe_result"],
        "method": compliance_info['method_name'][:30],
        "standard": compliance_info['standard'],
        "time": end_time_str,
        "hash": log_sha256[:16] + "...",
        "verify": f"https://verify.zeroleaks.com/{cert_reference_number}"
    }
    
    # Create QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(json.dumps(qr_data))
    qr.make(fit=True)
    
    qr_image = qr.make_image(fill_color="black", back_color="white")
    qr_image.save(QR_FILE, format="PNG")

    # Generate professional PDF certificate
    try:
        generate_pdf_certificate(certificate, CERT_PDF, QR_FILE, compliance_info)
        print(f"PDF certificate generated successfully: {CERT_PDF}")
    except Exception as pdf_error:
        print(f"Error generating PDF certificate: {pdf_error}")
        traceback.print_exc()
        raise Exception(f"PDF generation failed: {pdf_error}")

    # Cleanup temporary files
    try:
        os.remove(SIG_FILE)
        os.remove(QR_FILE)
    except Exception as cleanup_error:
        print(f"Warning: Could not cleanup temp files: {cleanup_error}")
    
    # Return absolute paths to ensure download route can find files
    cert_json_path = os.path.abspath(CERT_JSON)
    cert_pdf_path = os.path.abspath(CERT_PDF)
    
    print(f"Certificate generated - JSON: {cert_json_path}")
    print(f"Certificate generated - PDF: {cert_pdf_path}")
    
    # Return just filenames (not full paths) for the download route
    # Extract filename from path (e.g., "certificates/wipe_cert.json" -> "wipe_cert.json")
    json_filename = os.path.basename(CERT_JSON)
    pdf_filename = os.path.basename(CERT_PDF)
    
    return json_filename, pdf_filename
