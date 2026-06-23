# File Inventory

This inventory is organized by path and purpose. It excludes `.git` internals
and does not expose local secret values.

## Root Application

- `api_client.py` - Supabase-backed Riot Tournament API client, validation,
  timeout, retry, and rate-limit handling.
- `client_settings.py` - Public build-time Supabase client settings.
- `config_manager.py` - Local configuration loading, legacy-field stripping,
  Supabase validation, and Production readiness warnings.
- `discord_helper.py` - Discord webhook validation and safe notification
  sending.
- `gui_main.py` - CustomTkinter desktop GUI.
- `main.py` - CLI entry point.
- `config/presets.json.example` - Safe preset template. Runtime presets are
  saved under `%APPDATA%/LOL_Tournament_Code_Creator/`.

## Supabase Backend

- `supabase/config.toml` - Edge Function JWT verification settings.
- `supabase/functions/riot-tournament/index.ts` - Authenticated Supabase Edge
  Function for allowed Riot Tournament API actions.
- `supabase/functions/riot-callback/index.ts` - Riot callback endpoint.
- `supabase/.env.example` - Safe Supabase secret-name template.
- `supabase/.env.production.example` - Safe template for the ignored deployment
  secret file.

## Documentation And Metadata

- `README.md` - Project overview and Supabase security model.
- `RIOT_PRODUCTION_READINESS.md` - Riot Production readiness checklist.
- `RIOT_APPROVAL_SUBMISSION.md` - Riot Developer Portal submission notes for
  the approval-ready prototype stage.
- `PRODUCTION_BACKEND_ARCHITECTURE.md` - Supabase backend trust-boundary notes.
- `SUPABASE_DEPLOYMENT.md` - Supabase login, secret, and Edge Function deploy
  runbook.
- `SUPABASE_OPERATOR_AUTH.md` - Manual Supabase Auth operator-user setup and
  offboarding notes.
- `FILE_INVENTORY.md` - This path-based inventory.
- `requirements.txt` - Python dependencies.
- `riot.txt` - Riot verification text file.
- `.gitattributes` - Git line-ending/file handling metadata.
- `.gitignore` - Ignore rules for local secrets, generated files, and build
  artifacts.
- `package.json` - Local Deno and Supabase CLI scripts.
- `package-lock.json` - Locked local CLI dependency versions.
- `tools/predeploy-check.mjs` - Combined predeploy guard for Edge Function
  checks, Python regressions, Supabase config, and blocked string scanning.
- `tools/supabase-secret-utils.mjs` - Shared parser and validation helpers for
  ignored Supabase secret files.
- `tools/check-supabase-secrets.mjs` - Local-only Supabase secret file validator.
- `tools/set-supabase-secrets.mjs` - Validates and uploads ignored local
  Supabase secret files without printing secret values.
- `tools/deploy-supabase-functions.mjs` - Runs predeploy checks and deploys both
  Supabase Edge Functions using API bundling.
- `tools/deploy-supabase-function.mjs` - Deploys one Edge Function with the
  validated project ref from the local secret file.
- `tools/postdeploy-check.mjs` - Verifies deployed Supabase Edge Function names
  and required secret names after deployment.
- `tools/release-guard.mjs` - Fails release preparation when local-only files or
  generated artifacts are present.
- `tools/readiness-report.mjs` - Prints local tool, secret, and release readiness
  without exposing secret values.
- `tools/run-supabase-cli.mjs` - Supabase CLI wrapper that keeps CLI state in
  the workspace-local `.supabase-cli-home/` folder.
- `tools/supabase-json.mjs` - Supabase CLI JSON wrapper used by deployment
  scripts when stderr must not be mixed with JSON output.
- `tools/deploy-supabase-production.ps1` - Interactive Supabase project and
  Edge Function deployment helper.
- `tools/update-riot-api-key.ps1` - Updates only the Supabase `RIOT_API_KEY`
  secret when the Development key rotates or Production key is approved.

## Tests

- `tests/test_security_controls.py` - Security, config, Supabase request-shape,
  callback non-exposure, and validation regression tests.

## Local Runtime Files

These files are local-only and should remain ignored by git. The packaged app
stores runtime settings and Discord presets under
`%APPDATA%/LOL_Tournament_Code_Creator/`; root copies are legacy/source-run
inputs and must not be bundled as release defaults.

- `.env` - Local environment variables. Do not commit.
- `config.json` - Local app settings. Do not commit.
- `presets.json` - Local Discord preset settings. Do not commit.

## Local Tooling Or Generated Folders

These should not be committed:

- `__pycache__/` - Python bytecode cache.
- `.agents/` - Local agent/tooling metadata.
- `.codex/` - Local Codex metadata.
- `node_modules/` - Local npm dependencies for Deno and Supabase CLI.
- `.supabase-cli-home/` - Workspace-local Supabase CLI state/cache.
- `scripts/` - Empty/obsolete helper folder if present.
- `LOL_Tournament_Code_Creator/` - Nested/unused folder if present.

## Public GitHub Pages Site

Path: `LOL_Tournament_Code_Creator-main/`

This folder contains only public GitHub Pages content. The root application and
root `supabase/` directory are the current source of truth.

Important nested files:

- `LOL_Tournament_Code_Creator-main/index.html` - Public project page.
- `LOL_Tournament_Code_Creator-main/privacy.html` - Public privacy page.
- `LOL_Tournament_Code_Creator-main/tos.html` - Public terms page.
- `LOL_Tournament_Code_Creator-main/riot.txt` - Riot domain verification text.
- `LOL_Tournament_Code_Creator-main/assets/` - Public screenshots.
- `LOL_Tournament_Code_Creator-main/legal/` - Privacy and terms markdown source.

Nested desktop source, Supabase backend copies, build scripts, and duplicate
requirements files were removed to keep one source of truth.
