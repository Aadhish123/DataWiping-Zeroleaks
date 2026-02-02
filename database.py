import sqlite3
from datetime import datetime

conn = sqlite3.connect('users.db')
cursor = conn.cursor()

# Users table
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        phone_number TEXT NOT NULL,
        is_verified INTEGER DEFAULT 0,
        verification_level TEXT DEFAULT 'unverified',
        account_status TEXT DEFAULT 'active',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        last_login TEXT,
        daily_wipe_limit INTEGER DEFAULT 3,
        total_wipes INTEGER DEFAULT 0
    )
''')

# Certificates table
cursor.execute('''
    CREATE TABLE IF NOT EXISTS certificates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cert_id TEXT NOT NULL UNIQUE,
        end_time TEXT NOT NULL,
        signature TEXT NOT NULL
    )
''')

# Audit logs table - CRITICAL for tracking all operations
cursor.execute('''
    CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        username TEXT NOT NULL,
        operation_type TEXT NOT NULL,
        device_path TEXT,
        wipe_method TEXT,
        purpose TEXT,
        ip_address TEXT NOT NULL,
        user_agent TEXT,
        geolocation TEXT,
        country_code TEXT,
        timestamp TEXT NOT NULL,
        certificate_id TEXT,
        hardware_info TEXT,
        success INTEGER DEFAULT 1,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
''')

# License management table
cursor.execute('''
    CREATE TABLE IF NOT EXISTS licenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        license_key TEXT NOT NULL UNIQUE,
        license_type TEXT NOT NULL,
        hardware_id TEXT,
        activation_date TEXT,
        expiry_date TEXT,
        is_active INTEGER DEFAULT 1,
        max_wipes_per_day INTEGER DEFAULT 3,
        can_be_deactivated INTEGER DEFAULT 1,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
''')

# User verification table
cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_verification (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        verification_type TEXT NOT NULL,
        document_path TEXT,
        verification_status TEXT DEFAULT 'pending',
        submitted_at TEXT DEFAULT CURRENT_TIMESTAMP,
        verified_at TEXT,
        verified_by TEXT,
        rejection_reason TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
''')

# Suspicious activity flags table
cursor.execute('''
    CREATE TABLE IF NOT EXISTS suspicious_activity (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        activity_type TEXT NOT NULL,
        severity TEXT NOT NULL,
        description TEXT NOT NULL,
        detected_at TEXT DEFAULT CURRENT_TIMESTAMP,
        ip_address TEXT,
        resolved INTEGER DEFAULT 0,
        resolved_at TEXT,
        action_taken TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
''')

# Rate limiting tracking table
cursor.execute('''
    CREATE TABLE IF NOT EXISTS rate_limits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        wipe_count INTEGER DEFAULT 0,
        last_wipe_time TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id),
        UNIQUE(user_id, date)
    )
''')

# Terms of Service acceptance table
cursor.execute('''
    CREATE TABLE IF NOT EXISTS tos_acceptance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        tos_version TEXT NOT NULL,
        accepted_at TEXT DEFAULT CURRENT_TIMESTAMP,
        ip_address TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
''')

# Remote kill switch log
cursor.execute('''
    CREATE TABLE IF NOT EXISTS kill_switch_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        license_key TEXT,
        reason TEXT NOT NULL,
        deactivated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        deactivated_by TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
''')

# Testimonials table for user feedback shown on the landing page
cursor.execute('''
    CREATE TABLE IF NOT EXISTS testimonials (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        role TEXT,
        rating INTEGER DEFAULT 5,
        text TEXT NOT NULL,
        approved INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
''')

print("Database 'users.db' initialized successfully with enhanced security tables.")
conn.commit()
conn.close()