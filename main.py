import config_manager
from api_client import RiotTournamentClient


def save_refreshed_supabase_session(session):
    config = config_manager.load_config()
    config["supabase_access_token"] = session.get("access_token", "")
    config["supabase_refresh_token"] = session.get("refresh_token") or config.get("supabase_refresh_token", "")
    config["supabase_user_email"] = session.get("user_email") or config.get("supabase_user_email", "")
    config["supabase_client_id"] = config_manager.get_supabase_client_id()
    config_manager.save_config(config)


def main():
    print("=== LOL Tournament Code Generator (CLI) ===")

    config = config_manager.load_config()
    warnings = config_manager.production_config_warnings(config)
    if warnings:
        print("Supabase configuration is not ready:")
        for warning in warnings:
            print(f"- {warning}")
        print("Complete operator authentication in the GUI settings first, then retry the CLI.")
        return

    client = RiotTournamentClient(
        use_stub=config.get("use_stub", True),
        platform_routing=config.get("routing_value", "americas"),
        supabase_url=config.get("supabase_url", ""),
        supabase_anon_key=config.get("supabase_anon_key", ""),
        supabase_access_token=config.get("supabase_access_token", ""),
        supabase_refresh_token=config.get("supabase_refresh_token", ""),
        supabase_function_name=config_manager.get_supabase_client_settings()["supabase_function_name"],
        on_session_refresh=save_refreshed_supabase_session,
    )

    target_region = input(f"Enter Target Region (default: {config.get('region', 'KR')}): ").strip().upper() or config.get("region", "KR")

    print("\n--- Step 1: Create Provider ---")
    print("Using server-side Riot callback URL from Supabase Edge Function secrets.")
    print(f"Creating Provider for Region: {target_region}")

    resp_provider = client.create_provider(region=target_region)

    if not resp_provider["success"]:
        print(f"Failed to create provider: {resp_provider['error']}")
        return

    provider_id = resp_provider["data"]
    print(f"Provider created successfully! ID: {provider_id}")

    print("\n--- Step 2: Create Tournament ---")
    tournament_name = input("Enter Tournament Name (default: My Tournament): ").strip() or "My Tournament"

    resp_tournament = client.create_tournament(provider_id, name=tournament_name)

    if not resp_tournament["success"]:
        print(f"Failed to create tournament: {resp_tournament['error']}")
        return

    tournament_id = resp_tournament["data"]
    print(f"Tournament created successfully! ID: {tournament_id}")

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
        for i, code in enumerate(codes):
            print(f"{i + 1}: {code}")

        print("\nCopy these codes to use in the League of Legends client.")
        print("(Play -> Tournament Code (trophy icon top right) -> Paste Code)")
    else:
        print(f"Failed to generate codes: {resp_codes['error']}")


if __name__ == "__main__":
    main()
