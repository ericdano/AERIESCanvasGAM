from ldap3 import Server, Connection, ALL, NTLM, SUBTREE
from pathlib import Path
import json

def load_config():
    """Loads credentials from your existing JSON file."""
    confighome = Path.home() / ".Acalanes" / "Acalanes.json"
    with open(confighome) as f:
        return json.load(f)

def test_ad_query():
    configs = load_config()
    
    # --- CONFIGURATION TO TEST ---
    ad_server = configs['AD_STU_Server']
    # You mentioned trying UPN vs NetBIOS. Try AUHSD\\tech first. 
    # If it fails, change to tech@student.acalanes.k12.ca.us
    ad_user = 'AUHSD\\tech' 
    ad_password = configs['ADPassword']
    
    # Hardcoded to the exact string you provided
    search_base = 'OU=Students,DC=student,DC=acalanes,DC=k12,DC=ca,DC=us'
    
    print(f"Connecting to Server: {ad_server}")
    print(f"Using Account: {ad_user}")
    print(f"Searching Base: {search_base}")
    print("-" * 40)

    try:
        # 1. Connect to Server
        server = Server(ad_server, get_info=ALL)
        
        # 2. Bind to Active Directory
        conn = Connection(
            server, 
            user=ad_user, 
            password=ad_password, 
            authentication=NTLM, 
            auto_bind=True
        )
        print("[SUCCESS] Bound to Active Directory.")
        
        # 3. Perform the Search
        # paged_size=1000 is REQUIRED if there are more than 1000 students!
        print("Querying accounts... (this might take a few seconds)")
        conn.search(
            search_base=search_base,
            search_filter='(&(objectCategory=person)(objectClass=user))',
            search_scope=SUBTREE,
            attributes=['sAMAccountName', 'givenName', 'sn'],
            paged_size=1000 
        )
        
        # 4. Process Results
        entries = conn.entries
        total_found = len(entries)
        
        if total_found == 0:
            print("\n[WARNING] Query succeeded, but 0 students were found.")
            print("Check if the OU path is exactly correct, or if the tech account lacks Read permissions.")
        else:
            print(f"\n[SUCCESS] Found {total_found} student accounts!")
            print("Here are the first 10 accounts found:")
            
            # Print the first 10 accounts as a sample
            for entry in entries[:10]:
                sam = entry.sAMAccountName.value if 'sAMAccountName' in entry else 'N/A'
                first = entry.givenName.value if 'givenName' in entry else 'N/A'
                last = entry.sn.value if 'sn' in entry else 'N/A'
                print(f" - {sam}: {first} {last}")
                
    except Exception as e:
        print("\n[ERROR] Connection or Query Failed!")
        print(str(e))
        
    finally:
        if 'conn' in locals() and conn.bound:
            conn.unbind()

if __name__ == "__main__":
    test_ad_query()