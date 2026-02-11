import os
import sys
import config_manager
from api_client import RiotTournamentClient

def main():
    print("=== LOL Tournament Code Generator (CLI) ===")
    
    # 0. Setup Client
    # All API requests are now routed through a secure backend (GAS).
    # No local API key is required.
    config = config_manager.load_config()
    client = RiotTournamentClient(use_stub=config.get("use_stub", True))
    
    # Ask for the Target Region (where the game is played)
    target_region = input("Enter Target Region (default: KR): ").strip().upper() or "KR"

    # 1. Create Provider
    print("\n--- Step 1: Create Provider ---")
    provider_url = "http://example.com/callback" # Dummy URL used for Stub
    print(f"Using Dummy Callback URL: {provider_url}")
    print(f"Creating Provider for Region: {target_region}")
    
    resp_provider = client.create_provider(region=target_region, url=provider_url)
    
    if not resp_provider["success"]:
        print(f"Failed to create provider: {resp_provider['error']}")
        return
        
    provider_id = resp_provider["data"]
    print(f"Provider created successfully! ID: {provider_id}")

    # 2. Create Tournament
    print("\n--- Step 2: Create Tournament ---")
    tournament_name = input("Enter Tournament Name (default: My Tournament): ").strip() or "My Tournament"
    
    resp_tournament = client.create_tournament(provider_id, name=tournament_name)
    
    if not resp_tournament["success"]:
        print(f"Failed to create tournament: {resp_tournament['error']}")
        return
        
    tournament_id = resp_tournament["data"]
    print(f"Tournament created successfully! ID: {tournament_id}")

    # 3. Generate Codes
    print("\n--- Step 3: Generate Codes ---")
    try:
        count = int(input("How many codes to generate? (default: 1): ").strip() or "1")
        team_size = int(input("Team Size (1-5, default: 5): ").strip() or "5")
    except ValueError:
        print("Invalid number entered. Using defaults.")
        count = 1
        team_size = 5

    resp_codes = client.create_codes(tournament_id, count=count, team_size=team_size)
    
    if resp_codes["success"]:
        codes = resp_codes["data"]
        print("\n=== Generated Codes ===")
        for i,code in enumerate(codes):
            print(f"{i+1}: {code}")
        
        print("\nCopy these codes to use in the League of Legends client.")
        print("(Play -> Tournament Code (trophy icon top right) -> Paste Code)")
    else:
        print(f"Failed to generate codes: {resp_codes['error']}")

if __name__ == "__main__":
    main()
