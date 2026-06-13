/**
 * Crash-safe entry point. Per the Lightest experience (desktop §2), main.ts only
 * installs crash protection and starts the bootstrap; all business
 * initialization lives in a diagnosable bootstrap module that is imported only
 * after the process-level handlers are registered.
 */
process.on("uncaughtException", (err) => {
  // eslint-disable-next-line no-console
  console.error("[FATAL] uncaughtException", err);
});

process.on("unhandledRejection", (reason) => {
  // eslint-disable-next-line no-console
  console.error("[FATAL] unhandledRejection", reason);
});

import("./bootstrap")
  .then(({ bootstrap }) => bootstrap())
  .catch((err) => {
    // eslint-disable-next-line no-console
    console.error("[FATAL] bootstrap import failed", err);
  });
