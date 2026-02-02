"""
Security Log Viewer - View all security-related information
Shows WHO, WHEN, WHAT, WHERE, and WHY for all data wipe operations
"""

import sqlite3
import json
from datetime import datetime

def print_section(title):
    print("\n" + "="*80)
    print(f"🔍 {title}")
    print("="*80)

def view_audit_logs():
    """View complete audit trail of all wipe operations"""
    print_section("AUDIT LOGS - Complete Wipe History")
    
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    try:
        # Get all audit logs with detailed information
        cursor.execute('''
            SELECT id, user_id, username, operation_type, device_path, 
                   wipe_method, purpose, ip_address, geolocation, 
                   timestamp, hardware_info, certificate_id, success
            FROM audit_logs 
            ORDER BY timestamp DESC 
            LIMIT 50
        ''')
        
        logs = cursor.fetchall()
        
        if not logs:
            print("❌ No wipe operations found yet. Perform a wipe to see logs here.")
            return
        
        for log in logs:
            log_id, user_id, username, op_type, device, method, purpose, ip, geo, ts, hw, cert, success = log
            
            status = "✅ SUCCESS" if success else "❌ FAILED"
            purpose_display = purpose if purpose else "Not specified"
            
            print(f"\n📋 Log ID: {log_id}")
            print(f"   Status: {status}")
            print(f"   👤 WHO: User ID #{user_id} - Username: {username}")
            print(f"   🕐 WHEN: {ts}")
            print(f"   📁 WHAT: {device}")
            print(f"   🔧 METHOD: {method}")
            print(f"   📝 WHY: {purpose_display}")
            print(f"   🌐 WHERE (IP): {ip}")
            print(f"   📍 WHERE (Location): {geo}")
            print(f"   💻 DEVICE: {hw}")
            print(f"   🎫 CERTIFICATE: {cert}")
            print(f"   {'-'*76}")
    
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        conn.close()

def view_certificates():
    """View all generated certificates"""
    print_section("CERTIFICATES - Verification Codes")
    
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT id, user_id, certificate_id, verification_code, 
                   device_path, wipe_method, created_at, file_size, duration
            FROM certificates 
            ORDER BY created_at DESC 
            LIMIT 20
        ''')
        
        certs = cursor.fetchall()
        
        if not certs:
            print("❌ No certificates generated yet.")
            return
        
        for cert in certs:
            cert_id, user_id, cert_uuid, verify_code, device, method, created, size, duration = cert
            
            print(f"\n🎫 Certificate ID: {cert_id}")
            print(f"   User: #{user_id}")
            print(f"   UUID: {cert_uuid}")
            print(f"   ✅ VERIFICATION CODE: {verify_code}")
            print(f"   Device: {device}")
            print(f"   Method: {method}")
            print(f"   Created: {created}")
            print(f"   Size: {size} bytes")
            print(f"   Duration: {duration}s")
            print(f"   {'-'*76}")
            print(f"   🔗 Verify at: http://localhost:5000/verify")
    
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        conn.close()

def view_user_activity():
    """View user activity and statistics"""
    print_section("USER ACTIVITY - Who's Using the System")
    
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT u.id, u.username, u.phone_number, u.created_at,
                   l.license_type, l.max_wipes_per_day,
                   rl.operations_today, rl.last_reset
            FROM users u
            LEFT JOIN licenses l ON u.id = l.user_id
            LEFT JOIN rate_limits rl ON u.id = rl.user_id
            ORDER BY u.id
        ''')
        
        users = cursor.fetchall()
        
        for user in users:
            user_id, username, phone, created, lic_type, max_wipes, ops_today, last_reset = user
            
            print(f"\n👤 User #{user_id}: {username}")
            print(f"   📱 Phone: {phone}")
            print(f"   📅 Joined: {created}")
            print(f"   🎫 License: {lic_type or 'No License'}")
            print(f"   📊 Today's Operations: {ops_today or 0}/{max_wipes or 0}")
            print(f"   🔄 Last Reset: {last_reset or 'Never'}")
            
            # Count total operations by this user
            cursor.execute('SELECT COUNT(*) FROM audit_logs WHERE user_id = ?', (user_id,))
            total = cursor.fetchone()[0]
            print(f"   📈 Total Operations: {total}")
            print(f"   {'-'*76}")
    
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        conn.close()

