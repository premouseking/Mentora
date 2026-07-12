export interface AiExplanation {
  id: string;
  title: string;
  topic: string;
  type: "解题思路" | "知识点讲解" | "错题分析" | "公式推导";
}

export const aiExplanations: AiExplanation[] = [
  {
    id: "ai-1",
    title: "Cache 映射方式解题思路",
    topic: "Cache 映射方式与命中率",
    type: "解题思路",
  },
  {
    id: "ai-2",
    title: "进位链与流水线结构精讲",
    topic: "指令流水线",
    type: "知识点讲解",
  },
  {
    id: "ai-3",
    title: "浮点数运算常见错误分析",
    topic: "浮点数运算",
    type: "错题分析",
  },
  {
    id: "ai-4",
    title: "Cache 命中率公式推导",
    topic: "Cache 映射方式与命中率",
    type: "公式推导",
  },
  {
    id: "ai-5",
    title: "总线仲裁与 DMA 对比讲解",
    topic: "总线与I/O",
    type: "知识点讲解",
  },
  {
    id: "ai-6",
    title: "中断响应流程易错点",
    topic: "中断与DMA",
    type: "错题分析",
  },
  {
    id: "ai-7",
    title: "虚拟存储器地址转换详解",
    topic: "Cache 映射方式与命中率",
    type: "知识点讲解",
  },
];
