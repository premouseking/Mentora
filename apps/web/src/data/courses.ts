export const courses = [
  {
    id: "computer-architecture",
    name: "计算机组成原理",
    updatedAt: "今天继续",
    phase: "阶段 2 · 重点突破",
    phaseDetail: "存储系统与 Cache",
    nextTask: "Cache 映射方式与命中率",
    estimate: "约 18 分钟",
    status: "学习中",
    progress: 42,
    color: "teal",
    icon: "组",
  },
  {
    id: "machine-learning",
    name: "机器学习基础",
    updatedAt: "3 天前学习",
    phase: "阶段 1 · 基础梳理",
    phaseDetail: "核心概念与数学基础",
    nextTask: "线性回归为什么有效",
    estimate: "约 22 分钟",
    status: "学习中",
    progress: 18,
    color: "blue",
    icon: "机",
  },
  {
    id: "data-structures",
    name: "数据结构与算法",
    updatedAt: "上周更新",
    phase: "等待方案确认",
    phaseDetail: "AI 已生成 4 个学习阶段",
    nextTask: "检查阶段安排",
    estimate: "确认后开始",
    status: "待确认",
    progress: 0,
    color: "violet",
    icon: "数",
  },
] as const;

export const coursePhases = [
  { id: "foundation", name: "基础梳理", share: 25, state: "completed" },
  { id: "focus", name: "重点突破", share: 35, state: "active" },
  { id: "application", name: "综合应用", share: 25, state: "upcoming" },
  { id: "review", name: "检验巩固", share: 15, state: "upcoming" },
] as const;

export const focusTasks = [
  {
    id: "cache-locality",
    index: "2.1",
    name: "Cache 基本概念与局部性原理",
    type: "知识点",
    state: "completed",
    estimate: "",
  },
  {
    id: "cache-mapping",
    index: "2.2",
    name: "Cache 映射方式与命中率",
    type: "知识点",
    state: "current",
    estimate: "约 18 分钟",
  },
  {
    id: "cache-replacement",
    index: "2.3",
    name: "Cache 替换策略",
    type: "知识点",
    state: "available",
    estimate: "约 16 分钟",
  },
  {
    id: "multi-level-cache",
    index: "2.4",
    name: "写策略与多级 Cache",
    type: "知识点",
    state: "available",
    estimate: "约 14 分钟",
  },
  {
    id: "cache-lab",
    index: "2.5",
    name: "实验：Cache 性能对比",
    type: "实践",
    state: "optional",
    estimate: "约 20 分钟",
  },
  {
    id: "focus-check",
    index: "2.6",
    name: "阶段检查：重点突破小测",
    type: "检查点",
    state: "checkpoint",
    estimate: "约 15 分钟",
  },
] as const;

export type EvidenceState = "mastered" | "reinforce" | "unfinished";

export type StageEvidence = {
  id: string;
  name: string;
  source: string;
  detail: string;
  state: EvidenceState;
};

export const stageEvidence: StageEvidence[] = [
  {
    id: "mapping",
    name: "Cache 映射方式",
    source: "阶段检查 4/4",
    detail: "能区分三种映射方式及其冲突特征",
    state: "mastered",
  },
  {
    id: "locality",
    name: "局部性原理",
    source: "阶段检查 4/4",
    detail: "能解释时间与空间局部性的实际作用",
    state: "mastered",
  },
  {
    id: "replacement",
    name: "Cache 替换策略",
    source: "阶段检查 2/4",
    detail: "需要继续比较 LRU、FIFO 与随机替换",
    state: "reinforce",
  },
  {
    id: "write-policy",
    name: "写策略",
    source: "阶段检查 2/4",
    detail: "写直达与写回的适用场景仍容易混淆",
    state: "reinforce",
  },
  {
    id: "cache-lab",
    name: "实验：Cache 性能对比",
    source: "任务未完成",
    detail: "保留为后续补学，不影响进入下一阶段",
    state: "unfinished",
  },
];

export const nextPhasePreview = {
  id: "application",
  name: "综合应用",
  goal: "将已学知识综合运用，解决综合性问题并独立设计方案。",
  connection: "基于映射方式与命中率的理解，进一步进行参数权衡与性能优化。",
  workload: "参考学习量：约 30%（约 4～5 小时）",
  tasks: [
    "综合应用：Cache 设计与优化分析",
    "练习：多级 Cache 系统设计",
    "项目：小型处理器 Cache 子系统设计",
  ],
} as const;

export const adjustmentImpact = [
  {
    id: "reinforcement",
    scope: "本阶段（重点突破）",
    change: "新增补学：Cache 替换策略",
  },
  {
    id: "guided",
    scope: "下一阶段（综合应用）",
    change: "首个综合题调整为引导式练习",
  },
  {
    id: "unchanged",
    scope: "其他阶段",
    change: "不受影响，保持原方案不变",
  },
] as const;
