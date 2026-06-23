# Production Backend Architecture

This project now uses Supabase as the server-side control plane for Riot
Production use. The desktop app is only an operator UI; it does not hold Riot
API secrets or decide Riot callback URLs.

## Trust Boundaries

- Desktop app:
  - Reads Supabase project URL and anon/public key from public build settings.
  - Stores only the operator Auth session locally.
  - Sends only app-level actions to Supabase Edge Functions.
  - Does not store or send Riot API keys.
  - Does not expose callback URL, generic proxy URL, or shared proxy token
    settings in the GUI.

- Supabase Auth:
  - Authenticates tournament operators.
  - Issues access tokens used by the desktop app.

- Supabase Edge Functions:
  - Store `RIOT_API_KEY`, `RIOT_CALLBACK_URL`, `RIOT_CALLBACK_SECRET`, and
    `ALLOWED_OPERATOR_EMAILS` as server-side secrets.
  - Verify Supabase JWTs for Riot action requests.
  - Authorize the operator email against the allowlist.
  - Validate request shape and Riot routing values.
  - Call only allowed Riot Tournament API endpoints.

- Riot Tournament API:
  - Receives requests only from the Supabase backend.
  - Sends tournament callbacks to the Supabase callback function URL.

## Edge Functions

`riot-tournament` is the authenticated action endpoint. Supported actions:

- `create_provider`
- `create_tournament`
- `create_codes`

The desktop payload describes intent:

```json
{
  "action": "create_codes",
  "routing_value": "americas",
  "use_stub": true,
  "tournament_id": 123,
  "count": 1,
  "map_type": "SUMMONERS_RIFT",
  "pick_type": "TOURNAMENT_DRAFT",
  "spectator_type": "ALL",
  "team_size": 5
}
```

The backend maps that intent to Riot Tournament API endpoints. The desktop app
never sends raw Riot endpoint paths such as `/lol/tournament/v5/codes`.
Tournament API routing defaults to `americas.api.riotgames.com`, which is the
verified working route for provider creation in this project. If Riot instructs
a different Tournament API routing host after approval, set the Supabase secret
`RIOT_TOURNAMENT_ROUTING` to `asia`, `europe`, or `sea`; this changes the
server behavior without rebuilding the desktop app.

`riot-callback` is the public Riot callback endpoint. It is unauthenticated
because Riot must be able to POST callback events to it, but it verifies the
server-signed Tournament Code metadata before accepting callback events. It
returns quickly and avoids logging secrets.

## Supabase Secrets

Configure these values in Supabase, not in the desktop app:

- `RIOT_API_KEY`: Riot API key. Use the temporary Development API key for
  private prototype validation before Riot approval, then replace this secret
  with the Production API key after approval.
- `RIOT_CALLBACK_URL`: deployed callback function URL, for example
  `https://<project-ref>.supabase.co/functions/v1/riot-callback`.
- `RIOT_CALLBACK_SECRET`: random 32+ character secret used to sign Tournament
  Code metadata and validate Riot callbacks.
- `ALLOWED_OPERATOR_EMAILS`: comma-separated trusted operator emails.
- `RIOT_TOURNAMENT_ROUTING` (optional): Tournament API routing host prefix.
  Defaults to `americas` when omitted.

Never configure Supabase service-role keys or Riot API keys in the desktop app.

## Current Controls

- Edge Function JWT verification is enabled for `riot-tournament`.
- Operator email allowlist is checked server-side.
- Riot Tournament API routing is restricted to `americas`, `asia`, `europe`,
  and `sea`; the verified default is `americas`.
- Provider region, provider ID, tournament ID, tournament name, code count,
  team size, map type, pick type, and spectator type are validated server-side.
- Live Tournament API code creation requires signed callback metadata, and the
  callback function rejects invalid metadata signatures.
- Client-side validation catches common mistakes before network requests.
- Client retries are bounded and respect retryable failure handling.
- Batch generation stops after Riot rate-limit/retryable failures.

## Future Hardening Before Broad Distribution

These are not feature expansions; they are operational controls that can be
added behind the same user flow:

- Per-operator and per-IP rate limiting in Supabase.
- Persistent audit table for provider, tournament, and code creation requests.
- Request IDs returned to the desktop app and stored with audit records.
- Idempotency keys for safe retry of code-generation requests.
- Structured callback storage if callback events need later incident review.
- Automated key/session rotation procedure for operator offboarding.
