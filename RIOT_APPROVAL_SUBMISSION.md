# Riot Production Application Notes

Use this file as the source checklist when filling out the Riot Developer Portal
product registration or follow-up messages.

## Current Stage

- The project is an approval-ready private prototype.
- Before Riot approval, `RIOT_API_KEY` should be the Riot key assigned to the
  Developer Portal product used for this prototype. If that key is permanent,
  still verify that the same product/key has Tournament API or Tournament Stub
  API access; key lifetime is not proof of Tournament API entitlement.
- The Riot API key is stored only as a Supabase Edge Function secret.
- The desktop app does not contain a Riot API key, callback URL, Supabase
  service-role key, or editable backend URL.
- The live callback flow uses server-signed Tournament Code metadata and
  verifies that signature in the public callback endpoint.
- After Riot approval, replace only the Supabase `RIOT_API_KEY` secret with the
  Production API key:

```powershell
npm run riot-key:update
```

## Product Summary

LOL Tournament Code Creator is a desktop operator tool for League of Legends
community tournament organizers. It creates Riot Tournament API providers,
tournaments, and tournament codes, then optionally sends generated codes to
operator-configured Discord webhooks.

## Riot API Use

- API family requested: League of Legends Tournament API.
- Intended endpoints:
  - `/lol/tournament-stub/v5/providers`
  - `/lol/tournament-stub/v5/tournaments`
  - `/lol/tournament-stub/v5/codes`
  - `/lol/tournament/v5/providers`
  - `/lol/tournament/v5/tournaments`
  - `/lol/tournament/v5/codes`
- Tournament API routing defaults to `americas`, because provider creation was
  verified successfully with `americas.api.riotgames.com` and failed with 403 on
  `asia.api.riotgames.com`.
- If Riot instructs a different Tournament API routing host after approval, set
  the Supabase secret `RIOT_TOURNAMENT_ROUTING` to `asia`, `europe`, or `sea`.
  This does not require a desktop app rebuild.
- Default testing mode: Stub API.
- Production Tournament API mode requires Supabase Auth operator sign-in.

## 403 Forbidden During Provider Creation

If the desktop log shows `Provider 생성 실패: Riot API Error 403: Forbidden`,
the request reached the Supabase Edge Function and Riot rejected the Tournament
API request. Treat it as a Riot key/product access issue first, not a desktop
login issue.

Check the following without posting the key in chat, screenshots, or docs:

- Confirm the Supabase `RIOT_API_KEY` secret is the exact current Riot key from
  the intended Developer Portal product.
- Confirm the Tournament API routing host. This project is verified with
  `americas.api.riotgames.com`; `asia.api.riotgames.com` caused 403 during
  provider creation.
- Confirm that product/key has access to `tournament-stub-v5` for Stub mode and
  `tournament-v5` for live mode.
- If the Riot key was regenerated or replaced, update only the Supabase secret
  with `npm run riot-key:update` and create a new provider. Riot documents that
  tournament providers are strongly associated with API keys.
- Keep Stub API enabled until the key/product access problem is resolved.
- Separately verify that `RIOT_CALLBACK_URL` is a deployed callback URL that
  satisfies Riot's callback port, TLD, and certificate restrictions. The
  Supabase default HTTPS endpoint can be used for direct callback-shape tests,
  but true Riot callback delivery must be verified with Riot's callback rules.
  A provider-creation 403 should still be investigated as key/product access
  first.
- Separately verify that `RIOT_CALLBACK_SECRET` is configured before switching
  from Stub API to live Tournament API code creation.

## Security Summary

- Riot API key is server-side only in Supabase Edge Function secrets.
- The desktop app calls only authenticated Supabase Edge Functions.
- The desktop app sends app-level actions, not arbitrary Riot endpoint paths.
- `riot-tournament` requires Supabase JWT verification.
- Operators are allowlisted with `ALLOWED_OPERATOR_EMAILS`.
- Riot callback URL is server-controlled through `RIOT_CALLBACK_URL`.
- The callback endpoint is public only because Riot must POST callbacks to it.
- Tournament Code metadata is signed server-side with `RIOT_CALLBACK_SECRET`,
  and callback requests are accepted only when that signature is valid.
- Supabase service-role keys are not shipped in the desktop app.
- Local runtime settings, presets, logs, and build artifacts are blocked from
  release bundles by `npm run release:guard`.

## Deployed Backend

- Supabase project URL: `https://ofogstpjheigpnsmnlxn.supabase.co`
- Current direct-test Riot callback URL:
  `https://ofogstpjheigpnsmnlxn.supabase.co/functions/v1/riot-callback`
- Edge Functions:
  - `riot-tournament`
  - `riot-callback`

## Verification Commands

Run these before submitting updated evidence:

```powershell
npm run predeploy
npm run postdeploy
npm run release:guard
```

## Riot Documentation Basis

Riot's Developer Portal explains that Development API keys are temporary keys
for prototype development and deactivate every 24 hours. It also explains that
Production API keys are requested for public products and typically require a
working prototype before receiving a key.

Reference:
https://developer.riotgames.com/docs/portal#web-apis_api-keys
