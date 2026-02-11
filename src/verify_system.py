import json
import os
import requests
from api_client import RiotTournamentClient
from discord_helper import send_discord_webhook

def check_presets_file():
    print("\n[1] Checking presets.json integrity...")
    if not os.path.exists("presets.json"):
        print("❌ presets.json not found!")
        return False
    try:
        with open("presets.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            print(f"✅ presets.json loaded. Found {len(data)} presets.")
            for p in data:
                print(f"   - Preset: {p.get('label', 'Unnamed')}")
                if "actions" not in p or not isinstance(p["actions"], list):
                    print("     ❌ Invalid actions structure")
                    return False
                for a in p["actions"]:
                    url = a.get("url", "")
                    masked_url = url[:35] + "..." if len(url) > 30 else url
                    print(f"     -> Action: {a.get('name', 'Unnamed')} (Webhook: {masked_url})")
            return True
    except Exception as e:
        print(f"❌ Error reading presets.json: {e}")
        return False

def check_backend_connection():
    print("\n[2] Checking GAS Backend & Riot API...")
    client = RiotTournamentClient(use_stub=True)
    
    # 1. Create Provider
    print("   -> Creating Provider...")
    res = client.create_provider("KR", "http://dummy.url/callback")
    if not res["success"]:
        print(f"❌ Failed to create provider: {res['error']}")
        return False
    provider_id = res["data"]
    print(f"✅ Provider Created: {provider_id}")
    
    # 2. Create Tournament
    print("   -> Creating Tournament...")
    res = client.create_tournament(provider_id, "Verify Test Tournament")
    if not res["success"]:
        print(f"❌ Failed to create tournament: {res['error']}")
        return False
    tournament_id = res["data"]
    print(f"✅ Tournament Created: {tournament_id}")
    
    # 3. Create Code
    print("   -> Generating Code...")
    res = client.create_codes(tournament_id, count=1)
    if not res["success"]:
        print(f"❌ Failed to generate code: {res['error']}")
        return False
    code = res["data"][0]
    print(f"✅ Code Generated: {code}")
    
    return True

def main():
    print("=== LOL Tournament Code Creator - System Verification ===")
    
    presets_ok = check_presets_file()
    backend_ok = check_backend_connection()
    
    print("\n" + "="*40)
    print(f"Presets File: {'✅ PASS' if presets_ok else '❌ FAIL'}")
    print(f"API Backend : {'✅ PASS' if backend_ok else '❌ FAIL'}")
    print("="*40)

if __name__ == "__main__":
    main()
