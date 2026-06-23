import time
from urllib.parse import urlparse

import requests


DEFAULT_TIMEOUT_SECONDS = 10
DEFAULT_MAX_RETRIES = 0
MAX_RETRY_AFTER_SECONDS = 10
TOURNAMENT_ROUTING_VALUES = {"americas", "asia", "europe", "sea"}
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
STOP_BATCH_STATUS_CODES = RETRYABLE_STATUS_CODES

MAP_TYPES = {"SUMMONERS_RIFT", "HOWLING_ABYSS"}
PICK_TYPES = {"BLIND_PICK", "DRAFT_MODE", "ALL_RANDOM", "TOURNAMENT_DRAFT"}
SPECTATOR_TYPES = {"NONE", "LOBBYONLY", "ALL"}


def _safe_text(response, limit=180):
    text = (response.text or "").strip().replace("\n", " ")
    return text[:limit]


def _normalize_supabase_url(supabase_url):
    return (supabase_url or "").strip().rstrip("/")


def _valid_supabase_url(supabase_url):
    parsed = urlparse(_normalize_supabase_url(supabase_url))
    return parsed.scheme == "https" and bool(parsed.netloc)


def should_stop_after_riot_failure(result):
    """Return True when another immediate Riot request would likely add load."""
    if not isinstance(result, dict):
        return False
    return bool(result.get("retryable")) or result.get("status_code") in STOP_BATCH_STATUS_CODES


def supabase_sign_in(supabase_url, anon_key, email, password, timeout=DEFAULT_TIMEOUT_SECONDS):
    """Sign in an operator with Supabase Auth and return session tokens."""
    supabase_url = _normalize_supabase_url(supabase_url)
    anon_key = (anon_key or "").strip()
    email = (email or "").strip()
    password = password or ""

    if not _valid_supabase_url(supabase_url):
        return {"success": False, "error": "Supabase Project URL must be a valid HTTPS URL."}
    if not anon_key:
        return {"success": False, "error": "Supabase anon key is required."}
    if not email or not password:
        return {"success": False, "error": "Operator email and password are required."}

    response, error = _supabase_auth_token_request(
        supabase_url,
        anon_key,
        "password",
        {"email": email, "password": password},
        "sign-in",
        timeout,
    )
    if error:
        return error

    return _parse_supabase_session(response, email, "sign-in")


def supabase_refresh_session(supabase_url, anon_key, refresh_token, timeout=DEFAULT_TIMEOUT_SECONDS):
    """Refresh a Supabase Auth session without storing the operator password."""
    supabase_url = _normalize_supabase_url(supabase_url)
    anon_key = (anon_key or "").strip()
    refresh_token = (refresh_token or "").strip()

    if not _valid_supabase_url(supabase_url):
        return {"success": False, "error": "Supabase Project URL must be a valid HTTPS URL."}
    if not anon_key:
        return {"success": False, "error": "Supabase anon key is required."}
    if not refresh_token:
        return {"success": False, "error": "Supabase refresh token is missing."}

    response, error = _supabase_auth_token_request(
        supabase_url,
        anon_key,
        "refresh_token",
        {"refresh_token": refresh_token},
        "session refresh",
        timeout,
    )
    if error:
        return error

    return _parse_supabase_session(response, "", "session refresh")


