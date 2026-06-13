/** 进程级崩溃保护后再动态导入 bootstrap，便于隔离启动失败（§2） */
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
