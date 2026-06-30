import { spawnSync } from "node:child_process";

export function terminateProcessTree(
  child,
  {
    platform = process.platform,
    spawnSync: runSync = spawnSync,
    kill = process.kill,
  } = {},
) {
  if (!child?.pid || child.exitCode !== null) return;

  if (platform === "win32") {
    runSync("taskkill", ["/PID", String(child.pid), "/T", "/F"], {
      stdio: "ignore",
    });
    return;
  }

  try {
    kill(-child.pid, "SIGTERM");
  } catch (error) {
    if (error?.code !== "ESRCH") throw error;
  }
}