def view_suspicious_activity():
    """View flagged suspicious activity"""
    print_section("SUSPICIOUS ACTIVITY - Security Alerts")
    
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT id, user_id, activity_type, severity, details, 
                   created_at, resolved
            FROM suspicious_activity 
            ORDER BY created_at DESC 
            LIMIT 20
        ''')
        
        activities = cursor.fetchall()
        
        if not activities:
            print("✅ No suspicious activity detected. System is secure!")
            return
        
        for activity in activities:
            act_id, user_id, act_type, severity, details, created, resolved = activity
            
            severity_icon = "🚨" if severity == "high" else "⚠️" if severity == "medium" else "ℹ️"
            status = "✅ Resolved" if resolved else "🔴 Active"
            
            print(f"\n{severity_icon} Alert ID: {act_id} - {status}")
            print(f"   User: #{user_id}")
            print(f"   Type: {act_type}")
            print(f"   Severity: {severity.upper()}")
            print(f"   Details: {details}")
            print(f"   Detected: {created}")
            print(f"   {'-'*76}")
    
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        conn.close()

def view_tos_acceptance():
    """View who accepted Terms of Service"""
    print_section("TERMS OF SERVICE - Legal Acceptance")
    
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT t.user_id, u.username, t.tos_version, 
                   t.ip_address, t.accepted_at
            FROM tos_acceptance t
            JOIN users u ON t.user_id = u.id
            ORDER BY t.accepted_at DESC
        ''')
        
        acceptances = cursor.fetchall()
        
        if not acceptances:
            print("❌ No ToS acceptances recorded.")
            return
        
        for acc in acceptances:
            user_id, username, version, ip, accepted = acc
            
            print(f"\n✅ User #{user_id}: {username}")
            print(f"   Version: {version}")
            print(f"   IP: {ip}")
            print(f"   Accepted: {accepted}")
            print(f"   {'-'*76}")
    
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        conn.close()

def search_by_user():
    """Search operations by username"""
    print_section("SEARCH BY USER")
    
    username = input("Enter username to search: ").strip()
    
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT id, operation_type, device_path, wipe_method, 
                   purpose, timestamp, success
            FROM audit_logs 
            WHERE username = ?
            ORDER BY timestamp DESC
        ''', (username,))
        
        logs = cursor.fetchall()
        
        if not logs:
            print(f"❌ No operations found for user: {username}")
            return
        
        print(f"\n✅ Found {len(logs)} operations for user: {username}\n")
        
        for log in logs:
            log_id, op_type, device, method, purpose, ts, success = log
            status = "✅" if success else "❌"
            purpose_display = purpose if purpose else "Not specified"
            
            print(f"{status} [{ts}] {device}")
            print(f"   Method: {method}")
            print(f"   Purpose: {purpose_display}")
            print(f"   {'-'*76}")
    
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        conn.close()

def main():
    """Main menu"""
    print("\n" + "="*80)
    print("🔐 CRABEX SECURITY LOG VIEWER")
    print("="*80)
    print("\nSelect an option:")
    print("1. View All Audit Logs (WHO, WHEN, WHAT, WHERE, WHY)")
    print("2. View Certificates & Verification Codes")
    print("3. View User Activity & Statistics")
    print("4. View Suspicious Activity Alerts")
    print("5. View Terms of Service Acceptance")
    print("6. Search by Username")
    print("7. View All (Complete Report)")
    print("0. Exit")
    
    choice = input("\nEnter choice (0-7): ").strip()
    
    if choice == "1":
        view_audit_logs()
    elif choice == "2":
        view_certificates()
    elif choice == "3":
        view_user_activity()
    elif choice == "4":
        view_suspicious_activity()
    elif choice == "5":
        view_tos_acceptance()
    elif choice == "6":
        search_by_user()
    elif choice == "7":
        view_audit_logs()
        view_certificates()
        view_user_activity()
        view_suspicious_activity()
        view_tos_acceptance()
    elif choice == "0":
        print("\n👋 Goodbye!")
        return
    else:
        print("\n❌ Invalid choice!")
    
    print("\n" + "="*80)
    print("✅ Security log viewing complete!")
    print("="*80)

if __name__ == "__main__":
    main()
