import sys
import gam

# ==========================================
# CONFIGURATION
# ==========================================
DOMAIN = "auhsdschools.org"
DEFAULT_PASSWORD = "Disney1901"

def execute_gam(command_list, description):
    """Executes a GAM command via the gam module and checks for errors."""
    print(description)
    status = gam.CallGAMCommand(command_list)
    if status != 0:
        print(f"   [!] GAM returned an error (status {status}) for the last command.")
        return False
    return True

def main():
    print("=== Google Workspace User Creation Tool ===\n")

    # ==========================================
    # GATHER USER INPUT
    # ==========================================
    first_name = input("Enter First Name: ").strip()
    last_name = input("Enter Last Name: ").strip()

    if not first_name or not last_name:
        print("Error: First and last names cannot be blank.")
        sys.exit(1)

    # Prompt for password visibly
    user_password = input(f"Enter Password (leave blank for default '{DEFAULT_PASSWORD}'): ").strip()
    if not user_password:
        user_password = DEFAULT_PASSWORD

    # Convert to lowercase, extract first initial, and create username
    first_initial = first_name.lower()[0]
    last_name_lower = last_name.lower()
    username = f"{first_initial}{last_name_lower}@{DOMAIN}"

    print(f"\nGenerated Username: {username}\n")

    # ==========================================
    # SCHOOL SELECTION MENU
    # ==========================================
    print("Select the school for this user:")
    print("1) AHS")
    print("2) MHS")
    print("3) CHS")
    print("4) LLHS")
    print("5) ACIS")
    
    choice = input("Enter choice [1-5]: ").strip()
    
    schools = {
        "1": "AHS",
        "2": "MHS",
        "3": "CHS",
        "4": "LLHS",
        "5": "CIS"
    }

    if choice not in schools:
        print("Invalid choice. Exiting script.")
        sys.exit(1)
        
    school_name = schools[choice]

    # ==========================================
    # ADMINISTRATOR CHECK & OU ASSIGNMENT
    # ==========================================
    print()
    is_admin_input = input(f"Is this user an AUHSD Domain user at {school_name}? (y/n): ").strip().lower()
    
    # Modify the OU path based on the administrator answer
    if is_admin_input in ['y', 'yes']:
        ou_path = f"/AUHSD/AUHSD Staff/{school_name}"
        print(f"User flagged as Administrator. Assigned OU: {ou_path}")
    else:
        ou_path = f"/Staff/Acad Staff/{school_name}"
        print(f"User flagged as standard Staff. Assigned OU: {ou_path}")
        # Now figure out if they are a teacher or not
        is_teacher_input = input(f"Is this user a teacher? (y/n)").strip().lower()
        if is_teacher_input in ['y','yes']:
            group1 = f"{school_name.lower()}certificatedstaff@{DOMAIN}"
        else:
            group1 = f"{school_name.lower()}classifiedstaff@{DOMAIN}"

    # Dynamically generate group addresses
    # always add acadstaff and classroom_teachers
    group2 = f"{school_name.lower()}acadstaff@{DOMAIN}"
    group3 = f"classroom_teachers@{DOMAIN}"
    print()

    # ==========================================
    # EXECUTE GAM COMMANDS VIA PYTHON MODULE
    # ==========================================
    
    # Create User
    create_cmd = [
        'gam', 'create', 'user', username,
        'firstname', first_name,
        'lastname', last_name,
        'org', ou_path,
        'password', user_password,
        'changepassword', 'on'
    ]
    execute_gam(create_cmd, f"-> Creating Google Workspace user: {username} in OU: {ou_path}")

    # Add to Certificated Group
    group1_cmd = [
        'gam', 'update', 'group', group1, 
        'add', 'member', 'user', username
    ]
    execute_gam(group1_cmd, f"\n-> Adding {username} to {group1}...")

    # Add to Acad Group
    group2_cmd = [
        'gam', 'update', 'group', group2, 
        'add', 'member', 'user', username
    ]
    # Add to classroom teachers

    execute_gam(group2_cmd, f"\n-> Adding {username} to {group2}...")

    group3_cmd = [
            'gam', 'update', 'group', group3, 
            'add', 'member', 'user', username
        ]
    execute_gam(group3_cmd, f"\n-> Adding {username} to {group3}...")
        

    print("\nAccount creation and group assignments complete!")

if __name__ == "__main__":
    main()