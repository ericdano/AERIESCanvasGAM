import os
import sys
import json
import time
import requests
import pynetbox
import re
from pathlib import Path
from pyzabbix import ZabbixAPI

# ==========================================
# Configuration & Credentials
# ==========================================
confighome = Path.home() / ".Acalanes" / "Acalanes.json"

try:
    with open(confighome, 'r') as f:
        configs = json.load(f)
        
    # Cambium Config
    CAMBIUM_BASE_URL = configs.get('CambiumAPI_URL') 
    CAMBIUM_CLIENT_ID = configs.get('CambiumAPI_ClientID')
    CAMBIUM_CLIENT_SECRET = configs.get('CambiumAPI_ClientSecret')

    # NetBox Config
    NETBOX_URL = configs.get('NetBox_URL')
    NETBOX_TOKEN = configs.get('NetBox_Token')
    
    # Zabbix Config
    ZABBIX_URL = configs.get('Zabbix_URL')
    ZABBIX_TOKEN = configs.get('Zabbix_Token')
    
except Exception as e:
    print(f"Config load error: {e}", file=sys.stderr)
    sys.exit(1)

# ==========================================
# Cambium Functions
# ==========================================

def get_access_token(base_url, client_id, client_secret):
    """Authenticates and retrieves the token and API redirect URI."""
    token_url = f"{base_url}/api/v2/access/token"
    payload = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    
    response = requests.post(token_url, data=payload, headers=headers, timeout=10)
    response.raise_for_status() 
    
    data = response.json()
    return data.get("access_token"), data.get("redirect_uri", base_url)

def get_cambium_aps(base_url, client_id, client_secret, api_server_url, initial_token):
    """Fetches paginated APs from Cambium Cloud."""
    endpoint_url = f"{api_server_url}/api/v2/devices"
    
    token = initial_token
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }
    
    ap_list = []
    offset = 0
    limit = 100  
    
    print("Fetching APs from Cambium Cloud...", flush=True)

    while True:
        params = {
            "limit": limit,
            "offset": offset
        }
        
        print(f"  -> Pulling devices {offset} to {offset + limit}...", flush=True)
        response = requests.get(endpoint_url, headers=headers, params=params, timeout=15)
        
        # --- Token Expiration Handler (401) ---
        if response.status_code == 401:
            print("\n  --> Token expired! Re-authenticating on the fly...", flush=True)
            token, _ = get_access_token(base_url, client_id, client_secret)
            headers["Authorization"] = f"Bearer {token}"
            print("  --> Resuming download...\n", flush=True)
            continue  
            
        # --- Rate Limit Handler (429) ---
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 60))
            print(f"  --> Rate limit hit! Pausing for {retry_after} seconds before retrying...", flush=True)
            time.sleep(retry_after)
            continue  
            
        response.raise_for_status()
        
        data = response.json()
        raw_devices = data.get("data", [])
        
        if not raw_devices:
            break
            
        # Transform and filter for Wi-Fi APs on the fly
        for device in raw_devices:
            if "wifi" in device.get("type", ""): 
                ap_list.append({
                    "hostname": device.get("name"),
                    "ip_address": device.get("ip"),
                    "serial": device.get("msn"), # Using MSN for NetBox
                    "mac": device.get("mac"),    
                    "model": device.get("product"),
                    "site": device.get("site")   
                })
        
        total_devices = data.get("paging", {}).get("total", 0)
        if offset + limit >= total_devices:
            break
            
        offset += limit
        time.sleep(1.0) 
        
    print(f"Found {len(ap_list)} APs.")
    return ap_list

