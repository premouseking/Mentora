import { useCallback, useState } from "react";

import { uploadFile, type UploadCompleteResult, type UploadProgress } from "../../services/uploadService";

export function useSourceUpload() {
  const [progress, setProgress] = useState<UploadProgress | null>(null);
  const [uploading, setUploading] = useState(false);

  const upload = useCallback(async (file: File): Promise<UploadCompleteResult> => {
    setUploading(true);
    setProgress({ step: "create", message: "正在创建上传会话…" });
    try {
      const result = await uploadFile(file, (next) => setProgress(next));
      setProgress({ step: "done", message: "上传完成，解析中…" });
      return result;
    } catch (error) {
      setProgress({
        step: "error",
        message: error instanceof Error ? error.message : "上传失败",
      });
      throw error;
    } finally {
      setUploading(false);
    }
  }, []);

  const reset = useCallback(() => {
    setProgress(null);
    setUploading(false);
  }, []);

  return { upload, progress, uploading, reset, setProgress };
}
