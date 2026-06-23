import { spawnSync } from "node:child_process";
import { loadAndValidateSecrets, rootDir } from "./supabase-secret-utils.mjs";

const validation = loadAndValidateSecrets();
if (!validation.ok) {
  console.error(validation.error);
  process.exit(1);
}
if (!validation.projectRef) {
  console.error("Unable to determine Supabase project ref.");
  process.exit(1);
}

const projectArgs = [
  "--project-ref",
  validation.projectRef,
  "--output-format",
  "json",
];

const functions = runJson("functions list", [
  "tools/run-supabase-cli.mjs",
  "functions",
  "list",
  ...projectArgs,
]);
const functionNames = collectValues(functions, ["name", "slug"]);
for (const expected of ["riot-tournament", "riot-callback"]) {
  if (!functionNames.has(expected)) {
    console.error(`Missing deployed Edge Function: ${expected}`);
    process.exit(1);
  }
}
console.log("Required Supabase Edge Functions are deployed.");

const secrets = runJson("secrets list", [
  "tools/run-supabase-cli.mjs",
  "secrets",
  "list",
  ...projectArgs,
]);
const secretNames = collectValues(secrets, ["name", "key"]);
for (
  const expected of [
    "RIOT_API_KEY",
    "RIOT_CALLBACK_URL",
    "RIOT_CALLBACK_SECRET",
    "ALLOWED_OPERATOR_EMAILS",
  ]
) {
  if (!secretNames.has(expected)) {
    console.error(`Missing Supabase secret: ${expected}`);
    process.exit(1);
  }
}
console.log("Required Supabase secrets are configured.");
console.log("Postdeploy checks passed.");

function runJson(label, args) {
  console.log(`\n== ${label} ==`);
  const result = spawnSync(process.execPath, args, {
    cwd: rootDir,
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
    shell: false,
  });
  if (result.status !== 0) {
    if (result.stderr) console.error(result.stderr.trim());
    if (result.stdout) console.error(result.stdout.trim());
    process.exit(result.status ?? 1);
  }

  const output = (result.stdout || "").trim();
  try {
    return JSON.parse(output);
  } catch (_error) {
    console.error(`Unable to parse ${label} JSON output.`);
    if (output) console.error(output);
    process.exit(1);
  }
}

function collectValues(value, keys) {
  const result = new Set();
  visit(value);
  return result;

  function visit(node) {
    if (Array.isArray(node)) {
      for (const item of node) visit(item);
      return;
    }
    if (!node || typeof node !== "object") return;
    for (const key of keys) {
      if (typeof node[key] === "string") result.add(node[key]);
    }
    for (const child of Object.values(node)) visit(child);
  }
}
