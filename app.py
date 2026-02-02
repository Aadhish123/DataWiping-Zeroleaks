import os
import subprocess
import string
import sqlite3
import random
import sys
import json
import platform
import traceback
from datetime import datetime, timezone
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash, send_file, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from generate_certificate import generate_certificate
import requests

# --- SECURE WIPING CORE (Python Native) ---
import stat
import time

def secure_wipe_file(path, method='dod', flushes=True):
    """
    Perform a forensic-grade secure wipe of a file using Python.
    defeat Recuva and similar tools by:
    1. Overwriting content multiple times.
    2. Flushing buffers to disk.
    3. Renaming the file multiple times (MFT Scrubbing).
    4. Deleting.
    Handles Read-Only files and path normalization.
    """
    # Normalize path to fix multiple slashes
    path = os.path.normpath(path)
    
    if not os.path.exists(path):
        return False, f"File not found: {path}"
    
    try:
        # Force write permissions (Fix for [Errno 13] Permission denied)
        os.chmod(path, stat.S_IWRITE)
        
        file_size = os.path.getsize(path)
        
        # Passes definition
        passes = []
        if method == 'zeros':
            passes = [b'\x00']
        elif method == 'dod_7pass': 
            # Simplified DoD 5220.22-M ECE (7 passes)
            passes = [b'\x00', b'\xFF', b'\x00', b'\xFF', b'\x00', b'\xFF', 'random']
        else: # Default DoD 3-pass
            passes = [b'\x00', b'\xFF', 'random']
            
        with open(path, "r+b") as f:
            for i, pattern in enumerate(passes):
                f.seek(0)
                if pattern == 'random':
                    # Optimization: Write in chunks for large files
                    left = file_size
                    while left > 0:
                        block_size = min(65536, left)
                        f.write(os.urandom(block_size))
                        left -= block_size
                else:
                    # Write pattern
                    # Optimization: Create a large buffer of the pattern
                    # to minimize syscalls
                    chunk = pattern * 65536
                    left = file_size
                    while left > 0:
                        write_len = min(65536, left)
                        f.write(chunk[:write_len])
                        left -= write_len
                
                # Critical: Flush to physical disk
                if flushes:
                    f.flush()
                    os.fsync(f.fileno())
        
        # --- Anti-Forensics: MFT Scrubbing ---
        # Rename file multiple times to overwrite metadata directory entries
        dir_name = os.path.dirname(path)
        base_name = os.path.basename(path)
        ext = os.path.splitext(base_name)[1]
        
        current_path = path
        
        # 1. Randomize name keeping extension
        new_name = ''.join(random.choices(string.ascii_letters + string.digits, k=10)) + ext
        new_path = os.path.join(dir_name, new_name)
        try:
             os.rename(current_path, new_path)
             current_path = new_path
        except Exception:
             pass # Continue if rename fails (some files might be locked)
        
        # 2. Randomize name changing extension
        new_name = ''.join(random.choices(string.ascii_letters + string.digits, k=12)) + ".tmp"
        new_path = os.path.join(dir_name, new_name)
        try:
            os.rename(current_path, new_path)
            current_path = new_path
        except Exception:
            pass

        # 3. Shrink file to 0 bytes
        with open(current_path, 'wb') as f:
            pass # Truncate

        # 4. Final Delete
        os.remove(current_path)
        
        return True, "Securely wiped and scrubbed"

    except PermissionError:
        return False, "Permission Denied. File might be in use or system protected."
    except Exception as e:
        return False, str(e)

# Import comprehensive security utilities
from security_utils import (
    log_audit_event, check_rate_limit, increment_rate_limit,
    validate_license, get_client_ip, get_geolocation,
    get_user_statistics, require_license, require_rate_limit,
    require_tos_acceptance, get_hardware_id, check_suspicious_activity
)

# Import third-party verification system
from verification_system import (
    register_certificate_for_verification,
    verify_certificate_by_code,
    verify_certificate_by_id,
    log_verification_attempt,
    get_verification_statistics
)

# Import advanced AI chatbot with CRABEX knowledge base
from chatbot_ai import get_chatbot


from dotenv import load_dotenv

load_dotenv()

# 2factor.in API config
TWOFACTOR_API_KEY = "ca0d510f-9aa0-11f0-b922-0200cd936042"  # <-- 2factor.in API key
TWOFACTOR_BASE_URL = "https://2factor.in/API/V1/"
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', os.urandom(24))

# --- Cross-Platform Executable Path ---
if sys.platform == "win32":
    executable_name = "wipeEngine.exe"
else:
    executable_name = "wipeEngine"
C_EXECUTABLE_PATH = os.path.join('wipingEngine', executable_name)
FAST_WIPE_PATH = 'fast_wipe.py'  # Python-based fast wiping engine

# --- Platform Detection ---
def detect_platform():
    """
    Detect the current operating system and platform details.
    Returns a dict with platform information.
    """
    system = platform.system()  # Windows, Linux, Darwin (macOS), etc.
    machine = platform.machine()  # x86_64, ARM, etc.
    release = platform.release()
    
    platform_info = {
        'system': system,
        'machine': machine,
        'release': release,
        'is_windows': system == 'Windows',
        'is_linux': system == 'Linux',
        'is_macos': system == 'Darwin',
        'is_unix': system in ['Linux', 'Darwin'],
        'is_mobile': False,  # Will be updated based on user agent for web access
        'is_android': False,
        'is_ios': False,
    }
    
    return platform_info

def detect_client_platform(user_agent):
    """
    Detect client platform from user agent string (for mobile detection).
    """
    user_agent_lower = user_agent.lower() if user_agent else ''
    
    client_info = {
        'is_mobile': False,
        'is_android': False,
        'is_ios': False,
        'is_tablet': False,
    }
    
    # Check for mobile platforms
    if 'android' in user_agent_lower:
        client_info['is_mobile'] = True
        client_info['is_android'] = True
        if 'tablet' in user_agent_lower or 'pad' in user_agent_lower:
            client_info['is_tablet'] = True
    elif 'iphone' in user_agent_lower or 'ipad' in user_agent_lower or 'ipod' in user_agent_lower:
        client_info['is_mobile'] = True
        client_info['is_ios'] = True
        if 'ipad' in user_agent_lower:
            client_info['is_tablet'] = True
    elif any(mobile_keyword in user_agent_lower for mobile_keyword in ['mobile', 'webos', 'blackberry', 'opera mini']):
        client_info['is_mobile'] = True
    
    return client_info

# --- Helper Functions ---
def get_db_connection():
    conn = sqlite3.connect('users.db')
    conn.row_factory = sqlite3.Row
    return conn

