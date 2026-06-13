/**
 * Central IPC channel registry. Channels follow the `mentora:<domain>:<action>`
 * convention from desktop-client-architecture §3.2. main and preload import the
 * same constants so a renderer can never invoke an unregistered channel.
 */
export const Channels = {
  app: {
    info: "mentora:app:info",
  },
  auth: {
    status: "mentora:auth:status",
    login: "mentora:auth:login",
    logout: "mentora:auth:logout",
    changed: "mentora:auth:changed",
  },
  api: {
    request: "mentora:api:request",
  },
  events: {
    open: "mentora:events:open",
    abort: "mentora:events:abort",
    message: "mentora:events:message",
  },
  files: {
    pick: "mentora:files:pick",
  },
  uploads: {
    start: "mentora:uploads:start",
    cancel: "mentora:uploads:cancel",
    progress: "mentora:uploads:progress",
  },
  shell: {
    openExternal: "mentora:shell:open-external",
    showItemInFolder: "mentora:shell:show-item-in-folder",
  },
  notifications: {
    show: "mentora:notifications:show",
    activated: "mentora:notifications:activated",
  },
  updater: {
    check: "mentora:updater:check",
    quitAndInstall: "mentora:updater:quit-and-install",
    status: "mentora:updater:status",
  },
  window: {
    minimize: "mentora:window:minimize",
    toggleMaximize: "mentora:window:toggle-maximize",
    close: "mentora:window:close",
    deepLink: "mentora:window:deep-link",
  },
} as const;

export type ChannelMap = typeof Channels;
