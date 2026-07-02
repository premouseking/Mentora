/**
 * 本地开发 ownerId，与后端 DEV_OWNER_ID 对齐。
 *
 * 约束：非 DEBUG 环境下资料库/上传 API 必须携带 ownerId。
 */
export const DEV_OWNER_ID =
  (import.meta.env.VITE_DEV_OWNER_ID as string | undefined)?.trim() || "dev-user";