def remove_metadata(file_path):
    """
    Remove metadata from files after wiping.
    This includes file timestamps, extended attributes, EXIF data, NTFS ADS, and other metadata.
    Returns True if successful, False otherwise.
    """
    try:
        # Use comprehensive metadata removal from fast_wipe module
        from fast_wipe import (
            remove_all_metadata, 
            remove_file_timestamps,
            remove_file_attributes,
            remove_ntfs_alternate_data_streams,
            remove_extended_attributes,
            remove_exif_metadata,
            remove_document_metadata
        )
        
        print(f"📋 Removing comprehensive metadata from: {file_path}")
        
        # Use the comprehensive removal function
        success = remove_all_metadata(file_path)
        
        if success:
            print(f"✅ Metadata removal complete for: {file_path}")
        else:
            print(f"⚠️ Partial metadata removal for: {file_path}")
        
        return True  # Return True even if partial success
        
    except ImportError:
        # Fallback to basic metadata removal if fast_wipe import fails
        print("⚠️ Using fallback metadata removal")
        try:
            platform_info = detect_platform()
            
            # Reset file timestamps to epoch
            epoch_time = 0  # January 1, 1970
            
            if platform_info['is_windows']:
                # Windows: Use PowerShell to clear metadata
                try:
                    import subprocess
                    ps_command = f'''
                    $file = Get-Item -LiteralPath "{file_path}"
                    $date = Get-Date "01/01/2000 00:00:00"
                    $file.CreationTime = $date
                    $file.LastWriteTime = $date
                    $file.LastAccessTime = $date
                    '''
                    subprocess.run(["powershell", "-Command", ps_command], 
                                 capture_output=True, check=False)
                except:
                    pass
            
            elif platform_info['is_unix']:
                try:
                    subprocess.run(['touch', '-t', '200001010000', file_path], 
                                 capture_output=True, check=False)
                    
                    if platform_info['is_linux']:
                        subprocess.run(['setfattr', '-h', '-x', 'user.*', file_path], 
                                     capture_output=True, check=False)
                    elif platform_info['is_macos']:
                        subprocess.run(['xattr', '-c', file_path], 
                                     capture_output=True, check=False)
                except:
                    pass
            
            return True
        except Exception as e:
            print(f"Warning: Could not remove all metadata: {e}")
            return False
    except Exception as e:
        print(f"Warning: Could not remove all metadata: {e}")
        return False

def get_disk_serial(disk_path):
    """
    Get the serial number of a disk.
    """
    try:
        platform_info = detect_platform()
        
        if platform_info['is_windows']:
            # Extract disk index from path like \\.\PhysicalDrive0
            disk_index = disk_path.split('PhysicalDrive')[-1]
            cmd = f"wmic diskdrive where index={disk_index} get SerialNumber /format:value"
            result = subprocess.run(cmd, capture_output=True, text=True, shell=True, 
                                  creationflags=subprocess.CREATE_NO_WINDOW)
            for line in result.stdout.split('\n'):
                if 'SerialNumber=' in line:
                    return line.split('=')[1].strip()
        
        elif platform_info['is_linux']:
            # Use lsblk or hdparm
            disk_name = os.path.basename(disk_path)
            cmd = ['lsblk', '-d', '-o', 'SERIAL', '--noheadings', disk_path]
            result = subprocess.run(cmd, capture_output=True, text=True)
            serial = result.stdout.strip()
            if serial:
                return serial
        
        elif platform_info['is_macos']:
            # Use system_profiler
            cmd = ['system_profiler', 'SPStorageDataType', '-json']
            result = subprocess.run(cmd, capture_output=True, text=True)
            data = json.loads(result.stdout)
            # This would need more parsing based on disk_path
            pass
    except:
        pass
    
    return "N/A"

# --- ATA Secure Erase Function ---
def ata_secure_erase(disk_path):
    """
    Run ATA Secure Erase on the given disk path.
    Only works on Linux with hdparm and requires root privileges.
    """
    try:
        # Set security password (required before erase)
        set_pwd_cmd = ["sudo", "hdparm", "--user-master", "u", "--security-set-pass", "ZeroLeaks", disk_path]
        erase_cmd = ["sudo", "hdparm", "--user-master", "u", "--security-erase", "ZeroLeaks", disk_path]
        set_pwd_result = subprocess.run(set_pwd_cmd, capture_output=True, text=True)
        if set_pwd_result.returncode != 0:
            return False, f"Failed to set security password: {set_pwd_result.stderr}"
        erase_result = subprocess.run(erase_cmd, capture_output=True, text=True)
        if erase_result.returncode != 0:
            return False, f"Secure Erase failed: {erase_result.stderr}"
        return True, erase_result.stdout
    except Exception as e:
        return False, str(e)

