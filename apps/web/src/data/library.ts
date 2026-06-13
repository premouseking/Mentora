export type LibraryItemType = "pdf" | "docx" | "pptx" | "image" | "video" | "audio" | "link";
export type ParseState =
  | "pending"
  | "uploading"
  | "reading"
  | "ready"
  | "analyzing"
  | "needs_confirm"
  | "failed";
export type MaterialRole =
  | "primary"
  | "auxiliary"
  | "supplement"
  | "diagnostic"
  | "unknown";

export interface LibraryItem {
  id: string;
  name: string;
  type: LibraryItemType;
  tags: string[];
  parseState: ParseState;
  updatedAt: string;
  usedBy: string[];
  size?: string;
  pages?: number;
  role: MaterialRole;
  version: number;
  sourcePath?: string;
  folderId: string | null;
}

export interface LibraryFolder {
  id: string;
  name: string;
}

export const libraryFolders: LibraryFolder[] = [
  { id: "f-1", name: "计算机组成原理" },
  { id: "f-2", name: "机器学习" },
  { id: "f-3", name: "考研真题" },
  { id: "f-4", name: "实验与数据" },
];

export const libraryItems: LibraryItem[] = [
  {
    id: "lib-1",
    name: "计算机组成原理（第6版）第3章.pdf",
    type: "pdf",
    tags: ["教材", "考试范围"],
    parseState: "ready",
    updatedAt: "今天",
    usedBy: ["计算机组成原理"],
    size: "4.2 MB",
    pages: 42,
    role: "primary",
    version: 1,
    folderId: "f-1",
  },
  {
    id: "lib-2",
    name: "课程PPT：存储系统.pptx",
    type: "pptx",
    tags: ["课件", "重点补充"],
    parseState: "ready",
    updatedAt: "2 天前",
    usedBy: ["计算机组成原理"],
    size: "8.7 MB",
    pages: 36,
    role: "auxiliary",
    version: 1,
    folderId: "f-1",
  },
  {
    id: "lib-3",
    name: "CSAPP 第6章 存储器层次结构.pdf",
    type: "pdf",
    tags: ["参考资料", "课外拓展"],
    parseState: "ready",
    updatedAt: "上周",
    usedBy: ["计算机组成原理", "数据结构与算法"],
    size: "12.1 MB",
    pages: 88,
    role: "supplement",
    version: 2,
    folderId: "f-1",
  },
  {
    id: "lib-4",
    name: "2024考研真题-组成原理.pdf",
    type: "pdf",
    tags: ["练习与题目", "考试范围"],
    parseState: "ready",
    updatedAt: "3 天前",
    usedBy: ["计算机组成原理"],
    size: "2.8 MB",
    pages: 24,
    role: "diagnostic",
    version: 1,
    folderId: "f-3",
  },
  {
    id: "lib-5",
    name: "Cache性能分析实验数据.xlsx",
    type: "docx",
    tags: ["实验", "练习与题目"],
    parseState: "analyzing",
    updatedAt: "今天",
    usedBy: [],
    size: "1.3 MB",
    role: "unknown",
    version: 1,
    folderId: "f-4",
  },
  {
    id: "lib-6",
    name: "机器学习-西瓜书-周志华.pdf",
    type: "pdf",
    tags: ["教材"],
    parseState: "ready",
    updatedAt: "3 天前",
    usedBy: ["机器学习基础"],
    size: "19.5 MB",
    pages: 432,
    role: "primary",
    version: 1,
    folderId: "f-2",
  },
  {
    id: "lib-7",
    name: "线性代数导论笔记整理.docx",
    type: "docx",
    tags: ["参考资料"],
    parseState: "needs_confirm",
    updatedAt: "今天",
    usedBy: [],
    size: "0.8 MB",
    pages: 18,
    role: "unknown",
    version: 1,
    folderId: null,
  },
  {
    id: "lib-8",
    name: "算法导论-第3版-中文.pdf",
    type: "pdf",
    tags: ["教材", "参考资料"],
    parseState: "ready",
    updatedAt: "上周",
    usedBy: ["数据结构与算法"],
    size: "48.2 MB",
    pages: 780,
    role: "primary",
    version: 3,
    folderId: null,
  },
  {
    id: "lib-9",
    name: "LeetCode分类题解.pdf",
    type: "pdf",
    tags: ["练习与题目"],
    parseState: "uploading",
    updatedAt: "刚刚",
    usedBy: [],
    size: "5.6 MB",
    role: "unknown",
    version: 1,
    folderId: null,
  },
  {
    id: "lib-10",
    name: "深度学习入门：基于Python的理论与实现.pdf",
    type: "pdf",
    tags: ["教材"],
    parseState: "pending",
    updatedAt: "1 分钟前",
    usedBy: [],
    size: "15.3 MB",
    role: "unknown",
    version: 1,
    folderId: null,
  },
  {
    id: "lib-11",
    name: "指令流水线优化论文合集",
    type: "link",
    tags: ["参考资料", "课外拓展"],
    parseState: "ready",
    updatedAt: "5 天前",
    usedBy: ["计算机组成原理"],
    role: "supplement",
    version: 1,
    folderId: "f-1",
  },
  {
    id: "lib-12",
    name: "计算机系统结构-量化研究方法-第6版.pdf",
    type: "pdf",
    tags: ["参考资料"],
    parseState: "failed",
    updatedAt: "昨天",
    usedBy: [],
    size: "22.7 MB",
    role: "unknown",
    version: 1,
    folderId: null,
  },
];

export const typeLabels: Record<LibraryItemType, string> = {
  pdf: "PDF",
  docx: "Word",
  pptx: "PPT",
  image: "图片",
  video: "视频",
  audio: "音频",
  link: "链接",
};

export const parseStateLabels: Record<ParseState, string> = {
  pending: "等待处理",
  uploading: "正在上传",
  reading: "正在读取内容",
  ready: "已可使用",
  analyzing: "仍在深度分析",
  needs_confirm: "需要确认",
  failed: "处理失败",
};

export const roleLabels: Record<MaterialRole, string> = {
  primary: "主要教材",
  auxiliary: "重点补充",
  supplement: "参考资料",
  diagnostic: "练习与题目",
  unknown: "暂未分配",
};
