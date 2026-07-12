import { ApiError, requestRaw } from "./client";

export async function fetchProtectedAssetBlobUrl(
  url: string,
  signal?: AbortSignal,
): Promise<string> {
  const response = await requestRaw("GET", url, { signal });
  if (!response.ok) throw new ApiError(response.status, `资源请求失败 (${response.status})`);
  return URL.createObjectURL(await response.blob());
}
