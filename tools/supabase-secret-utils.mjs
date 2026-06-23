import { existsSync, readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

export const rootDir = resolve(dirname(fileURLToPath(import.meta.url)), "..");

export function resolveSecretsFile() {
  return resolve(
    rootDir,
    process.env.SUPABASE_SECRETS_FILE || "supabase/.env.production.local",
  );
}

export function loadAndValidateSecrets() {
  const secretsFile = resolveSecretsFile();
  if (!existsSync(secretsFile)) {
    return {
      ok: false,
      error: `Missing secrets file: ${secretsFile}\nCreate it from supabase/.env.production.example.`,
    };
  }

  const secrets = parseEnvFile(readFileSync(secretsFile, "utf8"));
  const required = [
    "RIOT_API_KEY",
    "RIOT_CALLBACK_URL",
    "RIOT_CALLBACK_SECRET",
    "ALLOWED_OPERATOR_EMAILS",
  ];
  const missing = required.filter((key) => !secrets[key]);
  if (missing.length > 0) {
    return {
      ok: false,
      error: `Missing required Supabase secrets: ${missing.join(", ")}`,
    };
  }

  const riotKeyPrefix = ["RG", "API-"].join("");
  if (!secrets.RIOT_API_KEY.startsWith(riotKeyPrefix)) {
    return {
      ok: false,
      error:
        "RIOT_API_KEY should be a Riot API key. Use a development key before Riot approval, then replace it with the production key after approval.",
    };
  }

  let callbackUrl;
  try {
    callbackUrl = new URL(secrets.RIOT_CALLBACK_URL);
  } catch (_error) {
    return {
      ok: false,
      error:
        "RIOT_CALLBACK_URL must be an HTTPS URL ending in /functions/v1/riot-callback.",
    };
  }
  if (
    callbackUrl.protocol !== "https:" ||
    !callbackUrl.pathname.endsWith("/functions/v1/riot-callback")
  ) {
    return {
      ok: false,
      error:
        "RIOT_CALLBACK_URL must be an HTTPS URL ending in /functions/v1/riot-callback.",
    };
  }

  const callbackProjectRef = callbackUrl.hostname.endsWith(".supabase.co")
    ? callbackUrl.hostname.slice(0, -".supabase.co".length)
    : "";
  const envProjectRef = (process.env.SUPABASE_PROJECT_REF || "").trim();
  if (envProjectRef && callbackProjectRef && envProjectRef !== callbackProjectRef) {
    return {
      ok: false,
      error:
        "SUPABASE_PROJECT_REF does not match RIOT_CALLBACK_URL project ref.",
    };
  }

  if (
    !secrets.ALLOWED_OPERATOR_EMAILS.split(",").some((email) =>
      /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())
    )
  ) {
    return {
      ok: false,
      error: "ALLOWED_OPERATOR_EMAILS must contain at least one email address.",
    };
  }

  if (secrets.RIOT_CALLBACK_SECRET.length < 32) {
    return {
      ok: false,
      error: "RIOT_CALLBACK_SECRET must be at least 32 characters.",
    };
  }

  return {
    ok: true,
    secrets,
    secretsFile,
    projectRef: envProjectRef || callbackProjectRef,
  };
}

function parseEnvFile(text) {
  const values = {};
  for (const line of text.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const match = trimmed.match(/^([A-Za-z_][A-Za-z0-9_]*)=(.*)$/);
    if (!match) continue;
    const key = match[1];
    let value = match[2].trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    values[key] = value;
  }
  return values;
}
