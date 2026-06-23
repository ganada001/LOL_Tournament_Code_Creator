import { loadAndValidateSecrets } from "./supabase-secret-utils.mjs";

const result = loadAndValidateSecrets();
if (!result.ok) {
  console.error(result.error);
  process.exit(1);
}

console.log("Supabase local secret file is valid.");
console.log(`Secrets file: ${result.secretsFile}`);
console.log(`Project ref: ${result.projectRef || "(not inferred)"}`);