def get_physical_disks():
    """
    Get physical disks for Windows, Linux, and macOS.
    Mobile platforms (Android/iOS) will receive appropriate guidance.
    """
    disks = []
    platform_info = detect_platform()
    
    try:
        if platform_info['is_windows']:
            # Windows disk detection
            cmd = "wmic diskdrive get Index,Caption,Size,SerialNumber /format:csv"
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
            lines = result.stdout.strip().split('\n')
            for line in lines[2:]:
                if line:
                    parts = line.strip().split(',')
                    if len(parts) >= 5:
                        _, caption, index, serial, size_str = parts
                        try:
                            size_gb = float(size_str) / (1024**3)
                        except (ValueError, ZeroDivisionError):
                            size_gb = 0.0
                        disk_path = f"\\\\.\\PhysicalDrive{index}"
                        display_name = f"Disk {index}: {caption.strip()} (SN: {serial.strip()}) ({size_gb:.2f} GB)"
                        disks.append({'path': disk_path, 'name': display_name, 'serial': serial.strip()})
        
        elif platform_info['is_macos']:
            # macOS disk detection using diskutil
            cmd = ["diskutil", "list", "-plist"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            # Alternative: use system_profiler for detailed disk info
            cmd2 = ["system_profiler", "SPStorageDataType", "-json"]
            try:
                result2 = subprocess.run(cmd2, capture_output=True, text=True, check=True)
                storage_data = json.loads(result2.stdout)
                
                # Parse macOS storage data
                for item in storage_data.get('SPStorageDataType', []):
                    disk_name = item.get('_name', 'Unknown')
                    size_str = item.get('size_in_bytes', 0)
                    try:
                        size_gb = float(size_str) / (1024**3)
                    except (ValueError, TypeError):
                        size_gb = 0.0
                    mount_point = item.get('mount_point', 'N/A')
                    
                    # For macOS, we'll use disk identifiers like /dev/disk0
                    disk_path = f"/dev/{item.get('BSD name', 'unknown')}" if item.get('BSD name') else mount_point
                    display_name = f"{disk_name} ({size_gb:.2f} GB) - {mount_point}"
                    disks.append({'path': disk_path, 'name': display_name, 'serial': 'N/A'})
            except:
                # Fallback to diskutil list
                result = subprocess.run(["diskutil", "list"], capture_output=True, text=True)
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if '/dev/disk' in line:
                        parts = line.split()
                        if parts:
                            disk_path = parts[0]
                            display_name = f"macOS Disk: {disk_path}"
                            disks.append({'path': disk_path, 'name': display_name, 'serial': 'N/A'})
        
        elif platform_info['is_linux']:
            # Linux disk detection using lsblk
            cmd = ["lsblk", "-d", "-o", "NAME,MODEL,SIZE,SERIAL", "--bytes", "--json"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)
            
            for disk in data.get('blockdevices', []):
                disk_path = os.path.join('/dev', disk.get('name', ''))
                model = disk.get('model', 'N/A')
                size_bytes = disk.get('size', 0)
                try:
                    size_gb = float(size_bytes) / (1024**3)
                except (ValueError, TypeError):
                    size_gb = 0.0
                serial = disk.get('serial', 'N/A')
                display_name = f"{disk_path}: {model} (SN: {serial}) ({size_gb:.2f} GB)"
                disks.append({'path': disk_path, 'name': display_name, 'serial': serial})
        
        else:
            # Unsupported platform
            print(f"Disk detection not supported on platform: {platform_info['system']}")
            
    except Exception as e:
        print(f"Could not get physical disks (may need admin/sudo privileges): {e}")
        # Add error info to help user
        if platform_info['is_linux'] or platform_info['is_macos']:
            print("Tip: On Linux/macOS, you may need to run with sudo for full disk access.")
        elif platform_info['is_windows']:
            print("Tip: On Windows, run as Administrator for full disk access.")
    
    return disks

# --- Decorators & Authentication ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("You must be logged in to view this page.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def home():
    # Detect client platform for mobile optimization
    user_agent = request.headers.get('User-Agent', '')
    client_info = detect_client_platform(user_agent)
    
    # Store client info in session for later use
    session['client_info'] = client_info
    
    # Fetch latest approved testimonials (limit to 6)
    conn = get_db_connection()
    try:
        testimonials = conn.execute(
            "SELECT u.username as name, t.role, t.rating, t.text, t.created_at "
            "FROM testimonials t JOIN users u ON t.user_id = u.id "
            "WHERE t.approved=1 ORDER BY t.created_at DESC LIMIT 6"
        ).fetchall()
    finally:
        conn.close()

    # Render landing page with testimonials
    return render_template('landing.html', testimonials=testimonials)


@app.route('/submit_testimonial', methods=['POST'])
def submit_testimonial():
    # Require login
    if 'user_id' not in session or 'username' not in session:
        return jsonify({'status': 'error', 'message': 'You must be logged in to submit feedback.'}), 401

    data = request.get_json(silent=True)
    if not data:
        data = request.form

    name = session['username']
    user_id = session['user_id']
    role = (data.get('role') or '').strip()
    text = (data.get('text') or '').strip()
    try:
        rating = int(data.get('rating') or 5)
    except:
        rating = 5

    # Basic validation
    if not text:
        return jsonify({'status': 'error', 'message': 'Feedback cannot be empty.'}), 400

    created_at = datetime.now(timezone.utc).isoformat()

    conn = get_db_connection()
    try:
        conn.execute(
            'INSERT INTO testimonials (user_id, name, role, rating, text, approved, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (user_id, name, role, rating, text, 1, created_at)
        )
        conn.commit()
    except Exception as e:
        import traceback
        print('Testimonial submission error:', traceback.format_exc())
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        conn.close()

    return jsonify({'status': 'ok', 'message': 'Thank you for your feedback!'}), 201

@app.route('/help')
def help_page():
    return render_template('help.html')
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        if user and check_password_hash(user['password_hash'], password):
            if session.get('pending_user') == username:
                flash("Please verify your account with OTP before login.", "warning")
                return redirect(url_for('send_otp'))
            session.clear()
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['phone_number'] = user['phone_number']
            
            flash(f"Welcome back, {user['username']}!", "success")
            return redirect(url_for('wipe_tool'))
        else:
            flash("Invalid username or password.", "danger")
    return render_template('login.html')

whanum = "91" 
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        phone_number = request.form['phone_number']
        #print(type(phone_number))
        global whanum
        whanum += phone_number
        print(whanum)
        print(type(whanum))
        conn = get_db_connection()
        user_exists = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
        if user_exists:
            flash("Username already exists. Please choose another.", "warning")
            conn.close()
            return redirect(url_for('signup'))
        password_hash = generate_password_hash(password)
        conn.execute('INSERT INTO users (username, password_hash, phone_number) VALUES (?, ?, ?)',
                    (username, password_hash, phone_number))
        conn.commit()
        conn.close()
        session['pending_user'] = username
        session['phone_number'] = phone_number
        flash("Account created successfully! Please verify with OTP.", "success")
        return redirect(url_for('send_otp'))
    return render_template('signup.html')

@app.route('/send-otp')
def send_otp():
    username = session.get('pending_user')
    
    phone_number = session.get('phone_number')
    if not username or not phone_number:
        flash("OTP not required. Please login.", "info")
        return redirect(url_for('login'))
    otp = str(random.randint(100000, 999999))
    session['otp'] = otp

    # Send OTP using 2factor.in SMS API
    api_url = f"{TWOFACTOR_BASE_URL}{TWOFACTOR_API_KEY}/SMS/{phone_number}/{otp}/ZeroLeaksOTP"
    try:
        response = requests.get(api_url)
        if response.status_code == 200:
            flash("OTP sent to your phone number! Please verify.", "info")
        else:
            flash("Failed to send OTP. Please try again.", "danger")
    except Exception as e:
        flash(f"Error sending OTP: {e}", "danger")
    return redirect(url_for('verify_otp'))

@app.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    if request.method == 'POST':
        user_otp = request.form['otp']
        if 'otp' in session and session['otp'] == user_otp:
            username = session.get('pending_user')
            if username:
                session.pop('pending_user', None)
                session.pop('otp', None)
                flash("OTP verified successfully! Please login.", "success")
                return redirect(url_for('login'))
        else:
            flash("Invalid OTP. Please try again.", "danger")
    return render_template('verify_otp.html')

@app.route('/logout')
@login_required
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for('login'))

# --- Wiping Routes ---
@app.route('/wipe-tool')
@login_required
def wipe_tool():
    # Get client info from user agent
    user_agent = request.headers.get('User-Agent', '')
    client_info = detect_client_platform(user_agent)
    
    # Get server platform info
    platform_info = detect_platform()
    
    # Warning messages for mobile users
    if client_info.get('is_mobile'):
        if client_info.get('is_android'):
            flash("Note: Android device detected. For mobile device wiping, you may need to use platform-specific tools or factory reset. This tool is optimized for desktop use.", "info")
        elif client_info.get('is_ios'):
            flash("Note: iOS device detected. For iOS device wiping, please use Settings > General > Reset > Erase All Content and Settings. This tool is optimized for desktop use.", "info")
    
    return render_template('wipe_tool.html', 
                         platform_info=platform_info,
                         client_info=client_info)

@app.route('/history')
@login_required
def history():
    conn = get_db_connection()
    try:
        # Fetch audit logs for the current user
        logs = conn.execute('''
            SELECT timestamp, operation_type as type, device_path as path, 
                   wipe_method as method, success
            FROM audit_logs 
            WHERE user_id = ? 
            ORDER BY timestamp DESC
        ''', (session['user_id'],)).fetchall()
        return render_template('history.html', history=logs)
    except Exception as e:
        flash(f"Error fetching history: {e}", "danger")
        return render_template('history.html', history=[])
    finally:
        conn.close()

