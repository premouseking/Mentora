import { z } from "zod";

/**
 * Authoritative request schemas validated in the main process before any IPC
 * handler acts. The preload layer performs a lightweight shape check first, but
 * main never trusts renderer input (desktop-client-architecture §3.2, §4).
 */

// API bridge: only relative paths are accepted. Reject anything that looks like
// an absolute URL or a protocol-relative URL so the bridge can never become an
// open proxy (desktop-client-architecture §5.1).
const relativeApiPath = z
  .string()
  .min(1)
  .max(2048)
  .refine((p) => p.startsWith("/"), "API path must be relative and start with '/'")
  .refine((p) => !p.startsWith("//"), "Protocol-relative paths are not allowed")
  .refine((p) => !/^[a-z][a-z0-9+.-]*:/i.test(p), "Absolute URLs are not allowed");

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

// External links must be explicit http(s); never allow file:, javascript:, etc.
export const ExternalUrlSchema = z
  .string()
  .url()
  .refine((u) => /^https?:\/\//i.test(u), "Only http(s) external URLs are allowed");

export const NotificationRequestSchema = z.object({
  title: z.string().min(1).max(256),
  body: z.string().min(1).max(2048),
  route: z.string().max(512).optional(),
});

export type ApiRequestInput = z.infer<typeof ApiRequestSchema>;
export type EventStreamOptionsInput = z.infer<typeof EventStreamOptionsSchema>;
export type UploadStartRequestInput = z.infer<typeof UploadStartRequestSchema>;
export type NotificationRequestInput = z.infer<typeof NotificationRequestSchema>;
