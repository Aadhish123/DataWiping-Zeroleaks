"""
Initialize security database and create default licenses
Run this after updating database.py
"""

import sqlite3
from datetime import datetime, timedelta
import uuid

def setup_security():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    # Get all existing users
    cursor.execute('SELECT id, username FROM users')
    users = cursor.fetchall()
    
    for user_id, username in users:
        # Check if user already has a license
        cursor.execute('SELECT id FROM licenses WHERE user_id = ?', (user_id,))
        existing = cursor.fetchone()
        
        if not existing:
            # Create a free tier license
            license_key = str(uuid.uuid4()).upper()
            expiry_date = (datetime.now() + timedelta(days=365)).isoformat()  # 1 year
            
            cursor.execute('''
                INSERT INTO licenses (user_id, license_key, license_type, 
                                     activation_date, expiry_date, is_active, max_wipes_per_day)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, license_key, 'free', datetime.now().isoformat(), 
                  expiry_date, 1, 3))
            
            print(f"Created free license for user: {username} (ID: {user_id})")
    
    conn.commit()
    conn.close()
    print("\n✓ Security setup completed!")
    print("All users now have free tier licenses (3 wipes/day limit)")

if __name__ == '__main__':
    setup_security()
