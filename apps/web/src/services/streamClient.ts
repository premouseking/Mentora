import { ApiError, parseRawJson, requestRaw } from "./client";

/** 统一的 JSON POST 流式请求入口；负责鉴权、刷新、取消和错误转换。 */
export async function postJsonStream(
  url: string,
  body: unknown,
  options?: { signal?: AbortSignal; timeoutMs?: number },
): Promise<ReadableStream<Uint8Array>> {
  const response = await requestRaw("POST", url, {
    body: JSON.stringify(body),
    headers: { "Content-Type": "application/json" },
    signal: options?.signal,
    timeoutMs: options?.timeoutMs,
  });
  if (!response.ok) {
    await parseRawJson<never>(response);
  }
  if (!response.body) throw new ApiError(response.status, "响应流为空");
  return response.body;
}