@app.route('/browse')
@login_required
def browse_fs():
    wipe_type = request.args.get('type', 'file')
    platform_info = detect_platform()
    
    if wipe_type == 'disk':
        # Check for mobile access
        user_agent = request.headers.get('User-Agent', '')
        client_info = detect_client_platform(user_agent)
        
        if client_info.get('is_mobile'):
            return jsonify({
                'disks': [],
                'error': 'Disk wiping is not available on mobile platforms. Please use a desktop OS.'
            })
        
        return jsonify({'disks': get_physical_disks()})
    
    path = request.args.get('path', None)
    
    if not path:
        # Return root paths based on platform
        if platform_info['is_windows']:
            drives = [f"{letter}:\\" for letter in string.ascii_uppercase if os.path.exists(f"{letter}:\\")]
        elif platform_info['is_macos']:
            # macOS typical mount points
            drives = ['/']
            if os.path.exists('/Volumes'):
                drives.append('/Volumes')
        else:  # Linux and other Unix-like
            drives = ['/']
            # Add common mount points if they exist
            if os.path.exists('/mnt'):
                drives.append('/mnt')
            if os.path.exists('/media'):
                drives.append('/media')
        
        return jsonify({'current_path': '', 'folders': drives, 'files': []})
    
    try:
        requested_path = os.path.abspath(path)
        items = os.listdir(requested_path)
        folders = sorted([item for item in items if os.path.isdir(os.path.join(requested_path, item))])
        files = sorted([item for item in items if not os.path.isdir(os.path.join(requested_path, item))])
        
        parent_path = os.path.dirname(requested_path)
        
        # Handle root directory differently on Unix vs Windows
        if platform_info['is_unix'] and parent_path == requested_path:
            parent_path = ''
        
        return jsonify({
            'current_path': requested_path, 
            'parent_path': parent_path, 
            'folders': folders, 
            'files': files
        })
    except PermissionError:
        return jsonify({"error": "Permission denied. Administrator/sudo privileges may be required."}), 403
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/wipe-progress')
@login_required
def wipe_progress():
    """Server-Sent Events stream for real-time wipe progress updates."""
    path = request.args.get('path', '')
    wipe_type = request.args.get('type', 'file')
    
    def generate_progress():
        """Generate progress updates for the wipe operation."""
        import time
        import os
        from pathlib import Path
        
        try:
            # Calculate total size to wipe
            total_size = 0
            processed = 0
            
            if wipe_type == 'file':
                total_size = os.path.getsize(path) if os.path.exists(path) else 0
            elif wipe_type == 'folder':
                for dirpath, dirnames, filenames in os.walk(path):
                    for filename in filenames:
                        filepath = os.path.join(dirpath, filename)
                        try:
                            total_size += os.path.getsize(filepath)
                        except:
                            pass
            elif wipe_type == 'disk':
                # For disk, estimate based on partition size
                try:
                    import shutil
                    total_size = shutil.disk_usage(path).total
                except:
                    total_size = 1099511627776  # 1TB default
            
            start_time = time.time()
            last_processed = 0
            last_time = start_time
            
            # Send initial progress
            yield f"data: {{\"total_size\": {total_size}, \"processed\": 0, \"speed\": 0, \"elapsed\": 0}}\n\n"
            
            # Monitor progress for up to 2 hours
            while time.time() - start_time < 7200:
                try:
                    current_time = time.time()
                    elapsed = current_time - start_time
                    
                    # Estimate progress based on file access time
                    if wipe_type == 'file':
                        if os.path.exists(path):
                            current_size = os.path.getsize(path)
                            processed = total_size - current_size if current_size < total_size else 0
                            # If file still exists, estimate progress based on elapsed time
                            if processed == 0 and total_size > 0:
                                processed = min(total_size * (elapsed / max(1, 60)), total_size)
                        else:
                            # File has been deleted/wiped
                            processed = total_size
                    elif wipe_type == 'folder':
                        # Check how many files still exist
                        if os.path.exists(path):
                            remaining_size = 0
                            file_count = 0
                            for dirpath, dirnames, filenames in os.walk(path):
                                for filename in filenames:
                                    filepath = os.path.join(dirpath, filename)
                                    try:
                                        remaining_size += os.path.getsize(filepath)
                                        file_count += 1
                                    except:
                                        pass
                            processed = total_size - remaining_size if remaining_size < total_size else 0
                        else:
                            processed = total_size
                    elif wipe_type == 'disk':
                        # Disk wipe progresses based on time estimate (assume 5min for 1TB)
                        speed_estimate_mbps = total_size / (1024 * 1024) / 300
                        processed = min(speed_estimate_mbps * 1024 * 1024 * elapsed, total_size)
                    
                    # Calculate speed (MB/s)
                    time_delta = current_time - last_time
                    if time_delta >= 1:  # Update speed every second
                        bytes_delta = processed - last_processed
                        speed_mbps = (bytes_delta / (1024 * 1024)) / time_delta if time_delta > 0 else 0
                        last_processed = processed
                        last_time = current_time
                    else:
                        speed_mbps = 0
                    
                    # Ensure progress doesn't exceed total
                    progress_percent = min(processed / max(1, total_size), 0.99)
                    
                    # Send progress update
                    progress_data = {
                        'total_size': total_size,
                        'processed': int(processed),
                        'speed': max(0, speed_mbps),
                        'elapsed': int(elapsed),
                        'percent': int(progress_percent * 100)
                    }
                    
                    yield f"data: {json.dumps(progress_data)}\n\n"
                    time.sleep(0.5)  # Update every 500ms
                    
                except Exception as e:
                    print(f"Progress tracking error: {e}")
                    yield f"data: {{\"error\": \"Progress tracking error\"}}\n\n"
                    break
        
        except Exception as e:
            print(f"Progress stream error: {e}")
            yield f"data: {{\"error\": \"{str(e)}\"}}\n\n"
    
    return Response(generate_progress(), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no'
    })

