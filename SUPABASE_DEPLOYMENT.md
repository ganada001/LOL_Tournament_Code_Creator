# Supabase Deployment Runbook

This runbook is for deploying the Riot Tournament API backend without putting
Riot secrets in the desktop app.

## Prerequisites

- Supabase account access token created at
  `https://supabase.com/dashboard/account/tokens`.
- Supabase project created, or permission to create one in the target
  organization.
- Supabase Auth email/password provider enabled.
- Trusted operator user created in Supabase Auth.
- Riot API key available:
  - Before Riot approval, use the temporary Development API key for private
    prototype validation only.
  - After Riot approval, replace it with the Production API key.
- Local CLI tooling installed with `npm install`.

## Approval-Ready One-Command Flow

For a fresh setup, run:

```powershell
npm run supabase:deploy:approval
```

Before Riot Production approval, enter the Riot Development API key when
prompted. After Riot approval, run `npm run riot-key:update` and replace only
the Supabase `RIOT_API_KEY` secret with the Production key.

## Verify Local Tooling

```powershell
npm run deno -- --version
npm run supabase:version
npm run functions:fmt:check
npm run functions:check
npm run readiness
npm run predeploy
```

Expected installed versions:

- Deno `2.8.3`
- Supabase CLI `2.107.0`

## Login And Link Project

```powershell
npm run supabase:login
npm run supabase:projects
npm run supabase:link -- --project-ref <your-project-ref>
```

The wrapper stores Supabase CLI state under `.supabase-cli-home/`, not under the
Windows user profile.

## Configure Secrets

Create an ignored local secret file from the example:

```powershell
Copy-Item supabase/.env.production.example supabase/.env.production.local
```

Fill in:

```text
RIOT_API_KEY=<riot-development-key-before-approval-or-production-key-after-approval>
RIOT_CALLBACK_URL=https://<project-ref>.supabase.co/functions/v1/riot-callback
RIOT_CALLBACK_SECRET=<random-32-plus-character-secret>
ALLOWED_OPERATOR_EMAILS=operator@example.com
RIOT_TOURNAMENT_ROUTING=americas
```

Upload the secrets without placing values directly on the command line:

```powershell
npm run secrets:check
npm run secrets:set
npm run secrets:list
```

`RIOT_CALLBACK_URL` must point to a deployed URL that forwards to the
`riot-callback` Edge Function. For live Tournament API callbacks, verify the
final URL against Riot's documented callback port, TLD, and certificate
restrictions. If the default Supabase HTTPS domain is not accepted by Riot
callbacks, configure a compatible HTTP reverse proxy or approved-certificate
custom domain.
`RIOT_CALLBACK_SECRET` signs Tournament Code metadata and lets the public
callback endpoint reject forged callback payloads.
`RIOT_TOURNAMENT_ROUTING` defaults to `americas`, which is the verified working
Tournament API route for this project. Change it only if Riot explicitly
instructs another Tournament API routing host after approval.

If you are still waiting for Riot Production approval, the Development API key
may need to be refreshed regularly. Update only the Supabase secret:

```powershell
npm run riot-key:update
```

This command asks for a Supabase account access token and the new Riot API key.
It uploads a temporary env file directly to Supabase and deletes the local temp
file afterward.

After Riot approves the product and issues a Production API key, run the same
command once with the Production key.

## Deploy Functions

```powershell
npm run functions:deploy
npm run postdeploy
```

Or deploy one function at a time:

```powershell
npm run functions:deploy:riot-tournament
npm run functions:deploy:riot-callback
npm run postdeploy
```

## Desktop App Settings

Before building the desktop app, set these public values in `client_settings.py`:

- Supabase Project URL: `https://<project-ref>.supabase.co`
- Supabase Anon Key: the project's anon/public key

In the desktop app settings, enter:

- Authentication email: the allowed Supabase Auth operator email
- Authentication password: used only for authentication; it is not stored

Do not enter a Riot API key, callback URL, service-role key, or secret key in
the desktop app.

## Smoke Test

1. Keep `Stub API` enabled.
2. Save settings and complete operator authentication.
3. Create a Provider ID.
4. Generate one tournament code.

Only after Stub flow succeeds should Production mode be used.

## Release Bundle Guard

Before creating or publishing a release bundle, run:

```powershell
npm run release:guard
```

This intentionally fails if local-only files such as `.env`, `config.json`,
`presets.json`, build folders, or cached bytecode are present in the source tree.
Do not include those files in release artifacts.
