"""
Security Utilities Module
Comprehensive security features to prevent misuse of the data wiping application
"""

import sqlite3
import hashlib
import uuid
import platform
import socket
import requests
import re
from datetime import datetime, timedelta
from functools import wraps
from flask import session, request, jsonify, redirect, url_for

# ==================== GEOLOCATION & IP TRACKING ====================

def get_client_ip():
    """Get the real client IP address, considering proxies"""
    if request.headers.get('X-Forwarded-For'):
        ip = request.headers.get('X-Forwarded-For').split(',')[0].strip()
    elif request.headers.get('X-Real-IP'):
        ip = request.headers.get('X-Real-IP')
    else:
        ip = request.remote_addr
    return ip

def get_geolocation(ip_address):
    """Get geolocation information from IP address"""
    try:
        # If localhost/private IP, get real external IP first
        if ip_address in ['127.0.0.1', 'localhost', '::1'] or ip_address.startswith('192.168.') or ip_address.startswith('10.'):
            try:
                # Get real external IP
                ext_ip_response = requests.get('https://api.ipify.org?format=json', timeout=3)
                if ext_ip_response.status_code == 200:
                    ip_address = ext_ip_response.json().get('ip', ip_address)
                    print(f"🌐 Detected external IP: {ip_address}")
            except:
                print("⚠️ Could not detect external IP, using localhost")
        
        # Using free ip-api.com service (limit: 45 req/min)
        response = requests.get(f'http://ip-api.com/json/{ip_address}', timeout=3)
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success':
                geo_data = {
                    'country': data.get('country', 'Unknown'),
                    'country_code': data.get('countryCode', 'Unknown'),
                    'region': data.get('regionName', 'Unknown'),
                    'city': data.get('city', 'Unknown'),
                    'latitude': data.get('lat', 0),
                    'longitude': data.get('lon', 0),
                    'isp': data.get('isp', 'Unknown'),
                    'timezone': data.get('timezone', 'Unknown'),
                    'real_ip': ip_address  # Store the actual IP used for geolocation
                }
                print(f"✅ Geolocation: {geo_data['city']}, {geo_data['region']}, {geo_data['country']}")
                return geo_data
    except Exception as e:
        print(f"❌ Geolocation error: {e}")
    
    return {
        'country': 'Unknown',
        'country_code': 'Unknown',
        'region': 'Unknown',
        'city': 'Unknown',
        'latitude': 0,
        'longitude': 0,
        'isp': 'Unknown',
        'timezone': 'Unknown',
        'real_ip': ip_address
    }

def is_vpn_or_proxy(ip_address):
    """Detect if user is using VPN or proxy (basic check)"""
    try:
        # Check common VPN/proxy indicators
        geo = get_geolocation(ip_address)
        isp = geo.get('isp', '').lower()
        
        vpn_keywords = ['vpn', 'proxy', 'tunnel', 'tor', 'anonymizer', 'hide', 'privacy']
        for keyword in vpn_keywords:
            if keyword in isp:
                return True
        
        # Check against known VPN IP ranges (basic)
        # In production, use a proper VPN detection service
        return False
    except:
        return False

# ==================== HARDWARE FINGERPRINTING ====================

def get_hardware_id():
    """Generate unique hardware identifier"""
    try:
        # MAC address
        mac = ':'.join(re.findall('..', '%012x' % uuid.getnode()))
        
        # System info
        system_info = f"{platform.system()}_{platform.machine()}_{platform.processor()}"
        
        # Hostname
        hostname = socket.gethostname()
        
        # Combine and hash
        hardware_string = f"{mac}_{system_info}_{hostname}"
        hardware_id = hashlib.sha256(hardware_string.encode()).hexdigest()
        
        return hardware_id
    except:
        return "UNKNOWN"

def get_system_fingerprint():
    """Get detailed system information for logging"""
    return {
        'os': platform.system(),
        'os_version': platform.version(),
        'architecture': platform.machine(),
        'processor': platform.processor(),
        'hostname': socket.gethostname(),
        'hardware_id': get_hardware_id()
    }