# ==========================================
# NetBox & Zabbix Functions
# ==========================================
def assign_ip_to_netbox_device(nb, device, ip_address):
    """Creates an interface, assigns the IP, and sets it as Primary IPv4."""
    if not ip_address:
        return

    # NetBox requires CIDR notation. Defaulting to /24.
    ip_cidr = f"{ip_address}/24"
    interface_name = "wlan0"

    # 1. Ensure an interface exists on the device
    interface = nb.dcim.interfaces.get(device_id=device.id, name=interface_name)
    if not interface:
        interface = nb.dcim.interfaces.create(
            device=device.id, 
            name=interface_name, 
            type="other" # "other" or "ieee802.11ax" for WiFi
        )

    # 2. Ensure the IP exists in IPAM and is assigned to the interface
    ip_obj = nb.ipam.ip_addresses.get(address=ip_cidr)
    if ip_obj:
        # If the IP exists but is assigned elsewhere, move it here
        if getattr(ip_obj, 'assigned_object_id', None) != interface.id:
            ip_obj.assigned_object_type = "dcim.interface"
            ip_obj.assigned_object_id = interface.id
            ip_obj.save()
    else:
        # Create the IP if it doesn't exist at all
        ip_obj = nb.ipam.ip_addresses.create(
            address=ip_cidr,
            assigned_object_type="dcim.interface",
            assigned_object_id=interface.id
        )

    # 3. Set as primary IPv4 on the device if it isn't already
    current_primary = getattr(device, 'primary_ip4', None)
    if not current_primary or current_primary.id != ip_obj.id:
        device.primary_ip4 = ip_obj.id
        device.save()
        print(f"    [NetBox] Assigned {ip_cidr} as Primary IPv4.")

def sync_to_netbox(aps):
    """Syncs the extracted APs into NetBox, auto-creating Device Types as needed."""
    print("\nSyncing to NetBox...")
    nb = pynetbox.api(NETBOX_URL, token=NETBOX_TOKEN)

    # Hardcoded based on your specific instance configuration
    DEVICE_ROLE_ID = 2   

    # 1. Dynamically cache all NetBox Sites
    print("  -> Caching NetBox Sites...")
    netbox_sites = {site.name: site.id for site in nb.dcim.sites.all()}
    
    # 2. Dynamically cache Device Types
    print("  -> Caching Device Types...")
    netbox_device_types = {dt.model: dt.id for dt in nb.dcim.device_types.all()}

    # 3. Ensure the Manufacturer "Cambium Networks" exists
    manufacturer_name = "Cambium Networks"
    manuf = nb.dcim.manufacturers.get(name=manufacturer_name)
    if not manuf:
        print(f"  [NetBox] Creating Manufacturer: {manufacturer_name}...")
        manuf = nb.dcim.manufacturers.create(
            name=manufacturer_name, 
            slug="cambium-networks"
        )
    manuf_id = manuf.id

    # Translation Map: "Name in Cambium": "Exact Name in NetBox"
    SITE_TRANSLATOR = {
        "Acalanes": "Acalanes High School",    # Update these right-side values!
        "Miramonte": "Miramonte High School",
        "Las Lomas": "Las Lomas High School",
        "Campolindo": "Campolindo High School",
        "": "Unknown Site"                     # Catch APs with no site in Cambium
    }

    # 4. Loop through the APs

    for ap in aps:
        if not ap["hostname"]:
            continue
            
        # --- Match the Site with Translation ---
        raw_cambium_site = ap.get("site", "")
        # Translate it if it's in our dictionary, otherwise use the raw name
        netbox_site_name = SITE_TRANSLATOR.get(raw_cambium_site, raw_cambium_site) 
        site_id = netbox_sites.get(netbox_site_name)

        if not site_id:
            print(f" [Warning] Skipping {ap['hostname']}: Translated Site '{netbox_site_name}' not found in NetBox.")
            continue

        # --- Match or Create the Device Type ---
        model_name = ap.get("model", "Unknown Model")
        device_type_id = netbox_device_types.get(model_name)

        if not device_type_id:
            print(f"  [NetBox] Auto-creating new Device Type for model: {model_name}...")
            model_slug = re.sub(r'[^a-z0-9]+', '-', model_name.lower()).strip('-')
            
            new_dt = nb.dcim.device_types.create(
                manufacturer=manuf_id,
                model=model_name,
                slug=model_slug,
                u_height=0 
            )
            device_type_id = new_dt.id
            netbox_device_types[model_name] = device_type_id
        # --- Check for existing device ---
        existing_device = nb.dcim.devices.get(name=ap["hostname"])

        if existing_device:
            print(f" [NetBox] {ap['hostname']} already exists. Updating...")
            existing_device.serial = ap["serial"]
            existing_device.site = site_id 
            existing_device.device_type = device_type_id
            existing_device.save()
            
            # --- ADD THIS LINE ---
            assign_ip_to_netbox_device(nb, existing_device, ap.get("ip_address"))
            
        else:
            print(f" [NetBox] Creating {ap['hostname']} ({model_name}) at {netbox_site_name}...")
            try:
                new_device = nb.dcim.devices.create(  # <-- Changed to 'new_device ='
                    name=ap["hostname"],
                    site=site_id,
                    device_type=device_type_id,
                    role=DEVICE_ROLE_ID,
                    serial=ap["serial"]
                )
                
                # --- ADD THIS LINE ---
                assign_ip_to_netbox_device(nb, new_device, ap.get("ip_address"))
                
            except pynetbox.RequestError as e:
                print(f"Failed to create {ap['hostname']} in NetBox: {e.error}")

