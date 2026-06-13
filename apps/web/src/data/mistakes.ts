export interface MistakeItem {
  id: string;
  title: string;
  topic: string;
  difficulty: "简单" | "中等" | "困难";
  wrongCount: number;
  lastWrong: string;
}

export const mistakeItems: MistakeItem[] = [
  {
    id: "m-1",
    title: "Cache 映射方式计算题",
    topic: "Cache 映射方式与命中率",
    difficulty: "中等",
    wrongCount: 3,
    lastWrong: "2026-06-10",
  },
  {
    id: "m-2",
    title: "流水线冒险检测与处理",
    topic: "指令流水线",
    difficulty: "困难",
    wrongCount: 5,
    lastWrong: "2026-06-12",
  },
  {
    id: "m-3",
    title: "浮点数加减运算规格化",
    topic: "浮点数运算",
    difficulty: "中等",
    wrongCount: 2,
    lastWrong: "2026-06-08",
  },
  {
    id: "m-4",
    title: "DMA 与中断 I/O 对比选择",
    topic: "总线与I/O",
    difficulty: "简单",
    wrongCount: 1,
    lastWrong: "2026-05-30",
  },
  {
    id: "m-5",
    title: "虚拟地址到物理地址转换",
    topic: "虚拟存储器",
    difficulty: "困难",
    wrongCount: 4,
    lastWrong: "2026-06-11",
  },
  {
    id: "m-6",
    title: "总线仲裁方式判断",
    topic: "总线与I/O",
    difficulty: "中等",
    wrongCount: 2,
    lastWrong: "2026-06-05",
  },
];
