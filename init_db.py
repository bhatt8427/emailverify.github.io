import sqlite3

def init_database():
    """Initialize the SQLite database for caching verification results."""
    conn = sqlite3.connect('email_verification.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS verification_cache (
            email TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            reason TEXT,
            score INTEGER,
            provider TEXT,
            risk_level TEXT,
            checks TEXT,
            verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP
        )
    ''')
    
    # Create index for faster lookups
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_email ON verification_cache(email)
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_expires ON verification_cache(expires_at)
    ''')
    
    conn.commit()
    conn.close()
    print("Database initialized successfully!")

if __name__ == '__main__':
    init_database()
