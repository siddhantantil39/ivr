import sqlite3
from datetime import datetime
import os
import glob

def generate_new_filename():
    """Generate a new filename with timestamp"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return f'consent_data_{timestamp}.txt'

def process_consent_data():
    """Process consent data and create a new file"""
    conn = sqlite3.connect('call_data.db')
    cursor = conn.cursor()
    
    # Updated query to include customer_name from database
    cursor.execute('''
        SELECT DISTINCT 
            account_number, 
            caller_number, 
            consent_status,
            consent_type,
            timestamp,
            customer_name  -- Added customer_name field
        FROM calls
        WHERE account_number != 'Unknown'
        AND caller_number != 'Unknown'
        AND consent_status IS NOT NULL
        AND consent_type IS NOT NULL
        ORDER BY timestamp DESC
    ''')
    
    records = cursor.fetchall()
    
    if not records:
        print("No consent records to process")
        conn.close()
        return
    
    filename = generate_new_filename()
    print(f"Creating new file: {filename}")
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write("Account_Number|Phone_Number|Customer_Name|Consent_Type|Consent_Flag|Timestamp\n")
        
        for record in records:
            account_number = record[0]
            phone_number = record[1]
            consent_type = record[3]
            consent_flag = '1' if record[2].lower() == 'opt-in' else '0'
            timestamp = record[4]
            customer_name = record[5] if record[5] != 'Unknown' else '' 
            
            line = f"{account_number}|{phone_number}|{customer_name}|{consent_type}|{consent_flag}|{timestamp}\n"
            f.write(line)
    
    print(f"Created new file with {len(records)} records")
    conn.close()
    return filename

def cleanup_old_files(keep_days=7):
    """Remove files older than specified days"""
    pattern = 'consent_data_*.txt'
    current_time = datetime.now()
    
    for file in glob.glob(pattern):
        file_time = datetime.fromtimestamp(os.path.getctime(file))
        if (current_time - file_time).days > keep_days:
            try:
                os.remove(file)
                print(f"Removed old file: {file}")
            except Exception as e:
                print(f"Error removing {file}: {str(e)}")

if __name__ == "__main__":
    print("\n=== Consent Data Processor ===")
    print(f"Starting process at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        new_file = process_consent_data()
        if new_file:
            print(f"\nMost recent entries from {new_file}:")
            with open(new_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                print(lines[0].strip())  # Header
                print("-" * 80)
                for line in lines[-5:]:  # Last 5 entries
                    print(line.strip())
        
        cleanup_old_files()
    except Exception as e:
        print(f"Error: {str(e)}")
    
    print("\nProcess complete")
    print("=" * 30)