export interface FileNode {
  id: string;
  name: string;
  type: "file" | "folder";
  children?: FileNode[];
  extension?: string;
}

export const courseFiles: FileNode[] = [
  {
    id: "f1",
    name: "基础梳理",
    type: "folder",
    children: [
      { id: "f1-1", name: "计算机系统概述", type: "file", extension: ".md" },
      { id: "f1-2", name: "数据的表示与运算", type: "file", extension: ".md" },
      { id: "f1-3", name: "浮点数运算", type: "file", extension: ".md" },
      { id: "f1-4", name: "阶段自测", type: "file", extension: ".quiz" },
    ],
  },
  {
    id: "f2",
    name: "重点突破",
    type: "folder",
    children: [
      {
        id: "f2-1",
        name: "Cache 基本概念与局部性原理",
        type: "file",
        extension: ".md",
      },
      { id: "f2-2", name: "Cache 映射方式与命中率", type: "file", extension: ".md" },
      { id: "f2-3", name: "Cache 替换策略", type: "file", extension: ".md" },
      { id: "f2-4", name: "写策略与多级 Cache", type: "file", extension: ".md" },
      { id: "f2-5", name: "实验：Cache 性能对比", type: "file", extension: ".lab" },
      { id: "f2-6", name: "阶段检查：重点突破小测", type: "file", extension: ".check" },
    ],
  },
  {
    id: "f3",
    name: "综合应用",
    type: "folder",
    children: [
      { id: "f3-1", name: "指令流水线", type: "file", extension: ".md" },
      { id: "f3-2", name: "总线与I/O", type: "file", extension: ".md" },
      { id: "f3-3", name: "中断与DMA", type: "file", extension: ".md" },
    ],
  },
  {
    id: "f4",
    name: "检验巩固",
    type: "folder",
    children: [
      { id: "f4-1", name: "综合模拟试题（一）", type: "file", extension: ".quiz" },
      { id: "f4-2", name: "综合模拟试题（二）", type: "file", extension: ".quiz" },
    ],
  },
  { id: "f5", name: "学习计划.md", type: "file", extension: ".md" },
  { id: "f6", name: "知识地图.html", type: "file", extension: ".html" },
];
