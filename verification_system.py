"""
Third-Party Verification System
Allows independent verification of data wiping certificates
"""

import sqlite3
import hashlib
import json
from datetime import datetime

# Initialize verification database
def init_verification_db():
    """Create verification database for storing certificate hashes"""
    conn = sqlite3.connect('verification.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS verified_certificates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            certificate_id TEXT UNIQUE NOT NULL,
            certificate_hash TEXT NOT NULL,
            verification_code TEXT UNIQUE NOT NULL,
            issue_date TEXT NOT NULL,
            technician TEXT,
            asset_path TEXT,
            wipe_method TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            verification_count INTEGER DEFAULT 0,
            last_verified TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS verification_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            certificate_id TEXT NOT NULL,
            verification_code TEXT NOT NULL,
            verifier_ip TEXT,
            verifier_location TEXT,
            verification_time TEXT DEFAULT CURRENT_TIMESTAMP,
            verification_result TEXT
        )
    ''')
    
    conn.commit()
    conn.close()


def generate_verification_code(certificate_id, certificate_data):
    """
    Generate a unique verification code for a certificate
    Format: VERIFY-XXXX-XXXX-XXXX
    """
    # Create hash from certificate data
    hash_input = f"{certificate_id}{certificate_data}{datetime.now().isoformat()}"
    hash_obj = hashlib.sha256(hash_input.encode())
    hash_hex = hash_obj.hexdigest()[:12]
    
    # Format as verification code
    code_parts = [hash_hex[i:i+4].upper() for i in range(0, 12, 4)]
    verification_code = f"VERIFY-{'-'.join(code_parts)}"
    
    return verification_code


def register_certificate_for_verification(cert_data):
    """
    Register a certificate in the verification database
    Returns verification code
    """
    try:
        init_verification_db()
        conn = sqlite3.connect('verification.db')
        cursor = conn.cursor()
        
        certificate_id = cert_data.get('certificate_id', '')
        
        # Generate certificate hash for integrity check
        cert_json = json.dumps(cert_data, sort_keys=True)
        cert_hash = hashlib.sha256(cert_json.encode()).hexdigest()
        
        # Generate verification code
        verification_code = generate_verification_code(certificate_id, cert_json)
        
        # Store in database
        cursor.execute('''
            INSERT OR REPLACE INTO verified_certificates 
            (certificate_id, certificate_hash, verification_code, issue_date, 
             technician, asset_path, wipe_method)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            certificate_id,
            cert_hash,
            verification_code,
            cert_data.get('timestamp', datetime.now().isoformat()),
            cert_data.get('technician', 'Unknown'),
            cert_data.get('asset', {}).get('path', 'Unknown'),
            cert_data.get('wipe_details', {}).get('method', 'Unknown')
        ))
        
        conn.commit()
        conn.close()
        
        return verification_code
        
    except Exception as e:
        print(f"Error registering certificate: {e}")
        return None


def verify_certificate_by_code(verification_code):
    """
    Verify a certificate using its verification code
    Returns verification result dictionary
    """
    try:
        conn = sqlite3.connect('verification.db')
        cursor = conn.cursor()
        
        # Look up certificate
        cursor.execute('''
            SELECT certificate_id, certificate_hash, issue_date, technician, 
                   asset_path, wipe_method, verification_count
            FROM verified_certificates
            WHERE verification_code = ?
        ''', (verification_code,))
        
        result = cursor.fetchone()
        
        if not result:
            conn.close()
            return {
                'valid': False,
                'message': 'Invalid verification code. Certificate not found in verification database.',
                'status': 'NOT_FOUND'
            }
        
        cert_id, cert_hash, issue_date, technician, asset_path, wipe_method, ver_count = result
        
        # Update verification count
        cursor.execute('''
            UPDATE verified_certificates 
            SET verification_count = verification_count + 1,
                last_verified = ?
            WHERE verification_code = ?
        ''', (datetime.now().isoformat(), verification_code))
        
        conn.commit()
        conn.close()
        
        return {
            'valid': True,
            'message': 'Certificate is authentic and verified.',
            'status': 'VERIFIED',
            'certificate_details': {
                'certificate_id': cert_id,
                'issue_date': issue_date,
                'technician': technician,
                'asset_path': asset_path,
                'wipe_method': wipe_method,
                'verification_count': ver_count + 1
            }
        }
        
    except Exception as e:
        return {
            'valid': False,
            'message': f'Verification error: {str(e)}',
            'status': 'ERROR'
        }


def verify_certificate_by_id(certificate_id):
    """
    Verify a certificate using its ID
    """
    try:
        conn = sqlite3.connect('verification.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT certificate_hash, verification_code, issue_date, technician, 
                   asset_path, wipe_method, verification_count
            FROM verified_certificates
            WHERE certificate_id = ?
        ''', (certificate_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return {
                'valid': False,
                'message': 'Certificate ID not found in verification database.',
                'status': 'NOT_FOUND'
            }
        
        cert_hash, ver_code, issue_date, technician, asset_path, wipe_method, ver_count = result
        
        return {
            'valid': True,
            'message': 'Certificate found and verified.',
            'status': 'VERIFIED',
            'verification_code': ver_code,
            'certificate_details': {
                'certificate_id': certificate_id,
                'issue_date': issue_date,
                'technician': technician,
                'asset_path': asset_path,
                'wipe_method': wipe_method,
                'verification_count': ver_count
            }
        }
        
    except Exception as e:
        return {
            'valid': False,
            'message': f'Verification error: {str(e)}',
            'status': 'ERROR'
        }


def log_verification_attempt(cert_id, ver_code, ip, location, result):
    """Log a verification attempt for audit purposes"""
    try:
        conn = sqlite3.connect('verification.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO verification_logs 
            (certificate_id, verification_code, verifier_ip, verifier_location, verification_result)
            VALUES (?, ?, ?, ?, ?)
        ''', (cert_id, ver_code, ip, location, result))
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        print(f"Error logging verification: {e}")


def get_verification_statistics():
    """Get overall verification statistics"""
    try:
        conn = sqlite3.connect('verification.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM verified_certificates')
        total_certs = cursor.fetchone()[0]
        
        cursor.execute('SELECT SUM(verification_count) FROM verified_certificates')
        total_verifications = cursor.fetchone()[0] or 0
        
        cursor.execute('''
            SELECT COUNT(*) FROM verification_logs 
            WHERE verification_time > datetime('now', '-30 days')
        ''')
        recent_verifications = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'total_certificates': total_certs,
            'total_verifications': total_verifications,
            'recent_verifications_30d': recent_verifications
        }
        
    except Exception as e:
        return {
            'error': str(e)
        }


# Initialize database on module load
init_verification_db()
