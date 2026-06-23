import { spawnSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { loadAndValidateSecrets, rootDir } from "./supabase-secret-utils.mjs";

const functionName = process.argv[2];
if (!["riot-tournament", "riot-callback"].includes(functionName)) {
  console.error("Usage: node tools/deploy-supabase-function.mjs <riot-tournament|riot-callback>");
  process.exit(1);
}

const validation = loadAndValidateSecrets();
const projectRef = validation.ok
  ? validation.projectRef
  : inferProjectRefFromBuildSettings();

if (!projectRef) {
  if (!validation.ok) console.error(validation.error);
  console.error("Unable to determine Supabase project ref.");
  process.exit(1);
}

if (!validation.ok) {
  console.warn(
    "Supabase secrets file not found or not usable; deploying function code only.",
  );
  console.warn("Existing Supabase secrets will not be changed.");
}

const result = spawnSync(process.execPath, [
  "tools/run-supabase-cli.mjs",
  "functions",
  "deploy",
  functionName,
  "--use-api",
  "--project-ref",
  projectRef,
], {
  cwd: rootDir,
  stdio: "inherit",
  shell: false,
});

process.exit(result.status ?? 1);

function inferProjectRefFromBuildSettings() {
  const envProjectRef = (process.env.SUPABASE_PROJECT_REF || "").trim();
  if (envProjectRef) return envProjectRef;

  const settingsPath = resolve(rootDir, "client_settings.py");
  if (!existsSync(settingsPath)) return "";

  const text = readFileSync(settingsPath, "utf8");
  const match = text.match(/SUPABASE_PROJECT_URL\s*=\s*["']([^"']+)["']/);
  if (!match) return "";

  try {
    const url = new URL(match[1].trim());
    return url.hostname.endsWith(".supabase.co")
      ? url.hostname.slice(0, -".supabase.co".length)
      : "";
  } catch (_error) {
    return "";
  }
}
