/**
 * 文件上传服务：3 步流程（create → PUT presigned → complete）。
 *
 * 后端 API：/api/uploads/ → /api/uploads/complete/
 */

const API = "/api";

export interface UploadCreateResult {
  uploadId: string;
  uploadUrl: string;
  objectKey: string;
}

export interface UploadCompleteResult {
  sourceId: string;
  sourceVersionId: string;
  processingStatus: string;
  displayTitle: string;
}

function getMediaType(filename: string): string {
  const ext = filename.split(".").pop()?.toLowerCase() ?? "";
  const map: Record<string, string> = {
    pdf: "application/pdf",
    docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    pptx: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    png: "image/png",
    jpg: "image/jpeg",
    jpeg: "image/jpeg",
    mp4: "video/mp4",
    mp3: "audio/mpeg",
  };
  return map[ext] ?? "application/octet-stream";
}

async function computeSHA256(file: File): Promise<string> {
  const buffer = await file.arrayBuffer();
  const hashBuffer = await crypto.subtle.digest("SHA-256", buffer);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map((b) => b.toString(16).padStart(2, "0")).join("");
}

export interface UploadProgress {
  step: "create" | "upload" | "complete" | "done" | "error";
  message: string;
}

export async function uploadFile(
  file: File,
  onProgress?: (p: UploadProgress) => void,
): Promise<UploadCompleteResult> {
  // Step 1: 创建上传会话
  onProgress?.({ step: "create", message: "正在创建上传会话…" });
  const createRes = await fetch(`${API}/uploads/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      filename: file.name,
      size: file.size,
      mediaType: getMediaType(file.name),
    }),
  });
  if (!createRes.ok) {
    const err = await createRes.json().catch(() => ({}));
    throw new Error(err.error ?? `创建上传会话失败 (${createRes.status})`);
  }
  const { uploadId, uploadUrl } = (await createRes.json()) as UploadCreateResult;

  // Step 2: 上传到预签名 URL
  onProgress?.({ step: "upload", message: "正在上传文件…" });
  const putRes = await fetch(uploadUrl, {
    method: "PUT",
    body: file,
    headers: { "Content-Type": file.type || "application/octet-stream" },
  });
  if (!putRes.ok) {
    throw new Error(`文件上传失败 (${putRes.status})`);
  }

  // Step 3: 完成上传 → 触发解析
  onProgress?.({ step: "complete", message: "正在完成上传并触发解析…" });
  const sha256 = await computeSHA256(file);
  const completeRes = await fetch(`${API}/uploads/complete/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      uploadId,
      sha256,
      size: file.size,
      sync: true,
    }),
  });
  if (!completeRes.ok) {
    const err = await completeRes.json().catch(() => ({}));
    throw new Error(err.error ?? `完成上传失败 (${completeRes.status})`);
  }
  const result = (await completeRes.json()) as UploadCompleteResult;

  onProgress?.({ step: "done", message: "上传完成" });
  return result;
}
