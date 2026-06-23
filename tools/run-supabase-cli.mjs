import { spawnSync } from "node:child_process";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const rootDir = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const cliHome = join(rootDir, ".supabase-cli-home");
const executable = process.execPath;
const cliEntrypoint = join(rootDir, "node_modules", "supabase", "dist", "supabase.js");

const result = spawnSync(executable, [cliEntrypoint, ...process.argv.slice(2)], {
  cwd: rootDir,
  stdio: "inherit",
  shell: false,
  env: {
    ...process.env,
    HOME: cliHome,
    USERPROFILE: cliHome,
    SUPABASE_TELEMETRY_DISABLED: "1",
    DO_NOT_TRACK: "1",
  },
});

process.exit(result.status ?? 1);
