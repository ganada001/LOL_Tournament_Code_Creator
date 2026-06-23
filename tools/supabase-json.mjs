import { spawnSync } from "node:child_process";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const rootDir = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const cliHome = join(rootDir, ".supabase-cli-home");
const cliEntrypoint = join(rootDir, "node_modules", "supabase", "dist", "supabase.js");

const result = spawnSync(
  process.execPath,
  [cliEntrypoint, "--output-format", "json", ...process.argv.slice(2)],
  {
    cwd: rootDir,
    encoding: "utf8",
    shell: false,
    env: {
      ...process.env,
      HOME: cliHome,
      USERPROFILE: cliHome,
      SUPABASE_TELEMETRY_DISABLED: "1",
      DO_NOT_TRACK: "1",
    },
  },
);

if (result.status !== 0) {
  if (result.stderr) process.stderr.write(result.stderr);
  if (result.stdout) process.stderr.write(result.stdout);
  process.exit(result.status ?? 1);
}

process.stdout.write(result.stdout || "");