# ==================== AUDIT LOGGING ====================

def log_audit_event(user_id, username, operation_type, purpose=None, **kwargs):
    """
    Comprehensive audit logging for all operations
    
    Args:
        user_id: User ID
        username: Username
        operation_type: Type of operation (wipe, verify, etc.)
        purpose: User-provided reason for the operation (optional, defaults to None)
        **kwargs: Additional information (device_path, wipe_method, etc.)
    """
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        
        # Gather all tracking information
        ip_address = get_client_ip()
        user_agent = request.headers.get('User-Agent', 'Unknown')
        geo_info = get_geolocation(ip_address)
        hardware_info = get_system_fingerprint()
        
        # Use the real IP from geolocation if available (handles localhost)
        real_ip = geo_info.get('real_ip', ip_address)
        
        timestamp = datetime.now().isoformat()
        
        cursor.execute('''
            INSERT INTO audit_logs (
                user_id, username, operation_type, device_path, wipe_method,
                purpose, ip_address, user_agent, geolocation, country_code,
                timestamp, certificate_id, hardware_info, success
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_id,
            username,
            operation_type,
            kwargs.get('device_path', 'N/A'),
            kwargs.get('wipe_method', 'N/A'),
            purpose or 'N/A',
            real_ip,  # Log the REAL external IP, not localhost
            user_agent,
            f"{geo_info['city']}, {geo_info['region']}, {geo_info['country']}",
            geo_info['country_code'],
            timestamp,
            kwargs.get('certificate_id', 'N/A'),
            str(hardware_info),
            kwargs.get('success', 1)
        ))
        
        conn.commit()
        conn.close()
        
        # Check for suspicious activity
        check_suspicious_activity(user_id, operation_type, ip_address, geo_info)
        
        return True
    except Exception as e:
        print(f"Audit logging error: {e}")
        return False

# ==================== RATE LIMITING ====================

def check_rate_limit(user_id):
    """
    Check if user has exceeded rate limits
    Returns: (allowed: bool, remaining: int, reset_time: str)
    """
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        
        # Get user's daily limit
        cursor.execute('SELECT daily_wipe_limit, is_verified FROM users WHERE id = ?', (user_id,))
        result = cursor.fetchone()
        if not result:
            conn.close()
            return False, 0, None
        
        daily_limit, is_verified = result
        
        # Get today's usage
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute('''
            SELECT wipe_count, last_wipe_time FROM rate_limits 
            WHERE user_id = ? AND date = ?
        ''', (user_id, today))
        
        rate_limit = cursor.fetchone()
        
        if rate_limit:
            wipe_count, last_wipe_time = rate_limit
            
            # Check cooldown period (15 minutes between wipes)
            if last_wipe_time:
                last_wipe = datetime.fromisoformat(last_wipe_time)
                cooldown_minutes = 15
                time_since_last = datetime.now() - last_wipe
                
                if time_since_last.total_seconds() < cooldown_minutes * 60:
                    remaining_cooldown = cooldown_minutes * 60 - time_since_last.total_seconds()
                    reset_time = (datetime.now() + timedelta(seconds=remaining_cooldown)).strftime('%H:%M:%S')
                    conn.close()
                    return False, 0, f"Cooldown active. Wait until {reset_time}"
            
            if wipe_count >= daily_limit:
                conn.close()
                tomorrow = (datetime.now() + timedelta(days=1)).replace(hour=0, minute=0, second=0)
                return False, 0, tomorrow.strftime('%Y-%m-%d %H:%M:%S')
            
            remaining = daily_limit - wipe_count
        else:
            remaining = daily_limit
        
        conn.close()
        return True, remaining, None
        
    except Exception as e:
        print(f"Rate limit check error: {e}")
        return False, 0, None

def increment_rate_limit(user_id):
    """Increment the rate limit counter after a successful wipe"""
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        
        today = datetime.now().strftime('%Y-%m-%d')
        now = datetime.now().isoformat()
        
        cursor.execute('''
            INSERT INTO rate_limits (user_id, date, wipe_count, last_wipe_time)
            VALUES (?, ?, 1, ?)
            ON CONFLICT(user_id, date) DO UPDATE SET
                wipe_count = wipe_count + 1,
                last_wipe_time = ?
        ''', (user_id, today, now, now))
        
        # Update total wipes
        cursor.execute('UPDATE users SET total_wipes = total_wipes + 1 WHERE id = ?', (user_id,))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Rate limit increment error: {e}")
        return False

# ==================== SUSPICIOUS ACTIVITY DETECTION ====================

def check_suspicious_activity(user_id, operation_type, ip_address, geo_info):
    """Detect and flag suspicious activity patterns"""
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        
        flags = []
        
        # Check 1: High frequency usage (more than 5 wipes in 24 hours)
        cursor.execute('''
            SELECT COUNT(*) FROM audit_logs 
            WHERE user_id = ? AND timestamp > datetime('now', '-24 hours')
        ''', (user_id,))
        recent_count = cursor.fetchone()[0]
        
        if recent_count > 5:
            flags.append({
                'type': 'high_frequency',
                'severity': 'high',
                'description': f'User performed {recent_count} wipes in last 24 hours'
            })
        
        # Check 2: Multiple IP addresses or locations
        cursor.execute('''
            SELECT COUNT(DISTINCT ip_address), COUNT(DISTINCT country_code) 
            FROM audit_logs 
            WHERE user_id = ? AND timestamp > datetime('now', '-7 days')
        ''', (user_id,))
        ip_count, country_count = cursor.fetchone()
        
        if ip_count > 5:
            flags.append({
                'type': 'multiple_ips',
                'severity': 'medium',
                'description': f'User accessed from {ip_count} different IPs in last week'
            })
        
        if country_count > 2:
            flags.append({
                'type': 'multiple_countries',
                'severity': 'high',
                'description': f'User accessed from {country_count} different countries'
            })
        
        # Check 3: VPN/Proxy usage
        if is_vpn_or_proxy(ip_address):
            flags.append({
                'type': 'vpn_usage',
                'severity': 'medium',
                'description': f'User accessing via VPN/Proxy from {geo_info["country"]}'
            })
        
        # Check 4: Unusual time (2 AM - 5 AM)
        current_hour = datetime.now().hour
        if 2 <= current_hour <= 5:
            flags.append({
                'type': 'unusual_time',
                'severity': 'low',
                'description': f'Operation at unusual hour: {current_hour}:00'
            })
        
        # Log suspicious activities
        for flag in flags:
            cursor.execute('''
                INSERT INTO suspicious_activity (
                    user_id, activity_type, severity, description, ip_address
                ) VALUES (?, ?, ?, ?, ?)
            ''', (user_id, flag['type'], flag['severity'], flag['description'], ip_address))
        
        conn.commit()
        conn.close()
        
        # Auto-suspend account if high severity flags
        high_severity_count = sum(1 for f in flags if f['severity'] == 'high')
        if high_severity_count >= 2:
            suspend_account(user_id, "Automatic suspension due to suspicious activity")
        
        return flags
        
    except Exception as e:
        print(f"Suspicious activity check error: {e}")
        return []

def flag_suspicious_purpose(user_id, device_path, purpose, ip_address, geo_info):
    """
    NEW: Flag potentially criminal purposes for admin review
    This is a KEY anti-misuse feature that alerts when suspicious keywords are detected
    """
    try:
        suspicious_keywords = [
            'evidence', 'hide', 'cover', 'legal', 'investigation', 
            'court', 'police', 'case', 'destroy', 'lawsuit', 'attorney',
            'subpoena', 'warrant', 'forensic', 'incriminate'
        ]
        
        purpose_lower = purpose.lower()
        found_keywords = [kw for kw in suspicious_keywords if kw in purpose_lower]
        
        if found_keywords:
            conn = sqlite3.connect('users.db')
            cursor = conn.cursor()
            
            # Log as high severity suspicious activity
            description = f'SUSPICIOUS PURPOSE DETECTED: Keywords: {", ".join(found_keywords)} | Device: {device_path} | Purpose: "{purpose[:100]}"'
            
            cursor.execute('''
                INSERT INTO suspicious_activity (
                    user_id, activity_type, severity, description, ip_address
                ) VALUES (?, ?, ?, ?, ?)
            ''', (user_id, 'suspicious_purpose', 'high', description, ip_address))
            
            conn.commit()
            conn.close()
            
            # Print alert for admin monitoring
            print(f"""
╔═══════════════════════════════════════════════════════════════╗
║                 🚨 SECURITY ALERT - SUSPICIOUS PURPOSE 🚨      ║
╠═══════════════════════════════════════════════════════════════╣
║ User ID: {user_id}                                             
║ Keywords: {', '.join(found_keywords)}                          
║ Device: {device_path}                                          
║ Purpose: {purpose[:60]}...                                     
║ IP: {ip_address}                                               
║ Location: {geo_info['city']}, {geo_info['country']}           
║                                                                 
║ ⚠️  This operation has been FLAGGED for review                
║ ⚠️  All details logged to suspicious_activity table           
╚═══════════════════════════════════════════════════════════════╝
            """)
            
            return True, found_keywords
        
        return False, []
        
    except Exception as e:
        print(f"Suspicious purpose flagging error: {e}")
        return False, []

def suspend_account(user_id, reason):
    """Suspend a user account"""
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET account_status = ? WHERE id = ?', ('suspended', user_id))
        conn.commit()
        conn.close()
        print(f"Account {user_id} suspended: {reason}")
    except Exception as e:
        print(f"Account suspension error: {e}")

# ==================== LICENSE MANAGEMENT ====================

def generate_license_key():
    """Generate a unique license key"""
    return str(uuid.uuid4()).upper()

def validate_license(user_id):
    """
    Validate user's license
    Returns: (valid: bool, message: str, license_info: dict)
    """
    conn = None
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT license_key, license_type, expiry_date, is_active, max_wipes_per_day, hardware_id
            FROM licenses
            WHERE user_id = ? AND is_active = 1
            ORDER BY expiry_date DESC
            LIMIT 1
        ''', (user_id,))
        
        license_data = cursor.fetchone()
        
        if not license_data:
            return False, "No active license found. Please activate a license.", None
        
        license_key, license_type, expiry_date, is_active, max_wipes, stored_hardware = license_data
        
        # Check expiry
        if expiry_date:
            try:
                expiry = datetime.fromisoformat(expiry_date)
                if datetime.now() > expiry:
                    return False, "License expired. Please renew.", None
            except:
                pass  # Invalid date format, skip expiry check
        
        # Check hardware binding
        if stored_hardware:
            current_hardware_id = get_hardware_id()
            if stored_hardware != current_hardware_id:
                return False, "License is bound to different hardware.", None
        
        license_info = {
            'type': license_type,
            'expiry': expiry_date,
            'max_wipes': max_wipes
        }
        
        return True, "License valid", license_info
        
    except Exception as e:
        print(f"License validation error: {e}")
        return False, f"License validation error: {str(e)}", None
    finally:
        if conn:
            conn.close()

