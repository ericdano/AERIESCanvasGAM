import requests
import json
from pathlib import Path

# 1. Load your config
confighome = Path.home() / ".Acalanes" / "Acalanes.json"
with open(confighome) as f:
    configs = json.load(f)

api_key = configs['AERIES_API']
headers = {
    "Aeries-Cert": api_key, 
    "Content-Type": "application/json"
}

# 2. Test the most common Acalanes URL structures
test_urls = [
    "https://acalanes.aeries.net/api/v5",
    "https://acalanes.aeries.net/admin/api/v5",
    "https://acalanes.aeries.net/student/api/v5"
]

print("Starting Aeries API Diagnostic...\n")

success = False
for url in test_urls:
    # We query the '/schools' endpoint which lists all schools
    endpoint = f"{url}/schools"
    print(f"Testing URL: {endpoint}")
    
    response = requests.get(endpoint, headers=headers)
    
    if response.status_code == 200:
        print("\n✅ SUCCESS! We found the right base URL:")
        print(f"👉 Update your Acalanes.json 'AERIES_API_URL' to: {url}\n")
        
        schools = response.json()
        print("Here are your exact School Codes for the Master Schedule script:")
        print("-" * 40)
        for school in schools:
            # Safely grab the school name and code
            code = school.get('SchoolCode')
            name = school.get('Name', school.get('OrganizationName', 'Unknown School'))
            print(f"- {name}: Code '{code}'")
        
        success = True
        break
    else:
        print(f"❌ Failed with Status {response.status_code}")

if not success:
    print("\nCould not connect. Check that your API key is correct and active.")