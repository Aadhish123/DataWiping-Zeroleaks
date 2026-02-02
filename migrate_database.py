import sqlite3
from datetime import datetime

def migrate_database():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    # Get existing columns
    cursor.execute("PRAGMA table_info(users)")
    existing_columns = [row[1] for row in cursor.fetchall()]
    print(f"Existing columns: {existing_columns}")
    
    # Define columns to add
    columns_to_add = [
        ('is_verified', 'INTEGER DEFAULT 0'),
        ('verification_level', 'TEXT DEFAULT "unverified"'),
        ('account_status', 'TEXT DEFAULT "active"'),
        ('created_at', 'TEXT'),
        ('last_login', 'TEXT'),
        ('daily_wipe_limit', 'INTEGER DEFAULT 3'),
        ('total_wipes', 'INTEGER DEFAULT 0')
    ]
    
    # Add missing columns
    for col_name, col_def in columns_to_add:
        if col_name not in existing_columns:
            try:
                cursor.execute(f'ALTER TABLE users ADD COLUMN {col_name} {col_def}')
                print(f'✓ Added column: {col_name}')
            except sqlite3.OperationalError as e:
                print(f'✗ Failed to add {col_name}: {e}')
        else:
            print(f'→ Column already exists: {col_name}')
    
    # Set created_at for existing records
    cursor.execute('UPDATE users SET created_at = ? WHERE created_at IS NULL', 
                  (datetime.now().strftime('%Y-%m-%d %H:%M:%S'),))
    
    conn.commit()
    conn.close()
    print('\n✓ Database migration completed!')

if __name__ == '__main__':
    migrate_database()
