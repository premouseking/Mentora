import assert from "node:assert/strict";
import test from "node:test";

import { pnpmInvocation } from "./smoke-runtime.mjs";

test("Windows runs pnpm through ComSpec without shell mode", () => {
  assert.deepEqual(
    pnpmInvocation(["dev", "--host", "localhost"], {
      platform: "win32",
      comSpec: "C:\\Windows\\System32\\cmd.exe",
    }),
    {
      command: "C:\\Windows\\System32\\cmd.exe",
      args: ["/d", "/s", "/c", "pnpm dev --host localhost"],
    },
  );
});

test("Unix runs pnpm directly", () => {
  assert.deepEqual(
    pnpmInvocation(["dev", "--host", "localhost"], {
      platform: "linux",
    }),
    {
      command: "pnpm",
      args: ["dev", "--host", "localhost"],
    },
  );
});
