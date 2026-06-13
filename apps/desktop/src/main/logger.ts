/**
 * Minimal main-process logger. Logs must never contain access/refresh tokens,
 * raw learning answers, file contents, or pre-signed URLs
 * (desktop-client-architecture §4).
 */
type Level = "debug" | "info" | "warn" | "error";

function emit(level: Level, scope: string, message: string, meta?: unknown) {
  const line = `[${new Date().toISOString()}] [${level.toUpperCase()}] [${scope}] ${message}`;
  if (meta !== undefined) {
    // eslint-disable-next-line no-console
    console[level === "debug" ? "log" : level](line, meta);
  } else {
    // eslint-disable-next-line no-console
    console[level === "debug" ? "log" : level](line);
  }
}

export function createLogger(scope: string) {
  return {
    debug: (m: string, meta?: unknown) => emit("debug", scope, m, meta),
    info: (m: string, meta?: unknown) => emit("info", scope, m, meta),
    warn: (m: string, meta?: unknown) => emit("warn", scope, m, meta),
    error: (m: string, meta?: unknown) => emit("error", scope, m, meta),
  };
}

export type Logger = ReturnType<typeof createLogger>;
