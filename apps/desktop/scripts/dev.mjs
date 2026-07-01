import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const desktopDir = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
);
const repoRoot = path.resolve(desktopDir, "..", "..");

function loadRootEnv() {
  const envPath = path.join(repoRoot, ".env");
  if (!fs.existsSync(envPath)) return;

  const lines = fs.readFileSync(envPath, "utf8").split(/\r?\n/);
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;

    const match = trimmed.match(/^([A-Za-z_][A-Za-z0-9_]*)=(.*)$/);
    if (!match) continue;

    const [, key, rawValue] = match;
    if (process.env[key]) continue;

    process.env[key] = rawValue.replace(/^(['"])(.*)\1$/, "$2");
  }
}

function requireEnv(name) {
  if (!process.env[name]) {
    throw new Error(`${name} is required. Set it in ${path.join(repoRoot, ".env")}`);
  }
}

function pnpm(args, options = {}) {
  if (process.platform === "win32") {
    return spawn(
      process.env.ComSpec ?? "cmd.exe",
      ["/d", "/s", "/c", ["pnpm", ...args].join(" ")],
      options,
    );
  }

  return spawn("pnpm", args, options);
}

function pipe(name, stream, writer) {
  stream?.on("data", (chunk) => {
    for (const line of chunk.toString().split(/\r?\n/)) {
      if (line) writer.write(`[${name}] ${line}\n`);
    }
  });
}

function startLogged(name, args) {
  const child = pnpm(args, {
    cwd: desktopDir,
    env: process.env,
    stdio: ["ignore", "pipe", "pipe"],
  });
  pipe(name, child.stdout, process.stdout);
  pipe(name, child.stderr, process.stderr);
  child.on("exit", (code, signal) => {
    if (shuttingDown) return;
    if (code === 0 || signal) return;
    shutdown(code ?? 1);
  });
  return child;
}

function shutdown(code = 0) {
  shuttingDown = true;
  for (const child of children) {
    if (!child.killed) child.kill();
  }
  process.exitCode = code;
}

let shuttingDown = false;
const children = [];

loadRootEnv();

for (const name of [
  "MENTORA_DEV_SERVER_URL",
  "MENTORA_API_BASE_URL",
  "MENTORA_OBJECT_STORAGE_ORIGIN",
]) {
  requireEnv(name);
}

children.push(startLogged("bundle", ["exec", "tsup", "--watch"]));
children.push(
  startLogged("electron", [
    "exec",
    "nodemon",
    "--delay",
    "300ms",
    "--watch",
    "dist/main/index.cjs",
    "--watch",
    "dist/preload/index.cjs",
    "-e",
    "cjs",
    "--exec",
    "node",
    "scripts/launch-electron.mjs",
  ]),
);

process.on("SIGINT", () => shutdown());
process.on("SIGTERM", () => shutdown());
