import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const buildDir = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
  "build",
);

function readPngSize(buffer) {
  assert.equal(buffer.subarray(1, 4).toString("ascii"), "PNG");
  return {
    width: buffer.readUInt32BE(16),
    height: buffer.readUInt32BE(20),
  };
}

test("generated PNG assets use the expected dimensions", () => {
  const master = fs.readFileSync(path.join(buildDir, "icon.png"));
  const development = fs.readFileSync(path.join(buildDir, "icon-dev.png"));

  assert.deepEqual(readPngSize(master), { width: 1024, height: 1024 });
  assert.deepEqual(readPngSize(development), { width: 256, height: 256 });
});

test("generated ICO contains all Windows taskbar sizes", () => {
  const ico = fs.readFileSync(path.join(buildDir, "icon.ico"));
  const count = ico.readUInt16LE(4);
  const sizes = [];

  for (let index = 0; index < count; index += 1) {
    const entryOffset = 6 + index * 16;
    const width = ico.readUInt8(entryOffset);
    sizes.push(width === 0 ? 256 : width);
  }

  assert.deepEqual(sizes, [16, 24, 32, 48, 64, 128, 256]);
});
