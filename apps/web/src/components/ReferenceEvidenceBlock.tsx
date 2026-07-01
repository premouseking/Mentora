import { BookOpen, ExternalLink } from "lucide-react";
import { Link } from "react-router-dom";

import { buildWorkspaceEvidencePath } from "../pages/courseFlowHelpers";
import type { TaskSource } from "../services/learningApi";

export function ReferenceEvidenceBlock({
  courseId,
  sources,
}: {
  courseId: string;
  sources: TaskSource[];
}) {
  if (sources.length === 0) return null;

  return (
    <section className="task-reference-block" aria-label="参考资料">
      <div className="task-reference-head">
        <BookOpen size={16} />
        <span>参考资料</span>
      </div>
      <p className="task-reference-hint">以下证据是本任务的规划依据，点击可在课程工作区查看原文。</p>
      <ul className="task-reference-list">
        {sources.map((source) => (
          <li key={source.evidence_id}>
            <Link
              className="task-reference-item"
              to={buildWorkspaceEvidencePath(courseId, source.source_version_id, source.evidence_id)}
            >
              <div className="task-reference-meta">
                <strong>{source.title || "未命名资料"}</strong>
                {source.page_number > 0 && <span>第 {source.page_number} 页</span>}
              </div>
              {source.snippet_preview && (
                <p className="task-reference-snippet">{source.snippet_preview}</p>
              )}
              <span className="task-reference-link">
                在工作区查看 <ExternalLink size={13} />
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
