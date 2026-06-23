import { spawnSync } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { loadAndValidateSecrets } from "./supabase-secret-utils.mjs";

const rootDir = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const validation = loadAndValidateSecrets();
if (!validation.ok) {
  console.error(validation.error);
  process.exit(1);
}
const projectRef = validation.projectRef;
if (!projectRef) {
  console.error("Unable to determine Supabase project ref.");
  process.exit(1);
}

run("predeploy", [process.execPath, ["tools/predeploy-check.mjs"]]);

const projectArgs = ["--project-ref", projectRef];
run("deploy riot-tournament", [
  process.execPath,
  [
    "tools/run-supabase-cli.mjs",
    "functions",
    "deploy",
    "riot-tournament",
    "--use-api",
    ...projectArgs,
  ],
]);
run("deploy riot-callback", [
  process.execPath,
  [
    "tools/run-supabase-cli.mjs",
    "functions",
    "deploy",
    "riot-callback",
    "--use-api",
    ...projectArgs,
  ],
]);

console.log("Supabase Edge Function deployment commands completed.");

function run(label, [command, args]) {
  console.log(`\n== ${label} ==`);
  const result = spawnSync(command, args, {
    cwd: rootDir,
    stdio: "inherit",
    shell: false,
  });
  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }
}
