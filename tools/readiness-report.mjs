import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { join } from "node:path";
import { loadAndValidateSecrets, resolveSecretsFile, rootDir } from "./supabase-secret-utils.mjs";

const rows = [];
const npmCli = process.env.npm_execpath;
const npmCommand = npmCli
  ? [process.execPath, npmCli]
  : [process.platform === "win32" ? "npm.cmd" : "npm"];

rows.push(checkCommand("Deno", [...npmCommand, "run", "deno", "--", "--version"]));
rows.push(checkCommand("Supabase CLI", [process.execPath, "tools/run-supabase-cli.mjs", "--version"]));
rows.push(checkCommand("Edge Function types", [...npmCommand, "run", "functions:check"]));
rows.push(checkCommand("Edge Function format", [...npmCommand, "run", "functions:fmt:check"]));

const secretsFile = resolveSecretsFile();
const secrets = existsSync(secretsFile)
  ? loadAndValidateSecrets()
  : {
    ok: true,
    projectRef: "",
    absent: true,
  };
rows.push({
  label: "Local Supabase secrets",
  ok: secrets.ok,
  detail: secrets.absent
    ? "absent; expected after deployment"
    : secrets.ok
    ? `project ref ${secrets.projectRef || "not inferred"}`
    : secrets.error.split("\n")[0],
});

rows.push({
  label: "Local release guard blockers",
  ok: !hasReleaseBlockers(),
  detail: hasReleaseBlockers() ? "local-only files are present" : "none",
});

console.log("\nReadiness report");
for (const row of rows) {
  console.log(`${row.ok ? "OK " : "NO "} ${row.label}: ${row.detail}`);
}

if (rows.some((row) => !row.ok)) {
  process.exit(1);
}

function checkCommand(label, commandLine) {
  const [command, ...args] = commandLine;
  const result = spawnSync(command, args, {
    cwd: rootDir,
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
    shell: false,
  });
  const output = summarizeOutput(`${result.stdout || ""}${result.stderr || ""}`);
  return {
    label,
    ok: result.status === 0,
    detail: result.status === 0 ? output : output || "failed",
  };
}

function summarizeOutput(text) {
  const lines = text
    .replace(/\x1b\[[0-9;]*m/g, "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .filter((line) => !line.startsWith("> "));
  return lines[0] || "passed";
}

function hasReleaseBlockers() {
  const paths = [
    ".env",
    "config.json",
    "config/supabase-deploy-last.log",
    "config/supabase-deployment.json",
    "presets.json",
    "supabase/.temp",
    "supabase/.env.production.local",
    "build",
    "dist",
    "__pycache__",
  ];
  return paths.some((relativePath) => existsSync(join(rootDir, relativePath)));
}
