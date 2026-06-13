export interface QuizQuestion {
  topic: string;
  question: string;
  options: string[];
  answer: number;
}

export const sampleQuestion: QuizQuestion = {
  topic: "Cache 映射方式",
  question:
    "某计算机的 Cache 共有 16 块，采用 2 路组相联映射方式。每个主存块大小为 32 字节，按字节编址。主存 129 号单元所在的主存块应装入的 Cache 组号是？",
  options: ["A. 0", "B. 1", "C. 2", "D. 4"],
  answer: 2,
};
