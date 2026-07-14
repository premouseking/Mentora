import { useEffect, useRef, useState } from "react";
import { ChevronUp, X } from "lucide-react";
import { useCourseCreation } from "./CourseCreationContext";
import { ProfileQaList, courseInfoToQaItems } from "./ProfileQaDisplay";

interface CourseInfoBarProps {
  mode: "collapsed" | "expanded";
  onToggle: () => void;
}

/**
 * 创建课程常驻底栏 — 展示学习档案（Q&A 卡片）
 *
 * 约束：
 * - collapsed：底部约 1/5 视口高度，横向不占满，显示信息列表
 * - expanded：底部约 2/3 视口高度，贴底，鼠标进入可滚动，无可见滚动条
 * - 顶部中间有拉起/关闭按钮，点击外部区域可收起
 */
export function CourseInfoBar({ mode, onToggle }: CourseInfoBarProps) {
  const { items } = useCourseCreation();
  const barRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const isExpanded = mode === "expanded";
  const qaItems = courseInfoToQaItems(items);

  // 点击外部区域收起
  useEffect(() => {
    if (!isExpanded) return;
    function handleClick(e: MouseEvent) {
      if (barRef.current && !barRef.current.contains(e.target as Node)) {
        onToggle();
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [isExpanded, onToggle]);

  if (items.length === 0) return null;

  return (
    <div
      ref={barRef}
      className={`course-info-bar${isExpanded ? " expanded" : ""}`}
      aria-expanded={isExpanded}
      aria-label="学习档案"
      role="complementary"
    >
      <button
        className="info-bar-toggle"
        onClick={onToggle}
        type="button"
        aria-label={isExpanded ? "收起信息栏" : "展开信息栏"}
      >
        {isExpanded ? <X size={14} /> : <ChevronUp size={16} />}
      </button>

      <div ref={contentRef} className="info-bar-scroll">
        {isExpanded && <h3 className="info-bar-heading">学习档案</h3>}
        <ProfileQaList compact items={qaItems} />
      </div>
    </div>
  );
}

/**
 * 确认方案页的全屏滑出面板
 *
 * 约束：
 * - 不贴底，居中显示，高度不超过 2/3 视口
 * - 从底部滑入动画
 * - 底部包含确认按钮
 */
export function CourseInfoPanel({ onConfirm }: { onConfirm: () => void }) {
  const { items } = useCourseCreation();
  const [visible, setVisible] = useState(false);
  const qaItems = courseInfoToQaItems(items);

  useEffect(() => {
    const timer = setTimeout(() => setVisible(true), 50);
    return () => clearTimeout(timer);
  }, []);

  return (
    <div className={`course-info-panel-overlay${visible ? " visible" : ""}`}>
      <div className="course-info-panel">
        <h2>确认课程信息</h2>
        <div className="info-panel-content">
          <ProfileQaList items={qaItems} />
        </div>
        <div className="info-panel-footer">
          <button className="button primary" onClick={onConfirm} type="button">
            确认并开始学习
          </button>
        </div>
      </div>
    </div>
  );
}
