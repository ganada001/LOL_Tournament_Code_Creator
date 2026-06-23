import { spawnSync } from "node:child_process";
import { loadAndValidateSecrets, rootDir } from "./supabase-secret-utils.mjs";

const validation = loadAndValidateSecrets();
if (!validation.ok) {
  console.error(validation.error);
  process.exit(1);
}

const args = [
  "tools/run-supabase-cli.mjs",
  "secrets",
  "set",
  "--env-file",
  validation.secretsFile,
];
if (validation.projectRef) {
  args.push("--project-ref", validation.projectRef);
}

console.log("Uploading Supabase secrets from ignored local env file.");
const result = spawnSync(process.execPath, args, {
  cwd: rootDir,
  stdio: "inherit",
  shell: false,
});
process.exit(result.status ?? 1);