def activate_license(user_id, license_key):
    """Activate a license for a user"""
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        
        # Verify license key exists and is not already activated
        cursor.execute('SELECT id, user_id, is_active FROM licenses WHERE license_key = ?', (license_key,))
        license_data = cursor.fetchone()
        
        if not license_data:
            conn.close()
            return False, "Invalid license key"
        
        if license_data[2] == 1:  # is_active
            conn.close()
            return False, "License already activated"
        
        # Bind to hardware and activate
        hardware_id = get_hardware_id()
        activation_date = datetime.now().isoformat()
        
        cursor.execute('''
            UPDATE licenses 
            SET user_id = ?, hardware_id = ?, activation_date = ?, is_active = 1
            WHERE license_key = ?
        ''', (user_id, hardware_id, activation_date, license_key))
        
        conn.commit()
        conn.close()
        
        return True, "License activated successfully"
        
    except Exception as e:
        print(f"License activation error: {e}")
        return False, str(e)

def remote_kill_switch(user_id=None, license_key=None, reason="Administrative action"):
    """
    Remote kill switch to deactivate licenses
    Can target specific user or license key
    """
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        
        if user_id:
            cursor.execute('UPDATE licenses SET is_active = 0 WHERE user_id = ?', (user_id,))
            cursor.execute('UPDATE users SET account_status = ? WHERE id = ?', ('deactivated', user_id))
            cursor.execute('''
                INSERT INTO kill_switch_log (user_id, reason, deactivated_by)
                VALUES (?, ?, ?)
            ''', (user_id, reason, 'SYSTEM'))
        elif license_key:
            cursor.execute('UPDATE licenses SET is_active = 0 WHERE license_key = ?', (license_key,))
            cursor.execute('''
                INSERT INTO kill_switch_log (license_key, reason, deactivated_by)
                VALUES (?, ?, ?)
            ''', (license_key, reason, 'SYSTEM'))
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        print(f"Kill switch error: {e}")
        return False

