# LOL Tournament Code Creator

League of Legends community tournament operators can use this desktop app to
create Riot Tournament API providers, tournaments, and tournament codes, then
send generated codes to configured Discord webhooks.

## Security Model

- The desktop app does not store or send a Riot API key.
- Riot API calls are made only by Supabase Edge Functions.
- `RIOT_API_KEY`, `RIOT_CALLBACK_URL`, `RIOT_CALLBACK_SECRET`, and allowed
  operator emails are stored as Supabase function secrets.
- Supabase project URL and anon/public key are public build settings in
  `client_settings.py`, not operator-editable desktop settings.
- The desktop app stores the operator's Supabase Auth session under
  `%APPDATA%/LOL_Tournament_Code_Creator/`.
- Discord preset data is also stored under `%APPDATA%/LOL_Tournament_Code_Creator/`;
  `config/presets.json.example` is only a safe template.
- Expired Supabase access tokens are refreshed with the stored Supabase refresh
  token; the operator password is not stored.
- Callback URL is not editable in the desktop app. Provider creation always uses
  the server-side `RIOT_CALLBACK_URL` secret.
- Live Tournament API code creation requires `RIOT_CALLBACK_SECRET`. The backend
  signs Tournament Code metadata, and the callback endpoint verifies that
  signature before accepting callback events.
- The Supabase backend exposes app-level actions only:
  `create_provider`, `create_tournament`, and `create_codes`.

## Use Flow

1. Deploy the Supabase Edge Functions in `supabase/functions/`.
2. Configure Supabase secrets:
   `RIOT_API_KEY`, `RIOT_CALLBACK_URL`, `RIOT_CALLBACK_SECRET`, and
   `ALLOWED_OPERATOR_EMAILS`.
3. Set the public Supabase client values in `client_settings.py` before building.
4. Create an operator user in Supabase Auth.
5. In the desktop app settings, complete operator authentication with email and
   password.
6. Generate a Provider ID, then create tournament codes manually or through
   presets.

## Supabase Files

- `supabase/functions/riot-tournament/index.ts` - authenticated backend action
  endpoint for Riot Tournament API calls.
- `supabase/functions/riot-callback/index.ts` - Riot tournament callback
  endpoint.
- `supabase/config.toml` - Edge Function JWT verification settings.
- `supabase/.env.example` - safe secret-name template.

## Local CLI Tooling

Install the local tooling with `npm install`.

- `npm run deno -- --version` - verify the local Deno runtime.
- `npm run supabase:version` - verify the local Supabase CLI.
- `npm run functions:check` - type-check the Supabase Edge Functions.
- `npm run functions:fmt:check` - verify Deno formatting for Edge Functions.
- `npm run predeploy` - run Edge Function checks, Python regression tests,
  Supabase config guard, and blocked secret/legacy string scan.
- `npm run secrets:check` - validate the ignored Supabase secret file before
  upload.
- `npm run secrets:set` - upload Supabase secrets from ignored
  `supabase/.env.production.local`.
- `npm run riot-key:update` - replace only the Supabase `RIOT_API_KEY` secret
  when the Riot Development key rotates or when a Production key is approved.
- `npm run supabase:deploy:approval` - interactive approval-ready Supabase
  project, secret, and Edge Function deployment helper.
- `npm run functions:deploy` - run predeploy checks and deploy both Edge
  Functions with Supabase API bundling.
- `npm run postdeploy` - verify deployed Edge Functions and required Supabase
  secret names.
- `npm run release:guard` - fail if local-only files or generated artifacts are
  present before building a release bundle.
- `npm run readiness` - print a local readiness summary without exposing secret
  values.

The Supabase CLI is wrapped by `tools/run-supabase-cli.mjs` so it stores local
CLI state under `.supabase-cli-home/` instead of the Windows user profile.

## Riot Production Readiness

- Stub API remains the default mode for safer testing.
- Production mode requires build-time Supabase client settings and operator
  authentication before the Riot client initializes.
- Routing values are restricted to Riot regional routing clusters:
  `americas`, `asia`, `europe`, and `sea`.
- Tournament code options are validated before network calls.
- Retryable Riot failures and rate limits stop batch generation to avoid
  repeated load.
- Discord webhook URLs are validated as Discord HTTPS webhook URLs.
- Local `.env`, `config.json`, `presets.json`, build outputs, and caches are
  ignored and must not be packaged as release defaults.

See `RIOT_PRODUCTION_READINESS.md`, `RIOT_APPROVAL_SUBMISSION.md`, and
`PRODUCTION_BACKEND_ARCHITECTURE.md` for the review checklist, Riot submission
notes, and operational notes. See `SUPABASE_DEPLOYMENT.md` for the deploy
runbook and `SUPABASE_OPERATOR_AUTH.md` for the remaining operator account
setup.

## Requirements

- Python 3.11+
- `customtkinter`, `requests`, `pyperclip`
- Supabase project with Auth and Edge Functions enabled
- Riot Development API key for private prototype validation before approval;
  replace it with a Riot Production API key after Riot approval

## Riot Notice

LOL Tournament Code Creator is not endorsed by Riot Games and does not reflect
the views or opinions of Riot Games or anyone officially involved in producing
or managing Riot Games properties. Riot Games and all associated properties are
trademarks or registered trademarks of Riot Games, Inc.
