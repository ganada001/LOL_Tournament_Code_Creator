# Riot Production Readiness Checklist

This checklist focuses on reducing operational and security risk for Riot
Production review without expanding the product scope.

## Scope

- The app creates Tournament API providers, tournaments, and tournament codes.
- The app sends generated codes to configured Discord webhooks.
- The app does not collect Riot account credentials, player passwords, match
  history, ranked data, or private player profiles.
- The app does not provide betting, gambling, gameplay automation, unfair
  competitive advantage, or hidden game-session information.

## Security Controls

- Riot API keys are not stored in the desktop client, `config.json`, local app
  settings, or packaged binaries.
- Riot API keys live only in Supabase Edge Function secrets.
- Supabase service-role keys and secret keys must never be placed in the desktop
  app. The desktop app uses only the public Supabase anon key from build
  settings plus the operator's Supabase Auth access token.
- The operator password is not stored. Expired access tokens are refreshed with
  the stored Supabase refresh token.
- Supabase Edge Function JWT verification is enabled for Riot API actions.
- The backend authorizes operators against `ALLOWED_OPERATOR_EMAILS`.
- Callback URL is server-side only through `RIOT_CALLBACK_URL`; it is not an
  editable desktop setting.
- Live Tournament API code creation requires `RIOT_CALLBACK_SECRET`. The backend
  signs Tournament Code metadata, and the public callback endpoint verifies that
  signature before accepting callback events.
- The backend accepts app-level actions, not arbitrary Riot endpoint paths.
- Discord webhook URLs are validated as HTTPS Discord webhook endpoints before
  sending.
- Webhook failure logs avoid printing the full webhook URL or token.
- Network calls use bounded timeouts.
- Riot retryable failures and 429 responses stop batch generation to avoid
  repeated pressure on the API.

## Tournament API Controls

- Stub API is the default mode for safe testing.
- Production mode cannot initialize until build-time Supabase client settings
  and operator authentication are configured.
- Riot Tournament API routing defaults to `americas.api.riotgames.com`, which
  is verified for provider creation. A future Riot-required routing change can
  be made server-side with `RIOT_TOURNAMENT_ROUTING` without rebuilding the
  desktop app.
- Provider creation uses a server-controlled callback URL.
- Provider IDs are reset when Stub/Production mode, routing value, backend build
  identity, or operator identity changes.
- Tournament codes are generated on demand for selected preset actions, not as
  large unused batches.
- Code count, map type, pick type, spectator type, team size, provider ID, and
  tournament ID are validated before Riot requests are sent.

## Operator Responsibilities

- Before Riot approval, store the Riot key assigned to the prototype product
  only as a Supabase Edge Function secret. If the key is permanent, still verify
  that the product/key has Tournament API or Tournament Stub API access.
- After Riot approval, replace the Supabase secret with the Production API key.
- Set `RIOT_CALLBACK_URL` to the deployed Supabase callback function URL.
- Set `RIOT_CALLBACK_SECRET` to a random 32+ character secret and rotate it
  after suspected exposure.
- Set `ALLOWED_OPERATOR_EMAILS` to the exact Supabase Auth operator email list.
- Create Supabase Auth users only for trusted tournament operators.
- Rotate Riot API keys, Supabase sessions, and Discord webhooks after suspected
  exposure.
- Keep local `.env`, `config.json`, `presets.json`, build outputs, and caches out
  of release packages.
- Rebuild the executable after source or security-control changes.
- Keep the Riot Developer Portal product description, screenshots, callback URL,
  and user flow current.

## Runtime Failure Triage

- `Operator is not authorized` means Supabase Auth succeeded but the email is
  not in `ALLOWED_OPERATOR_EMAILS`.
- `RIOT_API_KEY is not configured` means the Supabase secret is missing.
- `Riot API Error 403: Forbidden` during provider creation means Riot rejected
  the Tournament API request. First check the routing host: this project created
  a provider with `americas.api.riotgames.com`, while `asia.api.riotgames.com`
  returned 403. Then check the Supabase `RIOT_API_KEY` secret and the Developer
  Portal product/key access to `tournament-stub-v5` or `tournament-v5`; if the
  key changed, update the secret and create a new provider.
- Callback URL and metadata validation issues should be checked separately
  through the deployed `riot-callback` endpoint and Riot's documented callback
  domain/certificate restrictions.

## Review Evidence

- `api_client.py` calls only the authenticated Supabase Edge Function.
- `config_manager.py` strips legacy client-side callback/proxy fields from local
  config and validates Supabase settings.
- `gui_main.py` exposes operator authentication only, not Riot API key, Supabase
  project URL, Supabase anon key, backend proxy token, or callback URL fields.
- `supabase/functions/riot-tournament/index.ts` stores Riot API access
  server-side, validates allowed actions, validates routing/options, and uses the
  server-side callback secret.
- `supabase/functions/riot-callback/index.ts` verifies signed callback
  metadata when `RIOT_CALLBACK_SECRET` is configured.
- `tests/test_security_controls.py` covers secret handling, legacy field
  stripping, Supabase request shape, callback non-exposure, and validation.
