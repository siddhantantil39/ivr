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