import csv
import sys
import os
import ldap3
from ldap3 import Server, Connection, ALL, MODIFY_ADD
import win32security
import ntsecuritycon as con

'''
Script to create Student Accounts in Active Directory


'''



def set_directory_permissions(path, username):
    """Sets Full Control permissions for the user on their home directory."""
    try:
        sd = win32security.GetFileSecurity(path, win32security.DACL_SECURITY_INFORMATION)
        dacl = sd.GetSecurityDescriptorDacl()
        
        # Get the SID for the user
        user_sid, domain, type = win32security.LookupAccountName(None, username)
        
        # Add Full Control Access Allowed ACE
        # ContainerInherit | ObjectInherit = 3
        dacl.AddAccessAllowedAceEx(win32security.ACL_REVISION, 3, con.FILE_ALL_ACCESS, user_sid)
        
        sd.SetSecurityDescriptorDacl(1, dacl, 0)
        win32security.SetFileSecurity(path, win32security.DACL_SECURITY_INFORMATION, sd)
        print(f"Permissions set for {username} on {path}")
    except Exception as e:
        print(f"Error setting permissions: {e}")

def main(csv_file):
    # LDAP Server Configuration
    server_name = 'socrates'
    # Note: Ensure you have credentials with AD write privileges
    server = Server(server_name, get_info=ALL)
    
    # Using auto_bind for NTLM (Windows Auth) - assumes script runs as Admin
    with Connection(server, authentication=ldap3.NTLM, auto_bind=True) as conn:
        
        with open(csv_file, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                # Map CSV columns to variables
                sam_name = row['STUID']
                display_name = f"{row['LN']}, {row['FN']}"
                dn = f"CN={row['DISPLAYNAME']},OU={row['OU1']},OU=Students,DC=student,DC=acalanes,DC=k12,DC=ca,DC=us"
                home_dir = row['HDrive']

                # Create User Attributes
                attrs = {
                    'sAMAccountName': sam_name,
                    'givenName': row['FN'],
                    'sn': row['LN'],
                    'displayName': display_name,
                    'userPrincipalName': f"{sam_name}@student.acalanes.k12.ca.us", # Adjusted based on typical UPN logic
                    'homeDrive': 'H:',
                    'homeDirectory': home_dir,
                    'description': row['Description'],
                    'userAccountControl': 544, # Enabled (512) + Password Not Required/Never Expires logic
                }

                # 1. Create the User
                if conn.add(dn, attributes=attrs):
                    print(f"User {sam_name} created successfully.")
                    
                    # 2. Set Password (requires LDAPS/SSL in most AD environments)
                    conn.extend.microsoft.change_password(dn, row['PASSWORD'])
                    
                    # 3. Add to Groups
                    for group_key in ['Group1', 'Group2']:
                        group_dn = f"CN={row[group_key]},OU=Groups,DC=student,DC=acalanes,DC=k12,DC=ca,DC=us" # Adjust Group DN path as needed
                        conn.modify(group_dn, {'member': [(MODIFY_ADD, [dn])]})

                    # 4. Handle Home Directory
                    if not os.path.exists(home_dir):
                        os.makedirs(home_dir)
                        set_directory_permissions(home_dir, sam_name)
                else:
                    print(f"Failed to create {sam_name}: {conn.result}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python CreateStudentAccounts.py <path_to_csv>")
    else:
        main(sys.argv[1])