import sqlite3
from tabulate import tabulate

def view_database():
    conn = sqlite3.connect('call_data.db')
    cursor = conn.cursor()
    
    def print_table(query, title):
        print(f"\n=== {title} ===")
        cursor.execute(query)
        headers = [description[0] for description in cursor.description]
        rows = cursor.fetchall()
        print(tabulate(rows, headers=headers, tablefmt="grid"))
    
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
    
    # Recent Calls
    print_table("""
        SELECT call_sid, caller_number, customer_name, account_number, issue_description
        FROM calls 
        ORDER BY timestamp DESC 
        LIMIT 5
    """, "Recent Calls")
    
    # Priority Distribution
    print_table("""
        SELECT priority, COUNT(*) as count 
        FROM calls 
        GROUP BY priority
    """, "Priority Distribution")
    
    # Issue Types
    print_table("""
        SELECT issue_type, COUNT(*) as count 
        FROM calls 
        GROUP BY issue_type
    """, "Issue Types")
    
    conn.close()

if __name__ == "__main__":
    view_database()