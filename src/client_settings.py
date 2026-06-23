import os


# Public Supabase client settings.
# These are not Riot secrets. Set them before building the production app.
SUPABASE_PROJECT_URL = "https://ofogstpjheigpnsmnlxn.supabase.co"
SUPABASE_ANON_KEY = "sb_publishable_cRpjyQ9UCWc6Evk4G9TJpQ_96_sNhLN"
SUPABASE_FUNCTION_NAME = "riot-tournament"


def get_supabase_project_url():
    return (os.getenv("LOL_TOURNAMENT_SUPABASE_URL") or SUPABASE_PROJECT_URL).strip().rstrip("/")


def get_supabase_anon_key():
    return (os.getenv("LOL_TOURNAMENT_SUPABASE_ANON_KEY") or SUPABASE_ANON_KEY).strip()


def get_supabase_function_name():
    return (os.getenv("LOL_TOURNAMENT_SUPABASE_FUNCTION") or SUPABASE_FUNCTION_NAME).strip() or "riot-tournament"
