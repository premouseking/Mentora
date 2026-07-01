import { useCallback, useEffect, useState } from "react";
import { BrainCircuit, Pencil, Save, Trash2, X } from "lucide-react";

import { AiKeywordPill } from "./AiKeywordPill";
import { AiMarkdownContent } from "./AiMarkdownContent";
import {
  deleteExplanation,
  fetchExplanationDetail,
  updateExplanation,
  type ExplanationDetail,
} from "../services/learningApi";

interface AiExplanationViewProps {
  docId: string;
  courseId: string;
  onDeleted?: () => void;
  onUpdated?: () => void;
}

export function AiExplanationView({
  docId,
  courseId,
  onDeleted,
  onUpdated,
}: AiExplanationViewProps) {
  const [doc, setDoc] = useState<ExplanationDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const [title, setTitle] = useState("");
  const [detail, setDetail] = useState("");
  const [keywords, setKeywords] = useState<string[]>([]);
  const [newKeyword, setNewKeyword] = useState("");

  const load = useCallback(() => {
    setLoading(true);
    setError("");
    fetchExplanationDetail(docId, courseId)
      .then((data) => {
        setDoc(data);
        setTitle(data.title);
        setDetail(data.detail);
        setKeywords(data.keywords ?? []);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "加载失败"))
      .finally(() => setLoading(false));
  }, [docId, courseId]);

  useEffect(() => {
    load();
  }, [load]);

  function removeKeyword(word: string) {
    setKeywords((prev) => prev.filter((k) => k !== word));
  }

  function addKeyword() {
    const word = newKeyword.trim().toLowerCase();
    if (!word || keywords.includes(word)) {
      setNewKeyword("");
      return;
    }
    setKeywords((prev) => [...prev, word]);
    setNewKeyword("");
  }

  async function handleSave() {
    setSaving(true);
    setError("");
    try {
      const updated = await updateExplanation(docId, courseId, {
        title: title.trim(),
        detail,
        keywords,
      });
      setDoc(updated);
      setEditing(false);
      onUpdated?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    setSaving(true);
    setError("");
    try {
      await deleteExplanation(docId, courseId);
      onDeleted?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "删除失败");
      setSaving(false);
    }
  }

  if (loading) {
    return <p className="cw-preview-text">加载讲解内容…</p>;
  }

  if (error && !doc) {
    return <p className="cw-preview-text">{error}</p>;
  }

  if (!doc) {
    return <p className="cw-preview-text">讲解文件不存在。</p>;
  }

  return (
    <div className="ai-explanation-view">
      <div className="ai-explanation-head">
        <div className="ai-explanation-head-icon">
          <BrainCircuit size={18} />
        </div>
        <div className="ai-explanation-head-main">
          {editing ? (
            <input
              className="ai-explanation-title-input"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              aria-label="讲解标题"
            />
          ) : (
            <h2>{doc.title}</h2>
          )}
          <p className="ai-explanation-type">{doc.doc_type}</p>
        </div>
        <div className="ai-explanation-actions">
          {editing ? (
            <>
              <button type="button" className="ai-explanation-btn" onClick={() => setEditing(false)} disabled={saving}>
                <X size={14} />
                取消
              </button>
              <button type="button" className="ai-explanation-btn primary" onClick={handleSave} disabled={saving}>
                <Save size={14} />
                {saving ? "保存中…" : "保存"}
              </button>
            </>
          ) : (
            <>
              <button type="button" className="ai-explanation-btn" onClick={() => setEditing(true)}>
                <Pencil size={14} />
                编辑
              </button>
              <button type="button" className="ai-explanation-btn danger" onClick={() => setConfirmDelete(true)}>
                <Trash2 size={14} />
                删除
              </button>
            </>
          )}
        </div>
      </div>

      <div className="ai-mentioned-context-list ai-explanation-keywords">
        {keywords.map((word) => (
          <AiKeywordPill
            key={word}
            label={word}
            onRemove={editing ? () => removeKeyword(word) : undefined}
          />
        ))}
        {editing && (
          <div className="ai-mentioned-context-pill ai-keyword-pill-add">
            <input
              value={newKeyword}
              onChange={(e) => setNewKeyword(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  addKeyword();
                }
              }}
              placeholder="添加标签"
              aria-label="添加关键词"
            />
          </div>
        )}
      </div>

      {error && <p className="ai-explanation-error">{error}</p>}

      <div className="ai-explanation-body">
        {editing ? (
          <textarea
            className="ai-explanation-editor"
            value={detail}
            onChange={(e) => setDetail(e.target.value)}
            aria-label="讲解正文"
          />
        ) : (
          <AiMarkdownContent content={doc.detail || "（暂无正文）"} />
        )}
      </div>

      {confirmDelete && (
        <div className="ai-explanation-confirm-overlay">
          <div className="ai-explanation-confirm-dialog">
            <p>确定删除此 AI 讲解文件？此操作不可撤销。</p>
            <div className="ai-explanation-confirm-actions">
              <button type="button" onClick={() => setConfirmDelete(false)} disabled={saving}>
                取消
              </button>
              <button type="button" className="danger" onClick={handleDelete} disabled={saving}>
                确认删除
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