def _supabase_auth_token_request(supabase_url, anon_key, grant_type, payload, operation, timeout):
    try:
        response = requests.post(
            f"{supabase_url}/auth/v1/token?grant_type={grant_type}",
            headers={
                "apikey": anon_key,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=timeout,
        )
    except requests.exceptions.Timeout:
        return None, {"success": False, "error": f"Supabase {operation} timed out after {timeout} seconds."}
    except requests.exceptions.RequestException as exc:
        return None, {"success": False, "error": f"Supabase {operation} network error: {exc.__class__.__name__}"}

    if response.status_code >= 400:
        return None, {
            "success": False,
            "error": f"Supabase {operation} failed ({response.status_code}): {_supabase_error_text(response)}",
        }

    return response, None


def _supabase_error_text(response):
    error = _safe_text(response)
    try:
        data = response.json()
    except ValueError:
        return error
    return data.get("msg") or data.get("message") or data.get("error_description") or error


def _parse_supabase_session(response, fallback_email, operation):
    try:
        data = response.json()
    except ValueError:
        return {"success": False, "error": f"Supabase {operation} returned a non-JSON response."}

    access_token = data.get("access_token")
    if not access_token:
        return {"success": False, "error": f"Supabase {operation} did not return an access token."}

    user = data.get("user") or {}
    return {
        "success": True,
        "access_token": access_token,
        "refresh_token": data.get("refresh_token", ""),
        "user_email": user.get("email") or fallback_email,
        "expires_in": data.get("expires_in"),
    }


class RiotTournamentClient:
    def __init__(
        self,
        api_key=None,
        use_stub=True,
        platform_routing="americas",
        timeout=DEFAULT_TIMEOUT_SECONDS,
        max_retries=DEFAULT_MAX_RETRIES,
        supabase_url="",
        supabase_anon_key="",
        supabase_access_token="",
        supabase_refresh_token="",
        supabase_function_name="riot-tournament",
        on_session_refresh=None,
    ):
        if api_key:
            raise ValueError("Riot API keys must be configured only as Supabase secrets.")
        self.use_stub = use_stub
        self.timeout = timeout
        self.max_retries = max_retries
        self.supabase_url = _normalize_supabase_url(supabase_url)
        self.supabase_anon_key = (supabase_anon_key or "").strip()
        self.supabase_access_token = (supabase_access_token or "").strip()
        self.supabase_refresh_token = (supabase_refresh_token or "").strip()
        self.supabase_function_name = (supabase_function_name or "riot-tournament").strip()
        self.on_session_refresh = on_session_refresh

        routing = (platform_routing or "americas").strip().lower()
        if routing not in TOURNAMENT_ROUTING_VALUES:
            raise ValueError(f"Unsupported Riot regional routing value: {platform_routing}")
        self.routing_value = routing
        self.session = requests.Session()

    def _request_action(self, action, body=None):
        missing = self._missing_supabase_config()
        if missing:
            return {"success": False, "error": missing, "status_code": 401}

        payload = {
            "action": action,
            "routing_value": self.routing_value,
            "use_stub": self.use_stub,
        }
        if body:
            payload.update(body)

        url = f"{self.supabase_url}/functions/v1/{self.supabase_function_name}"

        last_error = "Unknown Supabase Edge Function error"
        session_refreshed = False
        attempt = 0
        while attempt <= self.max_retries:
            headers = {
                "Content-Type": "application/json",
                "apikey": self.supabase_anon_key,
                "Authorization": f"Bearer {self.supabase_access_token}",
            }
            try:
                response = self.session.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=max(self.timeout, 15),
                )
            except requests.exceptions.Timeout:
                last_error = f"Supabase Edge Function timed out after {max(self.timeout, 15)} seconds."
                if attempt < self.max_retries:
                    time.sleep(self._retry_delay_seconds(None, attempt))
                    attempt += 1
                    continue
                break
            except requests.exceptions.RequestException as exc:
                last_error = f"Supabase Edge Function network error: {exc.__class__.__name__}"
                if attempt < self.max_retries:
                    time.sleep(self._retry_delay_seconds(None, attempt))
                    attempt += 1
                    continue
                break
            else:
                if response.status_code == 401 and not session_refreshed and self._refresh_supabase_session():
                    session_refreshed = True
                    continue
                if response.status_code in RETRYABLE_STATUS_CODES and attempt < self.max_retries:
                    time.sleep(self._retry_delay_seconds(response, attempt))
                    attempt += 1
                    continue

                result = self._normalize_response(response)
                if result.get("retryable") and attempt < self.max_retries:
                    retry_after = result.get("retry_after")
                    delay = retry_after if isinstance(retry_after, (int, float)) else self._retry_delay_seconds(None, attempt)
                    if result.get("status_code") == 429 and delay > MAX_RETRY_AFTER_SECONDS:
                        return result
                    time.sleep(delay)
                    attempt += 1
                    continue
                return result

        return {"success": False, "error": last_error, "retryable": True}

    def _refresh_supabase_session(self):
        result = supabase_refresh_session(
            self.supabase_url,
            self.supabase_anon_key,
            self.supabase_refresh_token,
            timeout=self.timeout,
        )
        if not result.get("success"):
            return False

        self.supabase_access_token = result.get("access_token", "")
        self.supabase_refresh_token = result.get("refresh_token") or self.supabase_refresh_token
        if callable(self.on_session_refresh):
            self.on_session_refresh(result)
        return bool(self.supabase_access_token)

    def _missing_supabase_config(self):
        if not _valid_supabase_url(self.supabase_url):
            return "Supabase Project URL is missing or invalid."
        if not self.supabase_anon_key:
            return "Supabase anon key is missing."
        if not self.supabase_access_token:
            return "Operator is not signed in to Supabase."
        return ""

    def _retry_delay_seconds(self, response, attempt):
        retry_after = response.headers.get("Retry-After") if response is not None else None
        if retry_after:
            try:
                return max(0, int(float(retry_after)))
            except ValueError:
                pass
        return min(2 ** attempt, 5)

    def _normalize_response(self, response):
        try:
            data = response.json()
        except ValueError:
            data = _safe_text(response)

        status_code = response.status_code
        if isinstance(data, dict):
            status_code = data.get("status_code") or status_code
            if data.get("success") is False or response.status_code >= 400:
                return {
                    "success": False,
                    "error": data.get("error") or self._status_error_message(data) or f"Supabase request failed ({response.status_code}).",
                    "status_code": status_code,
                    "retryable": status_code in RETRYABLE_STATUS_CODES if status_code else False,
                    "retry_after": data.get("retry_after"),
                }
            if "data" in data and "success" in data:
                return data

        if response.status_code >= 400:
            return {
                "success": False,
                "error": f"Supabase request failed ({response.status_code}): {data}",
                "status_code": response.status_code,
                "retryable": response.status_code in RETRYABLE_STATUS_CODES,
            }
        return {"success": True, "data": data}

    def _status_error_message(self, data):
        status = data.get("status", {}) if isinstance(data, dict) else {}
        if isinstance(status, dict) and status.get("message"):
            return f"API Error ({status.get('status_code', 'unknown')}): {status['message']}"
        return data.get("error", "Supabase backend request failed.") if isinstance(data, dict) else "Supabase backend request failed."

    def create_provider(self, region="KR"):
        return self._request_action(
            "create_provider",
            {"region": (region or "KR").upper()},
        )

    def create_tournament(self, provider_id, name="My Tournament"):
        if provider_id in (None, ""):
            return {"success": False, "error": "Provider ID is required."}
        return self._request_action(
            "create_tournament",
            {"provider_id": provider_id, "name": name},
        )

    def create_codes(
        self,
        tournament_id,
        count=1,
        map_type="SUMMONERS_RIFT",
        pick_type="TOURNAMENT_DRAFT",
        spectator_type="ALL",
        team_size=5,
        metadata="",
    ):
        try:
            count = int(count)
            team_size = int(team_size)
        except (TypeError, ValueError):
            return {"success": False, "error": "Code count and team size must be numbers."}

        if tournament_id in (None, ""):
            return {"success": False, "error": "Tournament ID is required."}
        if not 1 <= count <= 1000:
            return {"success": False, "error": "Code count must be between 1 and 1000."}
        if not 1 <= team_size <= 5:
            return {"success": False, "error": "Team size must be between 1 and 5."}
        if map_type not in MAP_TYPES:
            return {"success": False, "error": f"Unsupported map type: {map_type}"}
        if pick_type not in PICK_TYPES:
            return {"success": False, "error": f"Unsupported pick type: {pick_type}"}
        if spectator_type not in SPECTATOR_TYPES:
            return {"success": False, "error": f"Unsupported spectator type: {spectator_type}"}

        return self._request_action(
            "create_codes",
            {
                "tournament_id": tournament_id,
                "count": count,
                "map_type": map_type,
                "pick_type": pick_type,
                "spectator_type": spectator_type,
                "team_size": team_size,
                "metadata": metadata,
            },
        )
