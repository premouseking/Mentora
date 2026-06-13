import { randomUUID } from "node:crypto";
import { createReadStream } from "node:fs";
import { stat } from "node:fs/promises";
import { createHash } from "node:crypto";
import type { WebContents } from "electron";

import type { UploadProgress } from "../shared/desktopApi";
import type { UploadStartRequestInput } from "../shared/schemas";
import { Channels } from "../shared/channels";
import { createLogger } from "./logger";
import type { ApiClient } from "./apiClient";
import type { FileTokenStore } from "./fileTokens";

const log = createLogger("uploads");

interface ActiveUpload {
  controller: AbortController;
  owner: WebContents;
}

/** 约束：大文件不经 IPC 传 base64；main 直传预签名 URL（§6.2） */
export class UploadManager {
  private readonly uploads = new Map<string, ActiveUpload>();

  constructor(
    private readonly api: ApiClient,
    private readonly files: FileTokenStore,
  ) {}

  async start(
    sender: WebContents,
    req: UploadStartRequestInput,
  ): Promise<{ uploadId: string }> {
    const grant = this.files.resolve(req.fileToken, sender);
    if (!grant) throw new Error("Invalid or expired file token");

    const uploadId = randomUUID();
    const controller = new AbortController();
    this.uploads.set(uploadId, { controller, owner: sender });

    void this.run(uploadId, sender, grant.absolutePath, req, controller);
    return { uploadId };
  }

  cancel(uploadId: string): void {
    const upload = this.uploads.get(uploadId);
    if (!upload) return;
    upload.controller.abort();
    this.uploads.delete(uploadId);
  }

  cancelAllFor(owner: WebContents): void {
    for (const [uploadId, upload] of this.uploads) {
      if (upload.owner === owner) {
        upload.controller.abort();
        this.uploads.delete(uploadId);
      }
    }
  }

  private progress(sender: WebContents, p: UploadProgress): void {
    if (!sender.isDestroyed()) sender.send(Channels.uploads.progress, p);
  }

  private async run(
    uploadId: string,
    sender: WebContents,
    absolutePath: string,
    req: UploadStartRequestInput,
    controller: AbortController,
  ): Promise<void> {
    const bytesTotal = (await stat(absolutePath)).size;
    const emit = (
      phase: UploadProgress["phase"],
      bytesSent: number,
      message?: string,
    ) => this.progress(sender, { uploadId, phase, bytesSent, bytesTotal, message });

    try {
      emit("creating", 0);

      const created = await this.api.request<{ uploadUrl: string }>({
        path: "/uploads/",
        method: "POST",
        body: { courseId: req.courseId, size: bytesTotal },
      });
      if (!created.ok) throw new Error(`create upload failed: ${created.status}`);
      const uploadUrl = created.data.uploadUrl;

      emit("uploading", 0);
      const hash = createHash("sha256");
      let bytesSent = 0;
      const stream = createReadStream(absolutePath);
      stream.on("data", (chunk) => {
        hash.update(chunk);
        bytesSent += chunk.length;
        emit("uploading", bytesSent);
      });

      const putResponse = await fetch(uploadUrl, {
        method: "PUT",
        body: stream as unknown as ReadableStream,
        // @ts-expect-error Node fetch 对流式 body 要求 duplex
        duplex: "half",
        signal: controller.signal,
      });
      if (!putResponse.ok) throw new Error(`PUT failed: ${putResponse.status}`);

      emit("completing", bytesSent);
      const sha256 = hash.digest("hex");
      await this.api.request({
        path: "/uploads/complete/",
        method: "POST",
        body: { uploadId, sha256, size: bytesTotal },
      });

      emit("done", bytesSent);
    } catch (err) {
      if (controller.signal.aborted) {
        this.progress(sender, {
          uploadId,
          phase: "cancelled",
          bytesSent: 0,
          bytesTotal,
        });
        return;
      }
      log.warn("Upload failed", { uploadId, message: String(err) });
      this.progress(sender, {
        uploadId,
        phase: "error",
        bytesSent: 0,
        bytesTotal,
        message: String(err),
      });
    } finally {
      this.uploads.delete(uploadId);
    }
  }
}