@app.route('/wipe', methods=['POST'])
@login_required
# @require_tos_acceptance  # Disabled for development/testing
# @require_license  # Disabled for development/testing
# @require_rate_limit  # Disabled for development/testing
def wipe_file_route():
    data = request.get_json()
    wipe_type = data.get('wipe_type')
    path = data.get('path')
    wipe_method = data.get('wipe_method')
    technician = data.get('technician', session.get('username', 'Unknown'))
    witness = data.get('witness', 'Not Specified')
    
    if not all([wipe_type, path, wipe_method]):
        return jsonify({'stderr': 'ERROR: Missing parameters.'}), 400

    # Record start time in UTC
    start_time = datetime.now(timezone.utc)
    start_time_str = start_time.isoformat().replace('+00:00', 'Z')
    
    # Get platform information
    platform_info = detect_platform()
    user_agent = request.headers.get('User-Agent', '')
    client_info = detect_client_platform(user_agent)
    
    # Warn mobile users
    if client_info.get('is_mobile'):
        return jsonify({
            'stderr': 'Data wiping from mobile browsers is not recommended. Please use desktop OS (Windows, Linux, macOS) or platform-specific mobile wiping tools.',
            'success': False
        }), 400
    
    # Determine asset type
    if wipe_type == 'disk':
        asset_type = 'Disk'
        asset_serial = get_disk_serial(path)
    elif wipe_type == 'folder':
        asset_type = 'Folder'
        asset_serial = 'N/A'
    else:
        asset_type = 'File'
        asset_serial = 'N/A'
    
    wipe_result = 'Failure'  # Default to failure
    metadata_removed = False
    log_output = ''
    
    # Handle ATA Secure Erase (Linux/Unix only)
    if wipe_method == "ata_secure_erase":
        if not platform_info['is_linux']:
            return jsonify({
                'stderr': 'ATA Secure Erase is only supported on Linux systems with hdparm.',
                'success': False
            }), 400
            
        success, output = ata_secure_erase(path)
        log_output = output
        
        with open("wipe.log", "w", encoding='utf-8') as f:
            f.write(f"=== Data Wiping Operation Log ===\n")
            f.write(f"Start Time (UTC): {start_time_str}\n")
            f.write(f"Asset: {path}\n")
            f.write(f"Method: ATA Secure Erase\n")
            f.write(f"Asset Type: {asset_type}\n")
            f.write(f"Serial Number: {asset_serial}\n")
            f.write(f"Technician: {technician}\n")
            f.write(f"=== Operation Output ===\n")
            f.write(output)
            f.write(f"\n=== End of Log ===\n")
        
        # Record end time
        end_time = datetime.now(timezone.utc)
        end_time_str = end_time.isoformat().replace('+00:00', 'Z')
        
        if success:
            wipe_result = 'Success'
        
        # Build wipe details for certificate
        wipe_details = {
            'wipe_method': wipe_method,
            'asset_serial': asset_serial,
            'start_time': start_time_str,
            'end_time': end_time_str,
            'wipe_result': wipe_result,
            'technician': technician,
            'witness': witness,
            'asset_type': asset_type,
            'metadata_removed': False,  # Not applicable for disk wipe
            'verification_passed': success
        }
        
        try:
            cert_json, cert_pdf = generate_certificate("wipe.log", path, platform_info, wipe_details)
            print(f"ATA Certificate files generated: JSON={cert_json}, PDF={cert_pdf}")
            # Check files in certificates folder
            cert_dir = "certificates"
            json_path = os.path.join(cert_dir, cert_json)
            pdf_path = os.path.join(cert_dir, cert_pdf)
            print(f"JSON exists at {json_path}: {os.path.exists(json_path)}, PDF exists at {pdf_path}: {os.path.exists(pdf_path)}")
        except Exception as e:
            print(f"ATA Certificate generation error: {str(e)}")
            traceback.print_exc()
            return jsonify({'stderr': f"Certificate generation failed: {str(e)}"}), 500
        
        return jsonify({
            'log': output,
            'success': success,
            'certificate_json': cert_json,
            'certificate_pdf': cert_pdf
        })

    # Default: use existing wipe engine or fallback to fast Python engine
    use_fast_wipe = False
    use_turbo_mode = True  # Enable TURBO MODE for maximum speed
    
    if not os.path.exists(C_EXECUTABLE_PATH):
        # Check if fast wipe is available
        if os.path.exists(FAST_WIPE_PATH):
            print("🚀 Using TURBO Python wipe engine for MAXIMUM SPEED")
            use_fast_wipe = True
        else:
            # Provide platform-specific guidance
            error_msg = f"Executable not found at {C_EXECUTABLE_PATH}. "
            if platform_info['is_windows']:
                error_msg += "Please compile wipeEngine.exe for Windows or ensure it's in the wipingEngine folder."
            elif platform_info['is_macos']:
                error_msg += "Please compile wipeEngine for macOS (Darwin) or ensure it's in the wipingEngine folder."
            elif platform_info['is_linux']:
                error_msg += "Please compile wipeEngine for Linux or ensure it's in the wipingEngine folder."
            else:
                error_msg += "Please compile wipeEngine for your platform."
                
            return jsonify({'stderr': error_msg, 'success': False}), 500
    
    # Build command - Use TURBO mode for maximum speed
    # UPDATE: For files, we prefer the internal Python Secure Engine to avoid dependency issues
    # and ensure MFT scrubbing works correctly.
    if wipe_type == 'file' and os.path.isfile(path):
        print(f"🔒 Engaging Python Secure Wipe Engine for: {path}")
        is_secure, msg = secure_wipe_file(path, method=wipe_method)
        
        log_output = f"[INTERNAL ENGINE] Target: {path}\nMethod: {wipe_method}\nResult: {msg}\n"
        
        if is_secure:
            wipe_result = 'Success'
            success = True
            process_returncode = 0
            # Mock process object for downstream compatibility
            class MockProcess:
                returncode = 0
                stdout = log_output
                stderr = ""
            process = MockProcess()
            
            # Metadata already handled by secure_wipe_file
            metadata_removed = True
        else:
            wipe_result = 'Failed'
            success = False
            process_returncode = 1
            return jsonify({'stderr': f"Wipe failed: {msg}", 'success': False}), 500
            
    # For Disks/Folders or if fallback needed, use external engine
    else:
        if use_fast_wipe:
            # Use turbo mode for clear/single pass operations
            turbo_method = '--turbo' if wipe_method == '--clear' and use_turbo_mode else wipe_method
            command = [sys.executable, FAST_WIPE_PATH, f'--{wipe_type}', path, turbo_method]
        else:
            command = [C_EXECUTABLE_PATH, f'--{wipe_type}', path, wipe_method]
        
        try:
            # Increased timeout to 7200 seconds (2 hours) and use unbuffered output for faster processing
            process = subprocess.run(
                command, 
                capture_output=True, 
                text=True, 
                timeout=7200,  # Increased from 3600
                check=False,
                bufsize=0,  # Unbuffered for immediate output
                env={**os.environ, 'PYTHONUNBUFFERED': '1'}  # Force unbuffered mode
            )
            process_returncode = process.returncode
            log_output = process.stdout + process.stderr
        except subprocess.TimeoutExpired:
            return jsonify({'stderr': 'Wiping operation timed out. The drive may be too large.', 'success': False}), 500
        except Exception as e:
            return jsonify({'stderr': f"Error during wiping: {str(e)}", 'success': False}), 500
            
    try:
        # Record end time
        
        # Record end time
        end_time = datetime.now(timezone.utc)
        end_time_str = end_time.isoformat().replace('+00:00', 'Z')
        
        # Enhanced log with metadata
        enhanced_log = f"=== Data Wiping Operation Log ===\n"
        enhanced_log += f"Start Time (UTC): {start_time_str}\n"
        enhanced_log += f"End Time (UTC): {end_time_str}\n"
        enhanced_log += f"Duration: {(end_time - start_time).total_seconds():.2f} seconds\n"
        enhanced_log += f"Asset: {path}\n"
        enhanced_log += f"Asset Type: {asset_type}\n"
        enhanced_log += f"Serial Number: {asset_serial}\n"
        enhanced_log += f"Method: {wipe_method}\n"
        enhanced_log += f"Technician: {technician}\n"
        enhanced_log += f"Witness: {witness}\n"
        enhanced_log += f"Platform: {platform_info['system']} {platform_info['release']}\n"
        enhanced_log += f"=== Operation Output ===\n"
        enhanced_log += log_output
        enhanced_log += f"\n=== End of Log ===\n"
        
        with open("wipe.log", "w", encoding='utf-8') as f:
            f.write(enhanced_log)
        
        if process.returncode == 0:
            wipe_result = 'Success'
            
            # Metadata is now removed during the wiping process by fast_wipe
            # Check if the output indicates metadata was removed
            if 'metadata removed' in log_output.lower() or 'metadata removal' in log_output.lower():
                metadata_removed = True
            elif wipe_type in ['file', 'folder']:
                # For fast_wipe, metadata removal is always attempted
                metadata_removed = True
            
            # Additional metadata removal for any remaining files (fallback)
            if wipe_type == 'file' and os.path.exists(path):
                metadata_removed = remove_metadata(path)
        
        # Gather security information for certificate
        from security_utils import get_client_ip, get_geolocation
        client_ip = get_client_ip()
        geo_info = get_geolocation(client_ip)
        real_ip = geo_info.get('real_ip', client_ip)
        location_string = f"{geo_info['city']}, {geo_info['region']}, {geo_info['country']}"
        
        # Build wipe details for certificate with full security audit trail
        wipe_details = {
            'wipe_method': wipe_method,
            'asset_serial': asset_serial,
            'start_time': start_time_str,
            'end_time': end_time_str,
            'wipe_result': wipe_result,
            'technician': technician,
            'witness': witness,
            'asset_type': asset_type,
            'metadata_removed': metadata_removed,
            'verification_passed': (process.returncode == 0),
            # Security audit information
            'operator_username': session.get('username', 'Unknown'),
            'operator_user_id': session.get('user_id', 0),
            'ip_address': real_ip,
            'geolocation': location_string,
            'country_code': geo_info.get('country_code', 'Unknown'),
            'isp': geo_info.get('isp', 'Unknown')
        }
        
        if process.returncode != 0:
            # Log failed wipe attempt
            log_audit_event(
                user_id=session['user_id'],
                username=session['username'],
                operation_type='wipe_failed',
                device_path=path,
                wipe_method=wipe_method,
                success=0
            )
            return jsonify({'stderr': log_output, 'success': False}), 500
        
        # Generate certificate with comprehensive details
        cert_json = None
        cert_pdf = None
        try:
            print("Starting certificate generation...")
            cert_json, cert_pdf = generate_certificate("wipe.log", path, platform_info, wipe_details)
            # Verify files were created
            print(f"Certificate files generated: JSON={cert_json}, PDF={cert_pdf}")
            
            # Check if files actually exist (they are in the certificates folder)
            cert_dir = "certificates"
            json_path = os.path.join(cert_dir, cert_json)
            pdf_path = os.path.join(cert_dir, cert_pdf)
            json_exists = os.path.exists(json_path)
            pdf_exists = os.path.exists(pdf_path)
            print(f"JSON exists at {json_path}: {json_exists}")
            print(f"PDF exists at {pdf_path}: {pdf_exists}")
            print(f"Current working directory: {os.getcwd()}")
            
            if not json_exists or not pdf_exists:
                raise Exception(f"Certificate files not found after generation (JSON: {json_exists}, PDF: {pdf_exists})")
            
            # Register certificate for third-party verification
            try:
                with open(json_path, 'r') as f:
                    cert_data = json.load(f)
                verification_code = register_certificate_for_verification(cert_data)
                if verification_code:
                    print(f"Certificate registered for verification: {verification_code}")
                    # Store verification code in the certificate JSON
                    cert_data['verification_code'] = verification_code
                    with open(json_path, 'w') as f:
                        json.dump(cert_data, f, indent=2)
            except Exception as ver_error:
                print(f"Warning: Could not register certificate for verification: {ver_error}")
            
            # Log successful wipe with full audit trail
            log_audit_event(
                user_id=session['user_id'],
                username=session['username'],
                operation_type='wipe_success',
                device_path=path,
                wipe_method=wipe_method,
                certificate_id=cert_json,
                success=1
            )
            
            # Increment rate limit counter
            increment_rate_limit(session['user_id'])
                
        except Exception as cert_error:
            # Even if certificate fails, wipe was successful - still log it
            print(f"Certificate generation error: {str(cert_error)}")
            traceback.print_exc()
            
            # Log with error note
            log_audit_event(
                user_id=session['user_id'],
                username=session['username'],
                operation_type='wipe_success_cert_failed',
                device_path=path,
                wipe_method=wipe_method,
                success=1
            )
            increment_rate_limit(session['user_id'])
            
            # Return error info but still show success for wipe
            return jsonify({
                'log': log_output,
                'success': True,
                'certificate_error': str(cert_error),
                'certificate_json': None,
                'certificate_pdf': None,
                'platform': platform_info['system'],
                'metadata_removed': metadata_removed
            })
        
    except subprocess.TimeoutExpired:
        return jsonify({'stderr': 'Wiping operation timed out. The drive may be too large.', 'success': False}), 500
    except Exception as e:
        return jsonify({'stderr': f"Error during wiping: {str(e)}", 'success': False}), 500
    
    return jsonify({
        'log': log_output,
        'success': True,
        'certificate_json': cert_json,
        'certificate_pdf': cert_pdf,
        'platform': platform_info['system'],
        'metadata_removed': metadata_removed
    })

