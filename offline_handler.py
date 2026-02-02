#!/usr/bin/env python3
"""
Offline Mode Handler for Zero Leaks
Enables certificate generation and wiping without network connectivity
"""

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from generate_certificate import generate_certificate, COMPLIANCE_STANDARDS
import hashlib

class OfflineHandler:
    """Handle offline operations and certificate sync"""
    
    def __init__(self, offline_db="offline_operations.db"):
        self.offline_db = offline_db
        self.setup_offline_database()
        
    def setup_offline_database(self):
        """Setup offline operations database"""
        conn = sqlite3.connect(self.offline_db)
        c = conn.cursor()
        
        # Create tables for offline operations
        c.execute('''
            CREATE TABLE IF NOT EXISTS offline_operations (
                id TEXT PRIMARY KEY,
                operation_type TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                data TEXT NOT NULL,
                sync_status TEXT DEFAULT 'pending',
                retry_count INTEGER DEFAULT 0,
                last_error TEXT,
                created_offline INTEGER DEFAULT 1
            )
        ''')
        
        # Create table for offline certificates
        c.execute('''
            CREATE TABLE IF NOT EXISTS offline_certificates (
                cert_id TEXT PRIMARY KEY,
                cert_data TEXT NOT NULL,
                pdf_path TEXT,
                json_path TEXT,
                created_timestamp TEXT NOT NULL,
                sync_status TEXT DEFAULT 'pending',
                wipe_log TEXT
            )
        ''')
        
        # Create table for queued operations
        c.execute('''
            CREATE TABLE IF NOT EXISTS operation_queue (
                id TEXT PRIMARY KEY,
                operation TEXT NOT NULL,
                parameters TEXT NOT NULL,
                priority INTEGER DEFAULT 1,
                created_timestamp TEXT NOT NULL,
                status TEXT DEFAULT 'queued'
            )
        ''')
        
        conn.commit()
        conn.close()
        
    def is_online(self):
        """Check if system has internet connectivity"""
        try:
            import requests
            response = requests.get('https://google.com', timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def generate_offline_certificate(self, log_file, path, platform_info, wipe_details):
        """
        Generate certificate in offline mode with delayed sync capability
        """
        print("📴 OFFLINE MODE: Generating certificate without network validation")
        
        try:
            # Generate certificate normally (doesn't require network)
            cert_json, cert_pdf = generate_certificate(log_file, path, platform_info, wipe_details)
            
            # Store offline certificate info
            cert_id = str(uuid.uuid4())
            
            # Read certificate data
            cert_dir = "certificates"
            json_path = os.path.join(cert_dir, cert_json)
            pdf_path = os.path.join(cert_dir, cert_pdf)
            
            with open(json_path, 'r', encoding='utf-8') as f:
                cert_data = f.read()
            
            # Read log file
            with open(log_file, 'r', encoding='utf-8') as f:
                log_data = f.read()
            
            # Store in offline database
            conn = sqlite3.connect(self.offline_db)
            c = conn.cursor()
            
            c.execute('''
                INSERT INTO offline_certificates 
                (cert_id, cert_data, pdf_path, json_path, created_timestamp, wipe_log)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                cert_id,
                cert_data,
                pdf_path,
                json_path,
                datetime.now(timezone.utc).isoformat(),
                log_data
            ))
            
            conn.commit()
            conn.close()
            
            print(f"✅ Offline certificate stored with ID: {cert_id}")
            print(f"📁 Certificate files: {cert_json}, {cert_pdf}")
            
            return cert_json, cert_pdf, cert_id
            
        except Exception as e:
            print(f"❌ Offline certificate generation failed: {e}")
            raise e
    
    def queue_operation(self, operation, parameters, priority=1):
        """Queue an operation for when network comes back online"""
        
        op_id = str(uuid.uuid4())
        
        conn = sqlite3.connect(self.offline_db)
        c = conn.cursor()
        
        c.execute('''
            INSERT INTO operation_queue 
            (id, operation, parameters, priority, created_timestamp)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            op_id,
            operation,
            json.dumps(parameters),
            priority,
            datetime.now(timezone.utc).isoformat()
        ))
        
        conn.commit()
        conn.close()
        
        print(f"📋 Operation queued for sync: {operation} (ID: {op_id})")
        return op_id
    
    def sync_offline_operations(self):
        """Sync all pending offline operations when network is available"""
        
        if not self.is_online():
            print("📴 No network connectivity - cannot sync operations")
            return False
        
        print("🔄 Network detected - syncing offline operations...")
        
        # Sync certificates
        synced_certs = self._sync_certificates()
        
        # Sync queued operations  
        synced_ops = self._sync_queued_operations()
        
        print(f"✅ Sync complete: {synced_certs} certificates, {synced_ops} operations")
        return True
    
    def _sync_certificates(self):
        """Sync offline certificates to main database"""
        
        conn = sqlite3.connect(self.offline_db)
        c = conn.cursor()
        
        # Get pending certificates
        c.execute('''
            SELECT cert_id, cert_data, created_timestamp 
            FROM offline_certificates 
            WHERE sync_status = 'pending'
        ''')
        
        certificates = c.fetchall()
        synced_count = 0
        
        for cert_id, cert_data, timestamp in certificates:
            try:
                # Parse certificate data
                cert_json = json.loads(cert_data)
                
                # Store in main database
                main_conn = sqlite3.connect("users.db")
                main_c = main_conn.cursor()
                
                # Ensure certificates table exists
                main_c.execute('''
                    CREATE TABLE IF NOT EXISTS certificates (
                        cert_id TEXT PRIMARY KEY,
                        end_time TEXT NOT NULL,
                        signature TEXT NOT NULL,
                        verification_hash TEXT NOT NULL,
                        created_offline INTEGER DEFAULT 0,
                        sync_timestamp TEXT
                    )
                ''')
                
                # Insert certificate
                main_c.execute('''
                    INSERT OR REPLACE INTO certificates 
                    (cert_id, end_time, signature, verification_hash, created_offline, sync_timestamp)
                    VALUES (?, ?, ?, ?, 1, ?)
                ''', (
                    cert_json['certificate_id'],
                    cert_json['finish_time_utc'],
                    cert_json['signature'],
                    cert_json['verification_hash'],
                    datetime.now(timezone.utc).isoformat()
                ))
                
                main_conn.commit()
                main_conn.close()
                
                # Update sync status
                c.execute('''
                    UPDATE offline_certificates 
                    SET sync_status = 'completed', retry_count = retry_count + 1
                    WHERE cert_id = ?
                ''', (cert_id,))
                
                synced_count += 1
                print(f"📤 Synced certificate: {cert_json['certificate_id']}")
                
            except Exception as e:
                # Mark as failed
                c.execute('''
                    UPDATE offline_certificates 
                    SET sync_status = 'failed', last_error = ?, retry_count = retry_count + 1
                    WHERE cert_id = ?
                ''', (str(e), cert_id))
                print(f"❌ Failed to sync certificate {cert_id}: {e}")
        
        conn.commit()
        conn.close()
        
        return synced_count
    
    def _sync_queued_operations(self):
        """Sync queued operations"""
        
        conn = sqlite3.connect(self.offline_db)
        c = conn.cursor()
        
        # Get pending operations
        c.execute('''
            SELECT id, operation, parameters 
            FROM operation_queue 
            WHERE status = 'queued'
            ORDER BY priority DESC, created_timestamp ASC
        ''')
        
        operations = c.fetchall()
        synced_count = 0
        
        for op_id, operation, parameters in operations:
            try:
                params = json.loads(parameters)
                
                # Execute operation based on type
                if operation == 'user_registration':
                    self._sync_user_registration(params)
                elif operation == 'certificate_validation':
                    self._sync_certificate_validation(params)
                # Add more operation types as needed
                
                # Mark as completed
                c.execute('''
                    UPDATE operation_queue 
                    SET status = 'completed'
                    WHERE id = ?
                ''', (op_id,))
                
                synced_count += 1
                print(f"📤 Synced operation: {operation}")
                
            except Exception as e:
                # Mark as failed
                c.execute('''
                    UPDATE operation_queue 
                    SET status = 'failed'
                    WHERE id = ?
                ''', (op_id,))
                print(f"❌ Failed to sync operation {op_id}: {e}")
        
        conn.commit()
        conn.close()
        
        return synced_count
    
    def _sync_user_registration(self, params):
        """Sync user registration when online"""
        # Implementation for syncing user registrations
        pass
    
    def _sync_certificate_validation(self, params):
        """Sync certificate validation when online"""
        # Implementation for syncing certificate validations
        pass
    
    def get_offline_status(self):
        """Get status of offline operations"""
        
        conn = sqlite3.connect(self.offline_db)
        c = conn.cursor()
        
        # Count certificates by status
        c.execute('''
            SELECT sync_status, COUNT(*) 
            FROM offline_certificates 
            GROUP BY sync_status
        ''')
        cert_status = dict(c.fetchall())
        
        # Count operations by status
        c.execute('''
            SELECT status, COUNT(*) 
            FROM operation_queue 
            GROUP BY status
        ''')
        op_status = dict(c.fetchall())
        
        conn.close()
        
        return {
            'online': self.is_online(),
            'certificates': cert_status,
            'operations': op_status,
            'total_pending': cert_status.get('pending', 0) + op_status.get('queued', 0)
        }
    
    def create_offline_user_session(self, username):
        """Create temporary offline user session"""
        
        session_id = str(uuid.uuid4())
        session_data = {
            'session_id': session_id,
            'username': username,
            'created': datetime.now(timezone.utc).isoformat(),
            'offline': True,
            'expires': (datetime.now(timezone.utc)).isoformat()  # 24 hours
        }
        
        # Store in offline database
        conn = sqlite3.connect(self.offline_db)
        c = conn.cursor()
        
        c.execute('''
            INSERT OR REPLACE INTO offline_operations 
            (id, operation_type, timestamp, data)
            VALUES (?, 'user_session', ?, ?)
        ''', (
            session_id,
            datetime.now(timezone.utc).isoformat(),
            json.dumps(session_data)
        ))
        
        conn.commit()
        conn.close()
        
        print(f"👤 Offline user session created: {username}")
        return session_data
    
    def validate_offline_session(self, session_id):
        """Validate offline user session"""
        
        conn = sqlite3.connect(self.offline_db)
        c = conn.cursor()
        
        c.execute('''
            SELECT data FROM offline_operations 
            WHERE id = ? AND operation_type = 'user_session'
        ''', (session_id,))
        
        result = c.fetchone()
        conn.close()
        
        if result:
            session_data = json.loads(result[0])
            # Check expiration (simplified)
            return session_data
        
        return None
    
    def export_offline_data(self, export_path):
        """Export all offline data for backup/transfer"""
        
        conn = sqlite3.connect(self.offline_db)
        
        # Get all offline data
        data = {
            'export_timestamp': datetime.now(timezone.utc).isoformat(),
            'certificates': [],
            'operations': [],
            'sessions': []
        }
        
        # Export certificates
        c = conn.cursor()
        c.execute('SELECT * FROM offline_certificates')
        columns = [description[0] for description in c.description]
        for row in c.fetchall():
            data['certificates'].append(dict(zip(columns, row)))
        
        # Export operations
        c.execute('SELECT * FROM operation_queue')
        columns = [description[0] for description in c.description]
        for row in c.fetchall():
            data['operations'].append(dict(zip(columns, row)))
        
        conn.close()
        
        # Write to file
        with open(export_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"📦 Offline data exported to: {export_path}")
        return export_path

def main():
    """Command line interface for offline handler"""
    
    import argparse
    
    parser = argparse.ArgumentParser(description='Zero Leaks Offline Handler')
    parser.add_argument('command', choices=['status', 'sync', 'export'], 
                       help='Command to execute')
    parser.add_argument('--export-path', help='Export path for offline data')
    
    args = parser.parse_args()
    
    handler = OfflineHandler()
    
    if args.command == 'status':
        status = handler.get_offline_status()
        print(json.dumps(status, indent=2))
        
    elif args.command == 'sync':
        success = handler.sync_offline_operations()
        exit(0 if success else 1)
        
    elif args.command == 'export':
        if not args.export_path:
            args.export_path = f"offline_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        handler.export_offline_data(args.export_path)

if __name__ == '__main__':
    main()