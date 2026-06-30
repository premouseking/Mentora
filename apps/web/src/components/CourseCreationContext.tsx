import { createContext, useCallback, useContext, useState, type ReactNode } from "react";

/**
 * 课程创建过程中共享的学习档案项
 */
export interface CourseInfoItem {
  /** 唯一标识，用于去重与更新 */
  key: string;
  /** 左侧标题 */
  title: string;
  /** 右侧内容 */
  value: string;
  /** 来源标注，如 "你的输入" / "你的回答" / "资料识别" / "AI 建议" */
  source?: string;
}

interface CourseCreationContextValue {
  items: CourseInfoItem[];
  addItem: (item: CourseInfoItem) => void;
  removeItem: (key: string) => void;
  updateItem: (key: string, value: string) => void;
  /** 后端会话 ID，步骤 1 提交后赋值 */
  sessionId: string | null;
  setSessionId: (id: string) => void;
}

const CourseCreationContext = createContext<CourseCreationContextValue | null>(null);

export function CourseCreationProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<CourseInfoItem[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);

  const addItem = useCallback((item: CourseInfoItem) => {
    setItems((prev) => {
      const existing = prev.findIndex((i) => i.key === item.key);
      if (existing >= 0) {
        const next = [...prev];
        next[existing] = item;
        return next;
      }
      return [...prev, item];
    });
  }, []);

  const removeItem = useCallback((key: string) => {
    setItems((prev) => prev.filter((i) => i.key !== key));
  }, []);

  const updateItem = useCallback((key: string, value: string) => {
    setItems((prev) => prev.map((i) => (i.key === key ? { ...i, value } : i)));
  }, []);

  return (
    <CourseCreationContext.Provider value={{ items, addItem, removeItem, updateItem, sessionId, setSessionId }}>
      {children}
    </CourseCreationContext.Provider>
  );
}

export function useCourseCreation() {
  const ctx = useContext(CourseCreationContext);
  if (!ctx) {
    throw new Error("useCourseCreation 必须在 CourseCreationProvider 内部使用");
  }
  return ctx;
}