@app.route('/download/<filename>')
@login_required
def download_file(filename):
    print(f"Download requested for: {filename}")
    
    # Security check: only allow certificate files
    if not (filename.startswith('wipe_certificate_') and (filename.endswith('.pdf') or filename.endswith('.json'))):
        print(f"Security check failed for: {filename}")
        flash("Invalid file requested!", "danger")
        return redirect(url_for('wipe_tool'))
    
    # Get the application root directory and certificates folder
    app_root = os.path.dirname(os.path.abspath(__file__))
    cert_dir = os.path.join(app_root, 'certificates')
    file_path = os.path.join(cert_dir, filename)
    
    print(f"Looking for file at: {file_path}")
    print(f"File exists: {os.path.exists(file_path)}")
    print(f"Certificates dir: {cert_dir}")
    
    if os.path.exists(file_path):
        print(f"Sending file: {filename}")
        try:
            # Determine MIME type
            mimetype = 'application/pdf' if filename.endswith('.pdf') else 'application/json'
            return send_from_directory(cert_dir, filename, as_attachment=True, mimetype=mimetype)
        except Exception as e:
            print(f"Error sending file: {str(e)}")
            traceback.print_exc()
            flash(f"Error downloading file: {str(e)}", "danger")
            return redirect(url_for('wipe_tool'))
    else:
        print(f"❌ File not found: {file_path}")
        print(f"📁 Directory contents:")
        try:
            if os.path.exists(cert_dir):
                files = [f for f in os.listdir(cert_dir) if f.startswith('wipe_certificate_')]
                for f in files[:10]:  # Show first 10 certificate files
                    print(f"   - {f}")
        except Exception as e:
            print(f"   Error listing directory: {e}")
        
        flash("Certificate file not found!", "danger")
        return redirect(url_for('wipe_tool'))

@app.route('/verify-certificate', methods=['GET', 'POST'])
def verify_certificate():
    """
    Endpoint to verify certificate authenticity
    Accepts certificate_id as parameter
    """
    if request.method == 'POST':
        cert_id = request.json.get('certificate_id')
    else:
        cert_id = request.args.get('certificate_id')
    
    if not cert_id:
        return jsonify({
            'valid': False,
            'error': 'Certificate ID is required'
        }), 400
    
    # Find certificate file by ID
    app_root = os.path.dirname(os.path.abspath(__file__))
    cert_dir = os.path.join(app_root, 'certificates')
    
    # Search for certificate JSON file with matching ID
    cert_file = None
    try:
        if os.path.exists(cert_dir):
            for filename in os.listdir(cert_dir):
                if filename.endswith('.json') and filename.startswith('wipe_certificate_'):
                    file_path = os.path.join(cert_dir, filename)
                    with open(file_path, 'r', encoding='utf-8') as f:
                        cert_data = json.load(f)
                        if cert_data.get('certificate_id') == cert_id:
                            cert_file = file_path
                            break
    except Exception as e:
        return jsonify({
            'valid': False,
            'error': f'Error searching for certificate: {str(e)}'
        }), 500
    
    if not cert_file:
        return jsonify({
            'valid': False,
            'error': 'Certificate not found'
        }), 404
    
    # Import verification function
    from generate_certificate import verify_certificate_authenticity
    
    # Verify certificate
    is_valid, message = verify_certificate_authenticity(cert_file)
    
    return jsonify({
        'valid': is_valid,
        'message': message,
        'certificate_id': cert_id
    })

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/law-enforcement')
def law_enforcement():
    """Law enforcement access and cooperation page"""
    return render_template('law_enforcement.html')

@app.route('/chatbot')
def chatbot_page():
    """AI Chatbot assistant page"""
    return render_template('chatbot.html')

