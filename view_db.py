import sqlite3
from tabulate import tabulate
from datetime import datetime

def view_database():
    conn = sqlite3.connect('call_data.db')
    cursor = conn.cursor()
    
    def print_table(query, title):
        print(f"\n=== {title} ===")
        try:
            cursor.execute(query)
            headers = [description[0] for description in cursor.description]
            rows = cursor.fetchall()
            if rows:
                print(tabulate(rows, headers=headers, tablefmt="grid"))
            else:
                print("No data found")
        except sqlite3.Error as e:
            print(f"Error executing query: {e}")

        # Recent OTPs
    print_table("""
        SELECT phone_number, otp, created_at, verified 
        FROM otp_verification 
        ORDER BY created_at DESC 
        LIMIT 5
    """, "Recent OTP Verifications")
    
    # OTP Statistics
    print_table("""
        SELECT 
            COUNT(*) as total_otps,
            SUM(CASE WHEN verified = 1 THEN 1 ELSE 0 END) as verified_otps,
            SUM(CASE WHEN verified = 0 THEN 1 ELSE 0 END) as pending_otps
        FROM otp_verification
    """, "OTP Statistics")
    
    # Recent Calls with Consent Info
    print_table("""
        SELECT 
            call_sid,
            caller_number,
            customer_name,
            account_number,
            substr(full_transcript, 1, 50) || '...' as transcript_preview,
            consent_type,
            consent_status,
            timestamp
        FROM calls 
        ORDER BY timestamp DESC 
        LIMIT 5
    """, "Recent Calls with Consent Information")
    
    # Consent Status Distribution
    print_table("""
        SELECT 
            consent_status,
            COUNT(*) as count,
            ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM calls), 2) as percentage
        FROM calls 
        GROUP BY consent_status
    """, "Consent Status Distribution")
    
    # Consent Type Distribution
    print_table("""
        SELECT 
            consent_type,
            COUNT(*) as count
        FROM calls 
        GROUP BY consent_type
    """, "Consent Type Distribution")
    
    # Daily Call Volume
    print_table("""
        SELECT 
            date(timestamp) as call_date,
            COUNT(*) as call_count
        FROM calls 
        GROUP BY date(timestamp)
        ORDER BY call_date DESC
        LIMIT 7
    """, "Daily Call Volume (Last 7 Days)")
    
    # Unknown Information Stats
    print_table("""
        SELECT 
            SUM(CASE WHEN customer_name = 'Unknown' THEN 1 ELSE 0 END) as unknown_names,
            SUM(CASE WHEN account_number = 'Unknown' THEN 1 ELSE 0 END) as unknown_accounts,
            SUM(CASE WHEN consent_status = 'Unknown' THEN 1 ELSE 0 END) as unknown_consent
        FROM calls
    """, "Unknown Information Statistics")
    
    # System Performance
    print_table("""
        SELECT 
            COUNT(*) as total_calls,
            AVG(LENGTH(full_transcript)) as avg_transcript_length,
            COUNT(DISTINCT caller_number) as unique_callers
        FROM calls
    """, "System Performance Metrics")
    
    conn.close()

if __name__ == "__main__":
    print(f"\nDatabase View Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    view_database()
    print("\nEnd of Report")
    print("=" * 80)