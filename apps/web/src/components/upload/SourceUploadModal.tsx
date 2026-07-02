import { FileWarning, Folders, Globe, Loader, Upload, X } from "lucide-react";
import { type DragEvent, useRef, useState } from "react";

import { useSourceUpload } from "./useSourceUpload";

const ACCEPTED_TYPES = ".pdf,.docx,.pptx,.xlsx,.png,.jpg,.jpeg,.mp4,.mp3";

export interface SourceUploadModalProps {
  onClose: () => void;
  /** 上传成功回调，返回 complete 结果供页面追加 sourceVersionId 等 */
  onUploaded: (result: { sourceVersionId: string; sourceId: string; displayTitle: string }) => void;
  /** 是否显示建课/资源库共用说明文案 */
  showLibraryNote?: boolean;
}

export function SourceUploadModal({
  onClose,
  onUploaded,
  showLibraryNote = true,
}: SourceUploadModalProps) {
  const { upload, progress, reset } = useSourceUpload();
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function handleFile(file: File) {
    try {
      const result = await upload(file);
      setTimeout(() => {
        onUploaded({
          sourceVersionId: result.sourceVersionId,
          sourceId: result.sourceId,
          displayTitle: result.displayTitle,
        });
        onClose();
      }, 800);
    } catch {
      // progress 已由 hook 设置为 error
    }
  }

  function pickFile() {
    fileInputRef.current?.click();
  }

  function onFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
    e.target.value = "";
  }

  function onDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }

  if (progress) {
    const isError = progress.step === "error";
    return (
      <div className="library-modal-overlay" onClick={isError ? onClose : undefined}>
        <div className="library-modal" onClick={(e) => e.stopPropagation()}>
          <header className="library-modal-header">
            <strong>{isError ? "上传失败" : "正在上传"}</strong>
            <button aria-label="关闭" onClick={onClose} type="button"><X size={17} /></button>
          </header>
          <div className="library-upload-zone" style={{ textAlign: "center", padding: "40px 24px" }}>
            {isError ? (
              <>
                <FileWarning size={32} color="#e74c3c" />
                <p style={{ color: "#e74c3c", marginTop: 12 }}>{progress.message}</p>
                <button className="button secondary" onClick={reset} style={{ marginTop: 12 }} type="button">
                  重新上传
                </button>
              </>
            ) : (
              <>
                <Loader size={32} className="spin" />
                <p style={{ marginTop: 12 }}>{progress.message}</p>
              </>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="library-modal-overlay" onClick={onClose}>
      <div className="library-modal" onClick={(e) => e.stopPropagation()}>
        <header className="library-modal-header">
          <strong>添加资料</strong>
          <button aria-label="关闭" onClick={onClose} type="button"><X size={17} /></button>
        </header>
        <input
          ref={fileInputRef}
          accept={ACCEPTED_TYPES}
          style={{ display: "none" }}
          type="file"
          onChange={onFileChange}
        />
        <div
          className={`library-upload-zone${dragOver ? " drag-over" : ""}`}
          onDragEnter={() => setDragOver(true)}
          onDragLeave={() => setDragOver(false)}
          onDragOver={(e) => e.preventDefault()}
          onDrop={onDrop}
        >
          <Upload size={28} />
          <strong>拖拽文件到此处上传</strong>
          <span>支持 PDF、Word、PPT、图片、视频、音频</span>
        </div>
        <div className="library-modal-separator"><span>或者</span></div>
        <div className="library-add-options">
          <button className="button secondary" onClick={pickFile} type="button">
            <Folders size={16} />
            从本地选择文件
          </button>
          <button className="button secondary" disabled type="button">
            <Globe size={16} />
            添加网页链接
          </button>
        </div>
        {showLibraryNote ? (
          <p className="library-upload-note">上传资料仅进入资源库，不会自动授权任何课程访问。</p>
        ) : null}
      </div>
    </div>
  );
}