def sync_to_zabbix(aps):
    """Syncs the extracted APs into Zabbix 7, assigning main and site-specific host groups."""
    print("\nSyncing to Zabbix...")
    zapi = ZabbixAPI(ZABBIX_URL)
    zapi.login(api_token=ZABBIX_TOKEN) # <--- Changed this line!

    TEMPLATE_ID = "11018" 
    MAIN_HOST_GROUP_ID = "74"

    # Map the raw Cambium Site names to your Zabbix Host Group IDs
    # (Adjust the left-side string if Cambium spells DO, DV, or SC differently)
    ZABBIX_SITE_MAP = {
        "Acalanes": "75",
        "Campolindo": "68",
        "District Office": "70",
        "Del Valle": "67",
        "Service Center": "72",
        "Miramonte": "69",
        "Las Lomas": "71"
    }

    for ap in aps:
        if not ap["hostname"]:
            continue
            
        # 1. Determine the correct Zabbix Groups for this specific AP
        groups = [{"groupid": MAIN_HOST_GROUP_ID}] # Always put in the Master AP group
        
        raw_cambium_site = ap.get("site", "")
        site_group_id = ZABBIX_SITE_MAP.get(raw_cambium_site)
        
        if site_group_id:
            groups.append({"groupid": site_group_id}) # Add the site-specific group
        else:
            # If the site is blank or misspelled in Cambium, it just stays in 74
            print(f"  [Zabbix Warning] Site '{raw_cambium_site}' not mapped. Assigning to Main Group 74 only.")

        # 2. Check if host already exists
        existing_host = zapi.host.get(filter={"host": ap["hostname"]})

        if existing_host:
            print(f" [Zabbix] {ap['hostname']} already monitored. Updating groups/IP...")
            try:
                host_id = existing_host[0]["hostid"]
                # Update the host to ensure it's in the correct site group
                # Zabbix host.update allows us to pass the 'groups' and 'interfaces' array to overwrite old data
                
                # First, we need the existing interface ID to update the IP cleanly
                interfaces = zapi.hostinterface.get(hostids=host_id)
                if interfaces:
                    interface_id = interfaces[0]["interfaceid"]
                    zapi.hostinterface.update(
                        interfaceid=interface_id, 
                        ip=ap["ip_address"] or "0.0.0.0"
                    )

                # Update the groups
                zapi.host.update(
                    hostid=host_id,
                    groups=groups
                )
            except Exception as e:
                print(f"Failed to update {ap['hostname']} in Zabbix: {e}")
        else:
            print(f" [Zabbix] Adding {ap['hostname']}...")
            try:
                zapi.host.create({
                    "host": ap["hostname"],
                    "interfaces": [{
                        "type": 2, # 2 = SNMP
                        "main": 1,
                        "useip": 1,
                        "ip": ap["ip_address"] or "0.0.0.0", 
                        "dns": "",
                        "port": "161",
                        "details": {
                            "version": 2, 
                            "community": "zabbixv2" # was public Make sure this matches your SNMP string!
                        }
                    }],
                    "groups": groups,
                    "templates": [{"templateid": TEMPLATE_ID}]
                })
            except Exception as e:
                 print(f"Failed to add {ap['hostname']} to Zabbix: {e}")

