import assert from "node:assert/strict";
import test from "node:test";

import { terminateProcessTree } from "./process-tree.mjs";

test("Windows terminates the complete process tree with taskkill", () => {
  const calls = [];

  terminateProcessTree(
    { pid: 1234, exitCode: null, killed: false },
    {
      platform: "win32",
      spawnSync: (...args) => calls.push(args),
      kill: () => {
        throw new Error("kill should not be used on Windows");
      },
    },
  );

  assert.deepEqual(calls, [
    ["taskkill", ["/PID", "1234", "/T", "/F"], { stdio: "ignore" }],
  ]);
});

test("Unix terminates the child process group", () => {
  const calls = [];

  terminateProcessTree(
    { pid: 4321, exitCode: null, killed: false },
    {
      platform: "linux",
      spawnSync: () => {
        throw new Error("spawnSync should not be used on Unix");
      },
      kill: (...args) => calls.push(args),
    },
  );

  assert.deepEqual(calls, [[-4321, "SIGTERM"]]);
});

test("already exited or missing children are ignored", () => {
  let called = false;
  const dependencies = {
    platform: "win32",
    spawnSync: () => {
      called = true;
    },
    kill: () => {
      called = true;
    },
  };

  terminateProcessTree(undefined, dependencies);
  terminateProcessTree(
    { pid: 1234, exitCode: 0, killed: false },
    dependencies,
  );

  assert.equal(called, false);
});
