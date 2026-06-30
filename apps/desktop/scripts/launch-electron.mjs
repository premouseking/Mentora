import { spawn } from "node:child_process";

function runPnpm(args) {
  const child =
    process.platform === "win32"
      ? spawn(process.env.ComSpec ?? "cmd.exe", [
          "/d",
          "/s",
          "/c",
          ["pnpm", ...args].join(" "),
        ], {
          env: process.env,
          stdio: "inherit",
        })
      : spawn("pnpm", args, {
          env: process.env,
          stdio: "inherit",
        });

  return new Promise((resolve, reject) => {
    child.on("error", reject);
    child.on("exit", (code, signal) => {
      if (code === 0) {
        resolve();
      } else {
        reject(new Error(`${args.join(" ")} exited with ${code ?? signal}`));
      }
    });
  });
}

if (!process.env.MENTORA_DEV_SERVER_URL) {
  throw new Error("MENTORA_DEV_SERVER_URL is required");
}

process.stdout.write(
  `[electron-launch] waiting for renderer and desktop bundles at ${process.env.MENTORA_DEV_SERVER_URL}\n`,
);
await runPnpm([
  "exec",
  "wait-on",
  process.env.MENTORA_DEV_SERVER_URL,
  "dist/main/index.cjs",
  "dist/preload/index.cjs",
]);
process.stdout.write("[electron-launch] renderer and bundles are ready\n");
process.stdout.write("[electron-launch] starting Electron\n");
await runPnpm(["exec", "electron", "."]);