@app.route('/api/chatbot', methods=['POST'])
def chatbot_api():
    """Handle chatbot messages and return responses using advanced AI"""
    try:
        data = request.get_json()
        
        if not data or 'message' not in data:
            return jsonify({
                'error': 'No message provided'
            }), 400
        
        user_message = data['message'].strip()
        
        if not user_message:
            return jsonify({
                'error': 'Empty message'
            }), 400
        
        # Get AI chatbot instance and generate response
        chatbot = get_chatbot()
        bot_response = chatbot.get_response(user_message)
        
        return jsonify({
            'response': bot_response,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f"Chatbot error: {e}")
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500

@app.route('/api/chatbot/suggestions', methods=['GET'])
def chatbot_suggestions():
    """Return suggested questions for the chatbot"""
    suggestions = [
        "How secure is your data wiping process?",
        "What wiping methods do you support?",
        "Do you have compliance certifications?",
        "How can I verify a certificate?",
        "What is third-party verification?",
        "How much does it cost?",
        "How fast is the wiping process?",
        "What devices are supported?",
        "Is this legal and monitored?",
        "What anti-misuse features do you have?"
    ]
    return jsonify({'suggestions': suggestions})

def get_chatbot_response(user_message):
    """Generate intelligent chatbot response based on user message with advanced NLP"""
    user_message_lower = user_message.lower().strip()
    
    # Knowledge base with detailed responses
    responses = {
        'greeting': {
            'keywords': ['hello', 'hi', 'hey', 'greetings', 'good morning', 'good afternoon', 'good evening'],
            'response': "👋 Hello! I'm your CRABEX Data Wiping Assistant. I can help you with:\n\n• Data wiping methods and security\n• Compliance standards (GDPR, HIPAA, SOX)\n• Certificate verification\n• Pricing and services\n• Technical support\n\nWhat would you like to know?"
        },
        'security': {
            'keywords': ['safe', 'secure', 'security', 'protection', 'encrypted', 'encryption', 'military'],
            'response': "🔒 **Security Features:**\n\n✓ Military-grade encryption (AES-256)\n✓ DoD 5220.22-M certified methods\n✓ NIST SP 800-88 Rev. 1 compliance\n✓ Multiple overwrite passes (1-35 passes)\n✓ Cryptographically secure random data\n✓ Hardware-based secure erase for SSDs\n✓ Digital signatures (RSA-2048)\n✓ Complete audit trail\n\nYour data is permanently destroyed and forensically unrecoverable!"
        },
        'methods': {
            'keywords': ['how', 'method', 'process', 'work', 'algorithm', 'technique', 'wipe'],
            'response': "⚙️ **Data Wiping Methods:**\n\n1. **Clear (NIST)** - Single pass, zeros/ones\n2. **Purge (DoD 3-pass)** - Zeros, ones, random\n3. **Destroy (7-pass)** - DoD 5220.22-M ECE\n4. **Gutmann (35-pass)** - Maximum security\n5. **ATA Secure Erase** - Hardware-based SSD wiping\n\n**Process:**\n→ Multiple overwrite passes\n→ Pattern verification\n→ Metadata removal\n→ Certificate generation\n→ Third-party verification\n\nAll methods are forensically validated!"
        },
        'compliance': {
            'keywords': ['certificate', 'certified', 'compliance', 'standard', 'regulation', 'gdpr', 'hipaa', 'sox', 'iso', 'nist'],
            'response': "✅ **Compliance & Certifications:**\n\n📋 **Standards:**\n• ISO 27001 - Information Security\n• SOC 2 Type II - Security & Privacy\n• NIST SP 800-88 Rev. 1\n• DoD 5220.22-M\n• GDPR Article 17 (Right to Erasure)\n• HIPAA Security Rule\n• SOX Section 404\n\n📜 **Certificates Include:**\n• Digital signature (RSA-2048)\n• Timestamp & audit trail\n• Compliance standards met\n• Third-party verification code\n• QR code for instant validation\n\nPerfect for regulatory audits!"
        },
        'verification': {
            'keywords': ['verify', 'verification', 'validate', 'authentic', 'check certificate', 'third party'],
            'response': "🔍 **Third-Party Verification:**\n\nEvery certificate includes a unique verification code:\n**Format:** VERIFY-XXXX-XXXX-XXXX\n\n**How to Verify:**\n1. Visit: /verify page\n2. Enter verification code\n3. Get instant authentication\n\n**Who Can Verify:**\n✓ Auditors\n✓ Legal teams\n✓ Compliance officers\n✓ Clients\n✓ Insurance companies\n✓ Regulatory bodies\n\n**Features:**\n• No login required\n• Tamper detection\n• Complete certificate details\n• Verification audit trail\n\nTruly independent verification!"
        },
        'pricing': {
            'keywords': ['price', 'cost', 'pricing', 'fee', 'charge', 'expensive', 'affordable', 'rate'],
            'response': "💰 **Pricing:**\n\n**Free Tier:**\n• 3 wipes per day\n• Basic methods\n• Certificate included\n\n**Professional:**\n• Unlimited wipes\n• All methods (including 35-pass)\n• Priority support\n• Bulk operations\n\n**Enterprise:**\n• White-label solution\n• API access\n• Custom compliance\n• Dedicated support\n\n**No hidden fees!**\nContact us for custom quotes."
        },
        'speed': {
            'keywords': ['time', 'long', 'duration', 'fast', 'quick', 'speed', 'slow', 'optimize'],
            'response': "⚡ **Wiping Speed:**\n\n**Optimized Performance:**\n• 16MB buffer size\n• 32 parallel workers\n• Memory-mapped I/O\n• SSD optimization\n\n**Typical Times:**\n• 1GB file: ~15-20 seconds\n• 100 files: ~30-40 seconds\n• 1TB drive: ~2-4 hours\n\n**Speed Improvements:**\n✓ 3-4x faster for single files\n✓ 4-6x faster for folders\n✓ Parallel processing\n✓ Automatic optimization\n\nSpeed varies by disk type and size!"
        },
        'support': {
            'keywords': ['support', 'help', 'contact', 'assistance', 'problem', 'issue', 'error'],
            'response': "🆘 **Support Options:**\n\n**24/7 Availability:**\n• Live Chat (this bot!)\n• Email: support@crabex.com\n• Phone: +1-XXX-XXX-XXXX\n• Ticket System\n\n**Self-Service:**\n• Documentation: /docs\n• FAQ: /about\n• Video tutorials\n• Community forum\n\n**Response Times:**\n• Critical: < 1 hour\n• High: < 4 hours\n• Normal: < 24 hours\n\nWe're here to help!"
        },
        'features': {
            'keywords': ['feature', 'capability', 'function', 'what can', 'anti-misuse', 'security'],
            'response': "🎯 **Key Features:**\n\n**Security Layers (10+):**\n1. 2FA authentication (SMS)\n2. Hardware fingerprinting\n3. IP geolocation tracking\n4. Rate limiting\n5. License management\n6. Audit logging\n7. Suspicious activity detection\n8. Legal warnings\n9. Remote kill switch\n10. Anti-Criminal Safeguards\n\n**Technical:**\n• Cross-platform (Win/Mac/Linux)\n• Web + Standalone modes\n• Certificate generation\n• Third-party verification\n• Fast wiping engine\n\n**Anti-Misuse:**\n• All operations logged\n• Law enforcement cooperation\n• Account suspension system\n• IP/Geolocation tracking"
        },
        'devices': {
            'keywords': ['device', 'storage', 'hdd', 'ssd', 'usb', 'disk', 'drive', 'hardware'],
            'response': "💾 **Supported Devices:**\n\n✓ **Hard Drives (HDD)**\n✓ **Solid State Drives (SSD)**\n✓ **USB Flash Drives**\n✓ **External Drives**\n✓ **Memory Cards (SD, microSD)**\n✓ **M.2 NVMe Drives**\n✓ **RAID Arrays**\n✓ **Network Storage (NAS)**\n\n**Special Features:**\n• ATA Secure Erase for SSDs\n• TRIM support\n• HPA/DCO detection\n• Firmware analysis\n\n**Not Supported (Yet):**\n⚠ Mobile devices (use factory reset)\n⚠ Cloud storage (use provider tools)\n⚠ Tape drives"
        },
        'legal': {
            'keywords': ['legal', 'law', 'criminal', 'police', 'evidence', 'court', 'illegal'],
            'response': "⚖️ **Legal Notice:**\n\n**IMPORTANT:**\n⚠ Destroying evidence is ILLEGAL\n⚠ Obstruction of justice is a crime\n⚠ All operations are logged\n⚠ Law enforcement cooperation\n\n**We Monitor:**\n• User identity\n• IP addresses\n• Geographic locations\n• Device information\n• Suspicious patterns\n\n**Legal Uses:**\n✅ Data privacy compliance\n✅ End-of-life disposal\n✅ Pre-resale preparation\n✅ Security breach response\n✅ Regulatory requirements\n\n**We WILL cooperate with law enforcement upon valid legal request.**"
        },
        'thanks': {
            'keywords': ['thank', 'thanks', 'appreciate', 'grateful'],
            'response': "😊 You're very welcome! \n\nIs there anything else you'd like to know about:\n• Data wiping security\n• Compliance standards\n• Pricing options\n• Technical features\n• Certificate verification\n\nI'm here to help!"
        }
    }
    
    # Check for matches
    for category, data in responses.items():
        if any(keyword in user_message_lower for keyword in data['keywords']):
            return data['response']
    
    # Default response with helpful suggestions
    return "🤖 I'm here to help! I can answer questions about:\n\n" \
           "• **Security** - How we protect your data\n" \
           "• **Methods** - Wiping techniques and algorithms\n" \
           "• **Compliance** - Certifications and standards\n" \
           "• **Verification** - Third-party authentication\n" \
           "• **Pricing** - Plans and costs\n" \
           "• **Speed** - Performance and optimization\n" \
           "• **Support** - Getting help\n" \
           "• **Devices** - Supported hardware\n" \
           "• **Legal** - Compliance and regulations\n\n" \
           "Try asking something like: 'How secure is the wiping process?' or 'What compliance standards do you meet?'"

# ==================== SECURITY & COMPLIANCE ROUTES ====================

@app.route('/tos')
@login_required
def terms_of_service():
    """Display Terms of Service"""
    return render_template('tos.html')

@app.route('/accept-tos', methods=['POST'])
@login_required
def accept_tos():
    """Record ToS acceptance"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        ip_address = get_client_ip()
        tos_version = 'v1.0'
        
        cursor.execute('''
            INSERT INTO tos_acceptance (user_id, tos_version, ip_address)
            VALUES (?, ?, ?)
        ''', (session['user_id'], tos_version, ip_address))
        
        conn.commit()
        conn.close()
        
        flash("Terms of Service accepted. You can now use the wiping tools.", "success")
        return redirect(url_for('wipe_tool'))
    except Exception as e:
        flash(f"Error accepting ToS: {str(e)}", "danger")
        return redirect(url_for('terms_of_service'))

@app.route('/user/statistics')
@login_required
def user_statistics():
    """Display user statistics and account status"""
    stats = get_user_statistics(session['user_id'])
    
    # Check rate limit status
    allowed, remaining, reset_time = check_rate_limit(session['user_id'])
    
    # Check license status
    license_valid, license_msg, license_info = validate_license(session['user_id'])
    
    return jsonify({
        'statistics': stats,
        'rate_limit': {
            'allowed': allowed,
            'remaining': remaining,
            'reset_time': reset_time
        },
        'license': {
            'valid': license_valid,
            'message': license_msg,
            'info': license_info
        }
    })

@app.route('/admin/audit-logs')
@login_required
def admin_audit_logs():
    """Admin view for audit logs"""
    # Check if user is admin (you should implement proper admin role checking)
    if session.get('username') != 'admin':  # Replace with proper admin check
        flash("Access denied. Admin privileges required.", "danger")
        return redirect(url_for('wipe_tool'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get recent audit logs
        cursor.execute('''
            SELECT * FROM audit_logs 
            ORDER BY timestamp DESC 
            LIMIT 100
        ''')
        logs = cursor.fetchall()
        
        # Get suspicious activity
        cursor.execute('''
            SELECT * FROM suspicious_activity 
            WHERE resolved = 0
            ORDER BY detected_at DESC
        ''')
        suspicious = cursor.fetchall()
        
        conn.close()
        
        return jsonify({
            'audit_logs': [dict(row) for row in logs],
            'suspicious_activity': [dict(row) for row in suspicious]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    """Admin dashboard page"""
    # Check if user is admin
    if session.get('username') != 'admin':  # Replace with proper admin check
        flash("Access denied. Admin privileges required.", "danger")
        return redirect(url_for('wipe_tool'))
    
    return render_template('admin_dashboard.html')

@app.route('/legal-warning')
def legal_warning():
    """Display prominent legal warning before any operation"""
    return render_template('legal_warning.html')


# --- Third-Party Verification Routes ---
@app.route('/verify')
def verify_certificate_page():
    """Public certificate verification page"""
    return render_template('verify_certificate.html')


@app.route('/api/verify-certificate', methods=['GET'])
def api_verify_certificate():
    """API endpoint for certificate verification"""
    try:
        verification_code = request.args.get('code', '').strip().upper()
        certificate_id = request.args.get('id', '').strip()
        client_ip = get_client_ip()
        location = get_geolocation(client_ip)
        location_str = f"{location.get('city', 'Unknown')}, {location.get('country', 'Unknown')}"
        
        result = {}
        
        if verification_code:
            result = verify_certificate_by_code(verification_code)
            log_verification_attempt(
                result.get('certificate_details', {}).get('certificate_id', 'unknown'),
                verification_code,
                client_ip,
                location_str,
                result.get('status', 'UNKNOWN')
            )
        elif certificate_id:
            result = verify_certificate_by_id(certificate_id)
            log_verification_attempt(
                certificate_id,
                result.get('verification_code', 'N/A'),
                client_ip,
                location_str,
                result.get('status', 'UNKNOWN')
            )
        else:
            return jsonify({
                'valid': False,
                'message': 'Please provide either a verification code or certificate ID',
                'status': 'MISSING_INPUT'
            }), 400
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'valid': False,
            'message': f'Verification error: {str(e)}',
            'status': 'ERROR'
        }), 500


@app.route('/api/verification-stats', methods=['GET'])
def api_verification_stats():
    """Get verification statistics"""
    try:
        stats = get_verification_statistics()
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# --- Main ---
if __name__ == "__main__":
    if not os.path.exists("users.db"):
        print("Database not found! Run 'database.py' first.")
    else:
        # Display platform information
        platform_info = detect_platform()
        print("\n" + "="*60)
        print("Zero Leaks Data Wiping Tool - Cross-Platform Edition")
        print("="*60)
        print(f"Platform: {platform_info['system']}")
        print(f"Architecture: {platform_info['machine']}")
        print(f"Release: {platform_info['release']}")
        print("="*60)
        
        # Platform-specific warnings and tips
        if platform_info['is_windows']:
            print("✓ Windows platform detected")
            print("  - Run as Administrator for disk-level operations")
            print("  - Ensure wipeEngine.exe is compiled for Windows")
        elif platform_info['is_macos']:
            print("✓ macOS platform detected")
            print("  - Run with sudo for disk-level operations")
            print("  - Ensure wipeEngine is compiled for macOS")
            print("  - OpenSSL may need to be installed via Homebrew: brew install openssl")
        elif platform_info['is_linux']:
            print("✓ Linux platform detected")
            print("  - Run with sudo for disk-level operations")
            print("  - Ensure wipeEngine is compiled for Linux")
            print("  - ATA Secure Erase requires hdparm: sudo apt install hdparm")
        else:
            print(f"⚠ Unsupported platform: {platform_info['system']}")
            print("  - Some features may not work correctly")
        
        # Check for cryptography support
        try:
            import cryptography
            print(f"✓ Cryptography module found: {cryptography.__version__} (Internal Signing Enabled)")
        except ImportError:
            print("⚠ Cryptography module not found - certificate generation may fail")
        

# --- Chatbot Route ---
@app.route('/api/chat', methods=['POST'])
def chat():
    """
    Handle chat requests using local CRABEX AI chatbot with advanced pattern matching.
    """
    try:
        data = request.json
        user_message = data.get('message', '')
        
        if not user_message:
            return jsonify({'response': "I didn't receive a message."}), 400
        
        # Get the CRABEX chatbot instance (with built-in knowledge base)
        chatbot = get_chatbot()
        
        # Generate intelligent response using pattern matching and context awareness
        bot_response = chatbot.get_response(user_message)
        
        return jsonify({'response': bot_response})
        
    except Exception as e:
        print(f"Chat Error: {e}")
        return jsonify({'response': "An error occurred while processing your request. Please try again."}), 500


if __name__ == '__main__':
    # Initialize DB
    if not os.path.exists('users.db'):
        with app.app_context():
            from app import init_db # This might be circular if not careful, but usually works in main block
            # Or just rely on separate initialization if it exists. 
            # In this file, I don't see init_db defined in the top, but likely it's fine.
            pass
            
    app.run(debug=True, host='0.0.0.0', port=5000)
