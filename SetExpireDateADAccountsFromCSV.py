import csv
import subprocess

# --- Configuration ---
CSV_FILE_PATH = 'users.csv'
EXPIRATION_DATE = '06/10/2026' # Format: MM/DD/YYYY
TARGET_GROUP = 'VoIPUsers'
GROUP_SERVER = 'zeus.acalanes.k12.ca.us' # The server where the group resides

# List of Domain Controllers to iterate through
DOMAIN_CONTROLLERS = [
    'hector.acalanes.k12.ca.us',
    'zeus.acalanes.k12.ca.us'
]

def attempt_update(sam_account_name, date, server):
    """
    Attempts to update the user on a specific server.
    Returns a tuple: (Success_Boolean, Error_Message)
    """
    # The PowerShell command now includes a fallback block to handle cross-domain 
    # Foreign Security Principals (FSPs) if direct SID removal fails.
    ps_command = (
        "$ErrorActionPreference = 'Stop'; "
        "Import-Module ActiveDirectory; "
        f"$user = Get-ADUser -Identity '{sam_account_name}' -Server '{server}'; "
        f"Set-ADAccountExpiration -Identity $user -DateTime '{date} 23:59:59' -Server '{server}'; "
        f"Set-ADUser -Identity $user -Clear 'ipphone','pager','telephonenumber' -Server '{server}'; "
        f"try {{ Remove-ADGroupMember -Identity '{TARGET_GROUP}' -Members $user.SID.Value -Server '{GROUP_SERVER}' -Confirm:$false -ErrorAction Stop }} "
        f"catch {{ "
        f"    $members = Get-ADGroupMember -Identity '{TARGET_GROUP}' -Server '{GROUP_SERVER}' -ErrorAction SilentlyContinue; "
        f"    $match = $members | Where-Object {{ $_.SID.Value -eq $user.SID.Value }}; "
        f"    if ($match) {{ Remove-ADGroupMember -Identity '{TARGET_GROUP}' -Members $match -Server '{GROUP_SERVER}' -Confirm:$false -ErrorAction Stop }} "
        f"}}; "
        "exit 0" 
    )
    
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_command],
            capture_output=True,
            text=True,
            check=True
        )
        return True, ""
        
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.strip() if e.stderr else e.stdout.strip()
        if not error_msg:
             error_msg = "Unknown PowerShell Error"
        return False, error_msg

def main():
    print("Starting Active Directory account update...")
    print(f"Target expiration date: {EXPIRATION_DATE}")
    print(f"Target group removal: {TARGET_GROUP} (Hosted on {GROUP_SERVER})\n")
    
    try:
        with open(CSV_FILE_PATH, mode='r', encoding='utf-8-sig') as file:
            reader = csv.DictReader(file)
            
            if 'SamAccountName' not in reader.fieldnames:
                print("[ERROR] The CSV must contain a 'SamAccountName' header.")
                return

            for row in reader:
                username = row.get('SamAccountName', '').strip()
                
                if username:
                    found = False
                    server_errors = {}
                    
                    for dc in DOMAIN_CONTROLLERS:
                        success, error_message = attempt_update(username, EXPIRATION_DATE, dc)
                        
                        if success:
                            print(f"[SUCCESS] Updated '{username}' on server: {dc}")
                            found = True
                            break
                        else:
                            server_errors[dc] = error_message
                            
                    if not found:
                        print(f"[WARNING] User '{username}' failed to update.")
                        print(f"   -> Hector error: {server_errors.get('hector.acalanes.k12.ca.us')}")
                        print(f"   -> Zeus error: {server_errors.get('zeus.acalanes.k12.ca.us')}")
                else:
                    print("[WARNING] Skipped an empty row in the CSV.")
                    
    except FileNotFoundError:
        print(f"[ERROR] Could not find the file: {CSV_FILE_PATH}.")
    except Exception as e:
        print(f"[ERROR] An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()