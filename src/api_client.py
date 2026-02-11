import requests
import urllib.parse

class RiotTournamentClient:
    def __init__(self, use_stub=True):
        self.use_stub = use_stub
        # Use Google Apps Script (GAS) backend to protect Production Key
        self.base_url = "https://script.google.com/macros/s/AKfycbz53p_hNUxB_EP8VaGaEZzpSzhXgiZ3ceMPDz5jdixqjLtEgrkpMqtB31Do-DXpFmMXug/exec"
        
    def _build_riot_path(self, endpoint_suffix):
        """Build full Riot API path based on stub/production mode."""
        base = "/lol/tournament-stub/v5" if self.use_stub else "/lol/tournament/v5"
        return base + endpoint_suffix

    def _request(self, method, endpoint_suffix, params=None, json_data=None):
        """
        Route requests through GAS backend.
        GAS script will receive this payload and forward to Riot API.
        """
        # Build the full Riot API endpoint path
        riot_endpoint = self._build_riot_path(endpoint_suffix)
        
        # Build payload for GAS
        payload = {
            "method": method,
            "endpoint": riot_endpoint,
            "use_stub": self.use_stub
        }
        if params:
            payload["params"] = params
        if json_data:
            payload["body"] = json_data

        try:
            response = requests.post(self.base_url, json=payload, timeout=30)
            response.raise_for_status()
            res_data = response.json()
            
            # Check if GAS returned an error from Riot
            if isinstance(res_data, dict):
                # Riot API error response
                if "status" in res_data and isinstance(res_data["status"], dict):
                    status_code = res_data["status"].get("status_code", 0)
                    if status_code >= 400:
                        return {"success": False, "error": f"Riot API Error {status_code}: {res_data['status'].get('message', 'Unknown')}"}
                # GAS error response
                if "error" in res_data:
                    return {"success": False, "error": res_data["error"]}
                # Success with custom structure
                if "success" in res_data:
                    return res_data
            
            # Direct success (number or list returned by Riot)
            return {"success": True, "data": res_data}
            
        except requests.exceptions.Timeout:
            return {"success": False, "error": "Backend timeout (30s). Please try again."}
        except requests.exceptions.HTTPError as e:
            return {"success": False, "error": f"Backend HTTP Error: {e}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def create_provider(self, region="KR", url="http://example.com/callback"):
        data = {
            "region": region.upper(),
            "url": url
        }
        return self._request("POST", "/providers", json_data=data)

    def create_tournament(self, provider_id, name="My Tournament"):
        data = {
            "name": name,
            "providerId": provider_id
        }
        return self._request("POST", "/tournaments", json_data=data)

    def create_codes(self, tournament_id, count=1, map_type="SUMMONERS_RIFT", 
                     pick_type="TOURNAMENT_DRAFT", spectator_type="ALL", 
                     team_size=5, metadata=""):
        params = {
            "count": count,
            "tournamentId": tournament_id
        }
        data = {
            "mapType": map_type,
            "pickType": pick_type,
            "spectatorType": spectator_type,
            "teamSize": team_size,
            "metadata": metadata
        }
        return self._request("POST", "/codes", params=params, json_data=data)