# ==================== DECORATOR FOR ROUTE PROTECTION ====================

def require_license(f):
    """Decorator to require valid license for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        
        valid, message, license_info = validate_license(session['user_id'])
        if not valid:
            return jsonify({
                'success': False,
                'message': f'License validation failed: {message}'
            }), 403
        
        return f(*args, **kwargs)
    return decorated_function

def require_rate_limit(f):
    """Decorator to enforce rate limits"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        
        allowed, remaining, reset_time = check_rate_limit(session['user_id'])
        if not allowed:
            return jsonify({
                'success': False,
                'message': f'Rate limit exceeded. Reset time: {reset_time}',
                'remaining': 0
            }), 429
        
        return f(*args, **kwargs)
    return decorated_function

def require_tos_acceptance(f):
    """Decorator to require Terms of Service acceptance"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id FROM tos_acceptance 
            WHERE user_id = ? AND tos_version = ?
        ''', (session['user_id'], 'v1.0'))
        
        has_accepted = cursor.fetchone()
        conn.close()
        
        if not has_accepted:
            return jsonify({
                'success': False,
                'message': 'You must accept the Terms of Service before using this feature',
                'redirect': '/tos'
            }), 403
        
        return f(*args, **kwargs)
    return decorated_function

# ==================== VERIFICATION UTILITIES ====================

def submit_verification_document(user_id, verification_type, document_path):
    """Submit verification documents for review"""
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO user_verification (user_id, verification_type, document_path)
            VALUES (?, ?, ?)
        ''', (user_id, verification_type, document_path))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Verification submission error: {e}")
        return False

def get_user_statistics(user_id):
    """Get comprehensive user statistics"""
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        
        # Basic user info
        cursor.execute('''
            SELECT username, is_verified, verification_level, account_status, 
                   daily_wipe_limit, total_wipes, created_at
            FROM users WHERE id = ?
        ''', (user_id,))
        user_info = cursor.fetchone()
        
        # Today's usage
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute('''
            SELECT wipe_count FROM rate_limits 
            WHERE user_id = ? AND date = ?
        ''', (user_id, today))
        today_usage = cursor.fetchone()
        today_wipes = today_usage[0] if today_usage else 0
        
        # Suspicious activity count
        cursor.execute('''
            SELECT COUNT(*) FROM suspicious_activity 
            WHERE user_id = ? AND resolved = 0
        ''', (user_id,))
        suspicious_count = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'username': user_info[0],
            'is_verified': bool(user_info[1]),
            'verification_level': user_info[2],
            'account_status': user_info[3],
            'daily_limit': user_info[4],
            'total_wipes': user_info[5],
            'today_wipes': today_wipes,
            'remaining_today': user_info[4] - today_wipes,
            'suspicious_flags': suspicious_count,
            'member_since': user_info[6]
        }
        
    except Exception as e:
        print(f"Statistics error: {e}")
        return None
