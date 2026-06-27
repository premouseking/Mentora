import type { FileNode } from "./files";
import type { QuizItem, QuizSession } from "../services/assessmentApi";

export const USE_MOCK_QUIZ = true;

const MOCK_QUESTIONS: Omit<QuizItem, "attempt_id" | "item_id" | "position" | "source_links" | "user_answer" | "is_correct">[] = [
  {
    question_type: "single_choice",
    question_text: "在 2 路组相联 Cache 中，若 Cache 共有 16 块，则 Cache 组数是多少？",
    options: [
      { label: "A", text: "2 组" },
      { label: "B", text: "4 组" },
      { label: "C", text: "8 组" },
      { label: "D", text: "16 组" },
    ],
    correct_answer: "C",
    explanation: "组相联 Cache 的组数 = Cache 总块数 / 每组块数。16 块采用 2 路组相联，因此组数为 16 / 2 = 8。",
    difficulty: 2,
  },
  {
    question_type: "single_choice",
    question_text: "主存地址按字节编址，主存块大小为 32 字节。地址 129 所在的主存块号是多少？",
    options: [
      { label: "A", text: "3" },
      { label: "B", text: "4" },
      { label: "C", text: "5" },
      { label: "D", text: "32" },
    ],
    correct_answer: "B",
    explanation: "主存块号 = floor(主存地址 / 块大小)。floor(129 / 32) = 4，因此地址 129 位于主存块 4。",
    difficulty: 3,
  },
  {
    question_type: "single_choice",
    question_text: "直接映射 Cache 中，主存块映射到 Cache 行通常由哪一部分决定？",
    options: [
      { label: "A", text: "主存块号对 Cache 行数取模" },
      { label: "B", text: "主存块大小对 Cache 容量取模" },
      { label: "C", text: "标记位对块内地址取模" },
      { label: "D", text: "CPU 字长对 Cache 行数取模" },
    ],
    correct_answer: "A",
    explanation: "直接映射中每个主存块只能映射到一个固定 Cache 行，常用规则是 Cache 行号 = 主存块号 mod Cache 行数。",
    difficulty: 3,
  },
  {
    question_type: "single_choice",
    question_text: "Cache 命中率提高时，在其他条件不变的情况下，平均访存时间通常会如何变化？",
    options: [
      { label: "A", text: "增加" },
      { label: "B", text: "减少" },
      { label: "C", text: "不变" },
      { label: "D", text: "与命中率无关" },
    ],
    correct_answer: "B",
    explanation: "平均访存时间通常由命中时间、缺失率和缺失代价共同决定。命中率提高意味着缺失率下降，因此平均访存时间通常减少。",
    difficulty: 2,
  },
  {
    question_type: "single_choice",
    question_text: "流水线发生数据冒险时，常见的处理方法不包括哪一项？",
    options: [
      { label: "A", text: "数据前递" },
      { label: "B", text: "插入暂停周期" },
      { label: "C", text: "编译器重排指令" },
      { label: "D", text: "扩大主存容量" },
    ],
    correct_answer: "D",
    explanation: "数据冒险通常通过数据前递、暂停或指令重排缓解；扩大主存容量不能直接解决流水线数据相关问题。",
    difficulty: 3,
  },
  {
    question_type: "single_choice",
    question_text: "DMA 方式相较于程序查询方式，最主要的优势是什么？",
    options: [
      { label: "A", text: "完全不需要总线" },
      { label: "B", text: "减少 CPU 参与数据传输的开销" },
      { label: "C", text: "一定能提高 Cache 命中率" },
      { label: "D", text: "可以取消主存" },
    ],
    correct_answer: "B",
    explanation: "DMA 允许外设和主存之间进行批量数据传输，CPU 只需参与初始化和结束处理，从而减少 CPU 开销。",
    difficulty: 2,
  },
  {
    question_type: "single_choice",
    question_text: "在虚拟存储器中，页表的主要作用是什么？",
    options: [
      { label: "A", text: "记录虚拟页到物理页框的映射" },
      { label: "B", text: "保存所有 CPU 指令的机器码" },
      { label: "C", text: "替代 Cache 存储数据" },
      { label: "D", text: "决定硬盘转速" },
    ],
    correct_answer: "A",
    explanation: "页表记录虚拟地址空间中的页与物理内存页框之间的对应关系，是地址转换的核心结构。",
    difficulty: 3,
  },
  {
    question_type: "single_choice",
    question_text: "总线仲裁的主要目的是什么？",
    options: [
      { label: "A", text: "决定多个主设备谁获得总线使用权" },
      { label: "B", text: "把十进制数转换成二进制数" },
      { label: "C", text: "计算 Cache 组号" },
      { label: "D", text: "提升显示器刷新率" },
    ],
    correct_answer: "A",
    explanation: "当多个主设备同时请求使用总线时，需要总线仲裁机制决定哪个设备获得总线控制权。",
    difficulty: 2,
  },
];

function findSourceName(files: FileNode[], id: string): string {
  for (const file of files) {
    if (file.id === id) return file.name;
    if (file.children) {
      const child = findSourceName(file.children, id);
      if (child) return child;
    }
  }
  return "当前课程文件";
}

export function createMockQuizSession(input: {
  sourceVersionIds: string[];
  files: FileNode[];
  count: number;
}): QuizSession {
  const sourceVersionId = input.sourceVersionIds[0] ?? "mock-source";
  const sourceTitle = findSourceName(input.files, sourceVersionId);
  const selectedQuestions = MOCK_QUESTIONS.slice(0, Math.max(1, Math.min(input.count, MOCK_QUESTIONS.length)));

  return {
    session_id: `mock-session-${Date.now()}`,
    course_session_id: "mock-course-session",
    status: "created",
    total_items: selectedQuestions.length,
    correct_count: 0,
    score_pct: 0,
    items: selectedQuestions.map((question, index) => ({
      ...question,
      attempt_id: `mock-attempt-${index + 1}`,
      item_id: `mock-item-${index + 1}`,
      position: index,
      source_links: [
        {
          evidence_id: `mock-evidence-${index + 1}`,
          source_version_id: sourceVersionId,
          title: sourceTitle,
          page_number: Math.max(1, Math.floor(index / 2) + 1),
          snippet: "这是用于预览刷题模式的本地 mock 来源片段，后续接入真实解析证据后会显示课程原文。",
        },
      ],
      user_answer: "",
      is_correct: false,
    })),
  };
}

export function completeMockQuizSession(
  session: QuizSession,
  answers: Record<string, string>,
): QuizSession {
  const items = session.items.map((item) => {
    const userAnswer = answers[item.item_id] || item.user_answer;
    return {
      ...item,
      user_answer: userAnswer,
      is_correct: userAnswer === item.correct_answer,
    };
  });
  const correctCount = items.filter((item) => item.is_correct).length;
  return {
    ...session,
    status: "completed",
    items,
    correct_count: correctCount,
    score_pct: Math.round((correctCount / Math.max(items.length, 1)) * 100),
  };
}
