import { defineConfig } from "tsup";

// Main and preload are compiled to CommonJS because Electron loads them in the
// Node/preload runtime. `electron` and Node-only main dependencies stay external
// and are resolved at runtime; pure-JS deps (zod) are bundled so the sandboxed
// preload never performs a runtime `require` of a third-party module.
export default defineConfig({
  entry: {
    "main/index": "src/main/index.ts",
    "preload/index": "src/preload/index.ts",
  },
  outDir: "dist",
  format: ["cjs"],
  outExtension: () => ({ js: ".cjs" }),
  target: "node20",
  platform: "node",
  sourcemap: true,
  clean: true,
  splitting: false,
  dts: false,
  external: ["electron", "electron-updater"],
  noExternal: ["zod"],
});
