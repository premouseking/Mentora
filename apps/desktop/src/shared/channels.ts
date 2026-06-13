/**
 * IPC 通道注册表（单一来源）
 *
 * 约定：`mentora:<domain>:<action>`
 *
 * 约束：
 * - main 与 preload 须从此处导入，禁止硬编码 channel
 * - invoke 通道 payload 须在 main 侧 zod 校验（schemas.ts）
 * - 广播通道不得向 renderer 转发 IpcRendererEvent
 *
 * @see docs/architecture/desktop-client-architecture.md §3.2
 */

export const CHANNEL_PREFIX = "mentora" as const;

export type IpcChannelName = `${typeof CHANNEL_PREFIX}:${string}:${string}`;

const CHANNEL_NAME_PATTERN = /^mentora:[a-z][a-z0-9-]*:[a-z][a-z0-9-]*$/;

function ipcChannel<
  const Domain extends string,
  const Action extends string,
>(
  domain: Domain,
  action: Action,
): `${typeof CHANNEL_PREFIX}:${Domain}:${Action}` {
  const name = `${CHANNEL_PREFIX}:${domain}:${action}`;
  if (process.env.NODE_ENV !== "production" && !CHANNEL_NAME_PATTERN.test(name)) {
    throw new Error(
      `IPC 通道命名不符合约定 mentora:<domain>:<action>：${name}`,
    );
  }
  return name as `${typeof CHANNEL_PREFIX}:${Domain}:${Action}`;
}

type LeafChannelNames<T> = T extends IpcChannelName
  ? T
  : T extends Record<string, infer V>
    ? LeafChannelNames<V>
    : never;

export const Channels = {
  app: {
    info: ipcChannel("app", "info"),
  },
  auth: {
    status: ipcChannel("auth", "status"),
    login: ipcChannel("auth", "login"),
    register: ipcChannel("auth", "register"),
    logout: ipcChannel("auth", "logout"),
    changed: ipcChannel("auth", "changed"),
  },
  api: {
    request: ipcChannel("api", "request"),
  },
  events: {
    open: ipcChannel("events", "open"),
    abort: ipcChannel("events", "abort"),
    message: ipcChannel("events", "message"),
  },
  files: {
    pick: ipcChannel("files", "pick"),
  },
  uploads: {
    start: ipcChannel("uploads", "start"),
    cancel: ipcChannel("uploads", "cancel"),
    progress: ipcChannel("uploads", "progress"),
  },
  shell: {
    openExternal: ipcChannel("shell", "open-external"),
    showItemInFolder: ipcChannel("shell", "show-item-in-folder"),
  },
  notifications: {
    show: ipcChannel("notifications", "show"),
    activated: ipcChannel("notifications", "activated"),
  },
  updater: {
    check: ipcChannel("updater", "check"),
    quitAndInstall: ipcChannel("updater", "quit-and-install"),
    status: ipcChannel("updater", "status"),
  },
  window: {
    minimize: ipcChannel("window", "minimize"),
    toggleMaximize: ipcChannel("window", "toggle-maximize"),
    close: ipcChannel("window", "close"),
    deepLink: ipcChannel("window", "deep-link"),
  },
} as const;

export type ChannelMap = typeof Channels;

export type RegisteredChannel = LeafChannelNames<ChannelMap>;

function collectAllChannels(map: ChannelMap): RegisteredChannel[] {
  const channels: string[] = [];
  for (const group of Object.values(map)) {
    for (const channel of Object.values(group)) {
      channels.push(channel);
    }
  }
  return channels as RegisteredChannel[];
}

export const ALL_IPC_CHANNELS: readonly RegisteredChannel[] =
  collectAllChannels(Channels);

if (process.env.NODE_ENV !== "production") {
  const seen = new Set<string>();
  for (const channel of ALL_IPC_CHANNELS) {
    if (seen.has(channel)) {
      throw new Error(`IPC 通道注册冲突：${channel}`);
    }
    seen.add(channel);
  }
}
