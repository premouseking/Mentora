import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const desktopDir = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
);

test("desktop window uses the Mentora icon path from config", () => {
  const configSource = fs.readFileSync(
    path.join(desktopDir, "src", "main", "config.ts"),
    "utf8",
  );
  const windowSource = fs.readFileSync(
    path.join(desktopDir, "src", "main", "window.ts"),
    "utf8",
  );

  assert.match(configSource, /export function resolveWindowIconPath\(\)/);
  assert.match(windowSource, /icon:\s*resolveWindowIconPath\(\)/);
});

test("desktop window uses renderer-owned chrome", () => {
  const windowSource = fs.readFileSync(
    path.join(desktopDir, "src", "main", "window.ts"),
    "utf8",
  );
  const bootstrapSource = fs.readFileSync(
    path.join(desktopDir, "src", "main", "bootstrap.ts"),
    "utf8",
  );

  assert.match(windowSource, /frame:\s*false/);
  assert.match(bootstrapSource, /Menu\.setApplicationMenu\(null\)/);
});

test("Windows packaging explicitly uses the Mentora ICO asset", () => {
  const builderConfig = fs.readFileSync(
    path.join(desktopDir, "electron-builder.yml"),
    "utf8",
  );

  assert.match(builderConfig, /win:\s*\r?\n\s+icon:\s+build\/icon\.ico/);
});