def cleanup_orphaned_aps(aps):
    """Marks APs as Offline/Disabled if they exist in NetBox/Zabbix but not in Cambium."""
    print("\nChecking for orphaned APs to clean up...")
    
    # Create a fast-lookup set of active Cambium hostnames
    active_cambium_hostnames = {ap["hostname"] for ap in aps if ap["hostname"]}
    
    # ==========================================
    # NetBox Cleanup
    # ==========================================
    print("  -> Checking NetBox for missing APs...")
    nb = pynetbox.api(NETBOX_URL, token=NETBOX_TOKEN)
    DEVICE_ROLE_ID = 2 # Your Access Point Role ID
    
    try:
        # Fetch all devices in NetBox that are assigned the Access Point role
        netbox_aps = nb.dcim.devices.filter(role_id=DEVICE_ROLE_ID)
        for nb_ap in netbox_aps:
            if nb_ap.name not in active_cambium_hostnames:
                # If it's missing from Cambium and not already offline, update it
                if getattr(nb_ap.status, 'value', '') != 'offline':
                    print(f"    [NetBox] Marking {nb_ap.name} as OFFLINE (Missing from Cambium).")
                    nb_ap.status = 'offline'
                    nb_ap.save()
            else:
                # Optional: If it comes BACK online in Cambium, mark it active again in NetBox!
                if getattr(nb_ap.status, 'value', '') == 'offline':
                    print(f"    [NetBox] Marking {nb_ap.name} as ACTIVE (Restored in Cambium).")
                    nb_ap.status = 'active'
                    nb_ap.save()
                    
    except pynetbox.RequestError as e:
        print(f"Failed during NetBox cleanup: {e}")
    # ==========================================
    # Zabbix Cleanup
    # ==========================================
    print("  -> Checking Zabbix for missing APs...")
    zapi = ZabbixAPI(ZABBIX_URL)
    zapi.login(api_token=ZABBIX_TOKEN)
    
    ZABBIX_MASTER_GROUP_ID = "74"
    
    try:
        zabbix_aps = zapi.host.get(groupids=ZABBIX_MASTER_GROUP_ID, output=["hostid", "host", "status"])
        for z_ap in zabbix_aps:
            if z_ap["host"] not in active_cambium_hostnames:
                # In Zabbix: status '0' is Enabled, '1' is Disabled
                if z_ap["status"] == "0":
                    print(f"    [Zabbix] Disabling monitoring for {z_ap['host']} (Missing from Cambium).")
                    zapi.host.update(hostid=z_ap["hostid"], status=1)
            else:
                if z_ap["status"] == "1":
                    print(f"    [Zabbix] Re-enabling monitoring for {z_ap['host']} (Restored in Cambium).")
                    zapi.host.update(hostid=z_ap["hostid"], status=0)
                    
    except Exception as e:
         print(f"Failed during Zabbix cleanup: {e}")

# ==========================================
# Main Execution
# ==========================================
if __name__ == "__main__":
    print("Starting integration script...\n")
    
    try:
        # 1. Authenticate
        print("Authenticating with Cambium...", flush=True)
        initial_token, api_server_url = get_access_token(CAMBIUM_BASE_URL, CAMBIUM_CLIENT_ID, CAMBIUM_CLIENT_SECRET)
        api_server_url = api_server_url.rstrip('/')
        
        # 2. Extract & Transform
        my_aps = get_cambium_aps(CAMBIUM_BASE_URL, CAMBIUM_CLIENT_ID, CAMBIUM_CLIENT_SECRET, api_server_url, initial_token)
        
        # 3. Load & Update
        if my_aps:
            sync_to_netbox(my_aps)
            sync_to_zabbix(my_aps)
            
            # 4. Clean up orphans
            cleanup_orphaned_aps(my_aps)
            
        print("\nIntegration complete!")
        
    except Exception as err:
        print(f"\nAn error occurred during execution: {err}", file=sys.stderr)
        sys.exit(1)

