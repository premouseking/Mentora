import { z } from "zod";

/**
 * IPC 请求 payload 权威校验。
 *
 * 约束：
 * - main handler 执行业务前必须 parse；preload 仅做轻量形状检查
 * - API path 仅相对路径；外部 URL 仅 http(s)
 *
 * @see docs/architecture/desktop-client-architecture.md §3.2、§5.1
 */

const relativeApiPath = z
  .string()
  .min(1)
  .max(2048)
  .refine((p) => p.startsWith("/"), "API 路径必须为以 '/' 开头的相对路径")
  .refine((p) => !p.startsWith("//"), "不允许协议相对路径（//...）")
  .refine(
    (p) => !/^[a-z][a-z0-9+.-]*:/i.test(p),
    "不允许绝对 URL",
  );

export const ApiRequestSchema = z.object({
  path: relativeApiPath,
  method: z.enum(["GET", "POST", "PUT", "PATCH", "DELETE"]).default("GET"),
  query: z
    .record(z.union([z.string(), z.number(), z.boolean(), z.undefined()]))
    .optional(),
  body: z.unknown().optional(),
  signalId: z.string().min(1).max(128).optional(),
});

export const EventStreamOptionsSchema = z.object({
  path: relativeApiPath,
  lastEventId: z.string().max(256).optional(),
});

export const StreamIdSchema = z.string().min(1).max(128);

export const FileTokenSchema = z.string().min(1).max(256);

export const UploadStartRequestSchema = z.object({
  fileToken: FileTokenSchema,
  courseId: z.string().min(1).max(128).optional(),
});

export const UploadIdSchema = z.string().min(1).max(128);

export const ExternalUrlSchema = z
  .string()
  .url()
  .refine(
    (u) => /^https?:\/\//i.test(u),
    "外部链接仅允许 http(s) 协议",
  );

export const NotificationRequestSchema = z.object({
  title: z.string().min(1).max(256),
  body: z.string().min(1).max(2048),
  route: z.string().max(512).optional(),
});

export const AuthCredentialsSchema = z.object({
  email: z.string().email().max(256),
  password: z.string().min(8).max(128),
});

export const AuthRegisterSchema = AuthCredentialsSchema.extend({
  displayName: z.string().min(1).max(64).optional(),
});

export type ApiRequestInput = z.infer<typeof ApiRequestSchema>;
export type EventStreamOptionsInput = z.infer<typeof EventStreamOptionsSchema>;
export type UploadStartRequestInput = z.infer<typeof UploadStartRequestSchema>;
export type NotificationRequestInput = z.infer<typeof NotificationRequestSchema>;
export type AuthCredentialsInput = z.infer<typeof AuthCredentialsSchema>;
export type AuthRegisterInput = z.infer<typeof AuthRegisterSchema>;
