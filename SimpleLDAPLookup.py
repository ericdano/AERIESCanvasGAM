from ldap3 import Server, Connection, ALL
from pathlib import Path
import io, ftplib, ssl, sys, os, datetime, json, smtplib, logging
from sqlalchemy.engine import URL


if __name__ == '__main__':
    confighome = Path.home() / ".Acalanes" / "Acalanes.json"
    with open(confighome) as f:
        configs = json.load(f)
    # 1. Configuration
    # Connect to the Root Domain Controller using the Global Catalog port
    GC_SERVER = 'ldap://acalanes.k12.ca.us:3268' 
    SEARCH_BASE = 'DC=acalanes,DC=k12,DC=ca,DC=us'
    BIND_USER = 'tech@acalanes.k12.ca.us'
    BIND_PASSWORD = configs['ADPassword']

    # 2. Setup Server and Connection
    server = Server(GC_SERVER, get_info=ALL)

    with Connection(server, user=BIND_USER, password=BIND_PASSWORD, auto_bind=True) as conn:
        # This filter looks for active users missing an employeeID
        search_filter = '(&(objectCategory=person)(objectClass=user)(!employeeID=*))'
        
        print(f"Searching for missing employeeIDs across the forest...")
        
        # Perform the search
        conn.search(
            search_base=SEARCH_BASE,
            search_filter=search_filter,
            attributes=['cn', 'distinguishedName', 'sAMAccountName']
        )

        # 3. Process Results
        if not conn.entries:
            print("No users found with missing employeeID.")
        else:
            print(f"Found {len(conn.entries)} total users:\n")
            print(f"{'Username':<20} | {'Domain':<30}")
            print("-" * 55)
            
            for entry in conn.entries:
                dn = entry.distinguishedName.value
                # Determine domain by looking at the DN
                domain = "Staff" if "DC=staff" in dn.lower() else "Root"
                print(f"{entry.sAMAccountName.value:<20} | {domain}")