import { spawnSync } from "node:child_process";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const rootDir = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const isWindows = process.platform === "win32";
const python = process.env.PYTHON ||
  (isWindows
    ? "C:\\Users\\a\\AppData\\Local\\Programs\\Python\\Python313\\python.exe"
    : "python3");
const pythonCheck = isWindows
  ? {
    command: "C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
    args: [
      "-NoProfile",
      "-ExecutionPolicy",
      "Bypass",
      "-Command",
      `& '${python.replaceAll("'", "''")}' -B -X utf8 -m unittest discover -s tests`,
    ],
  }
  : {
    command: python,
    args: ["-B", "-X", "utf8", "-m", "unittest", "discover", "-s", "tests"],
  };
const pythonModules = [
  "api_client.py",
  "client_settings.py",
  "config_manager.py",
  "discord_helper.py",
  "gui_main.py",
  "main.py",
  "src/api_client.py",
  "src/client_settings.py",
  "src/config_manager.py",
  "src/discord_helper.py",
  "src/gui_main.py",
  "src/main.py",
];
const pythonCompileCheck = isWindows
  ? {
    command: "C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
    args: [
      "-NoProfile",
      "-ExecutionPolicy",
      "Bypass",
      "-Command",
      `& '${python.replaceAll("'", "''")}' -B -X utf8 -m py_compile ${
        pythonModules.map((module) => `'${module.replaceAll("'", "''")}'`)
          .join(" ")
      }`,
    ],
  }
  : {
    command: python,
    args: ["-B", "-X", "utf8", "-m", "py_compile", ...pythonModules],
  };
const npmCli = process.env.npm_execpath || "";
const npmCommand = npmCli ? process.execPath : isWindows ? "npm.cmd" : "npm";
const npmArgs = (script) => npmCli ? [npmCli, "run", script] : ["run", script];

const checks = [
  {
    name: "Deno function format",
    command: npmCommand,
    args: npmArgs("functions:fmt:check"),
    shell: !npmCli && isWindows,
  },
  {
    name: "Deno function type-check",
    command: npmCommand,
    args: npmArgs("functions:check"),
    shell: !npmCli && isWindows,
  },
  {
    name: "Python security regression tests",
    ...pythonCheck,
  },
  {
    name: "Python module compile",
    ...pythonCompileCheck,
  },
];

for (const check of checks) {
  console.log(`\n== ${check.name} ==`);
  const result = spawnSync(check.command, check.args, {
    cwd: rootDir,
    stdio: "inherit",
    shell: Boolean(check.shell),
  });
  if (result.error) {
    console.error(result.error.message);
  }
  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }
}

console.log("\n== Supabase config guard ==");
const configPath = join(rootDir, "supabase", "config.toml");
const config = readFileSync(configPath, "utf8");
assertIncludes(config, "[functions.riot-tournament]", configPath);
assertIncludes(config, "verify_jwt = true", configPath);
assertIncludes(config, "[functions.riot-callback]", configPath);
assertIncludes(config, "verify_jwt = false", configPath);
console.log("Supabase function JWT settings OK");

console.log("\n== Callback metadata guard ==");
const tournamentFunction = readFileSync(
  join(rootDir, "supabase", "functions", "riot-tournament", "index.ts"),
  "utf8",
);
const callbackFunction = readFileSync(
  join(rootDir, "supabase", "functions", "riot-callback", "index.ts"),
  "utf8",
);
assertIncludes(
  tournamentFunction,
  "RIOT_CALLBACK_SECRET",
  "supabase/functions/riot-tournament/index.ts",
);
assertIncludes(
  callbackFunction,
  "verifyCallbackMetadata",
  "supabase/functions/riot-callback/index.ts",
);
assertIncludes(
  callbackFunction,
  "RIOT_CALLBACK_SECRET is not configured.",
  "supabase/functions/riot-callback/index.ts",
);
assertNotIncludes(
  callbackFunction,
  "verified: false",
  "supabase/functions/riot-callback/index.ts",
);
assertIncludes(
  readFileSync(join(rootDir, "supabase", ".env.production.example"), "utf8"),
  "RIOT_CALLBACK_SECRET=",
  "supabase/.env.production.example",
);
console.log("Callback metadata validation wiring OK");

console.log("\n== Secret and legacy transport scan ==");
const findings = [];
scanTree(rootDir, findings);
if (findings.length > 0) {
  for (const finding of findings) {
    console.error(`${finding.file}: ${finding.reason}`);
  }
  process.exit(1);
}
console.log("No blocked secret/legacy transport strings found");

console.log("\nPredeploy checks passed.");

function assertIncludes(text, expected, file) {
  if (!text.includes(expected)) {
    console.error(`${file}: missing ${expected}`);
    process.exit(1);
  }
}

function assertNotIncludes(text, blocked, file) {
  if (text.includes(blocked)) {
    console.error(`${file}: blocked fallback remains: ${blocked}`);
    process.exit(1);
  }
}

function scanTree(dir, findings) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const fullPath = join(dir, entry.name);
    if (entry.isDirectory()) {
      if (shouldSkipDirectory(entry.name)) continue;
      scanTree(fullPath, findings);
      continue;
    }
    if (!entry.isFile() || shouldSkipFile(entry.name)) continue;

    const size = statSync(fullPath).size;
    if (size > 1024 * 1024) continue;

    const text = readFileSync(fullPath, "utf8");
    const relative = fullPath.slice(rootDir.length + 1);
    const blocked = [
      [/RGAPI-[A-Za-z0-9_-]+/, "Riot API key-like value"],
      [/PROXY_AUTH_TOKEN/, "legacy shared proxy token reference"],
      [/Google Apps Script/i, "legacy GAS backend reference"],
      [/Backend Proxy URL/i, "legacy backend proxy URL reference"],
      [/SUPABASE_SERVICE_ROLE_KEY\s*=/, "Supabase service role key assignment"],
      [/service_role\s*[:=]\s*["'][^"']+["']/i, "Supabase service role value"],
    ];
    for (const [pattern, reason] of blocked) {
      if (pattern.test(text)) findings.push({ file: relative, reason });
    }
  }
}

function shouldSkipDirectory(name) {
  return new Set([
    ".git",
    ".agents",
    ".codex",
    ".supabase-cli-home",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
  ]).has(name);
}

function shouldSkipFile(name) {
  return (
    name === "predeploy-check.mjs" ||
    name.endsWith(".pyc") ||
    name.endsWith(".png") ||
    name.endsWith(".jpg") ||
    name.endsWith(".jpeg") ||
    name.endsWith(".exe") ||
    name.endsWith(".zip")
  );
}
