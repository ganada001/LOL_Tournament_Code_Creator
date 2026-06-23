import { existsSync, readdirSync } from "node:fs";
import { join, resolve } from "node:path";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

const rootDir = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const blockedPaths = [
  ".env",
  "config.json",
  "config/supabase-deploy-last.log",
  "config/supabase-redeploy-last.log",
  "config/supabase-deployment.json",
  "presets.json",
  "debug_stub.py",
  "supabase/.env",
  "supabase/.env.local",
  "supabase/.env.production.local",
  "supabase/.temp",
  "dist",
  "build",
  "__pycache__",
  "LOL_Tournament_Code_Creator-main/dist",
  "LOL_Tournament_Code_Creator-main/build",
  "LOL_Tournament_Code_Creator-main/.git",
  "LOL_Tournament_Code_Creator-main/config.json",
  "LOL_Tournament_Code_Creator-main/presets.json",
  "LOL_Tournament_Code_Creator",
  "LOL_Tournament_Code_Creator/.git",
];

const found = [];
for (const relativePath of blockedPaths) {
  if (existsSync(join(rootDir, relativePath))) found.push(relativePath);
}

for (const extra of findByName(rootDir, new Set(["__pycache__"]))) {
  found.push(extra);
}

const unique = [...new Set(found)].sort();
if (unique.length > 0) {
  console.error("Release guard found local-only/generated files:");
  for (const item of unique) console.error(`- ${item}`);
  console.error("Do not include these files in release bundles.");
  process.exit(1);
}

console.log("Release guard passed.");

function findByName(dir, names, base = rootDir) {
  const results = [];
  const skip = new Set([".git", "node_modules", ".supabase-cli-home"]);
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    if (skip.has(entry.name)) continue;

    const fullPath = join(dir, entry.name);
    const relative = fullPath.slice(base.length + 1);
    if (names.has(entry.name)) results.push(relative);
    results.push(...findByName(fullPath, names, base));
  }
  return results;
}
