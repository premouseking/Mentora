import { offsetDateKey, TODAY_DATE_KEY } from "./history";

export interface MistakeItem {
  id: string;
  title: string;
  topic: string;
  difficulty: "简单" | "中等" | "困难";
  wrongCount: number;
  lastWrong: string;
  question: string;
  options: string[];
  answer: number;
  explanation: string;
  errorReason: string;
  knowledgePoints: string[];
  sourceLinks: MistakeSourceLink[];
}

export interface MistakeSourceLink {
  id: string;
  fileId?: string;
  title: string;
  location: string;
  excerpt: string;
}

export const mistakeItems: MistakeItem[] = [
  {
    id: "m-1",
    title: "Cache 映射方式计算题",
    topic: "Cache 映射方式与命中率",
    difficulty: "中等",
    wrongCount: 3,
    lastWrong: offsetDateKey(TODAY_DATE_KEY, -6),
    question:
      "某计算机的 Cache 共有 16 块，采用 2 路组相联映射方式。每个主存块大小为 32 字节，按字节编址。主存 129 号单元所在的主存块应装入的 Cache 组号是多少？",
    options: ["0", "1", "2", "4"],
    answer: 3,
    explanation:
      "主存块号 = floor(129 / 32) = 4。2 路组相联时，Cache 组数 = 16 / 2 = 8，因此组号 = 主存块号 mod Cache 组数 = 4 mod 8 = 4。",
    errorReason:
      "上次把字节地址 129 直接参与取模，漏掉了先除以块大小得到主存块号这一步。",
    knowledgePoints: ["主存块号计算", "组相联映射", "Cache 组号取模"],
    sourceLinks: [
      {
        id: "m-1-s-1",
        fileId: "f2-2",
        title: "Cache 映射方式与命中率",
        location: "3.4 Cache 映射方式",
        excerpt: "组相联映射中，主存块按块号对 Cache 组数取模，组内任一路可放置。",
      },
      {
        id: "m-1-s-2",
        title: "计算机组成原理课堂笔记",
        location: "Cache 地址映射例题",
        excerpt: "地址到块号的转换必须先按块大小向下取整。",
      },
    ],
  },
  {
    id: "m-2",
    title: "流水线冒险检测与处理",
    topic: "指令流水线",
    difficulty: "困难",
    wrongCount: 5,
    lastWrong: offsetDateKey(TODAY_DATE_KEY, -4),
    question:
      "五级流水线 IF-ID-EX-MEM-WB 中，若后一条指令在 EX 阶段需要使用前一条 load 指令从内存读出的结果，且没有额外转发到 EX 的路径，最直接的处理方式是什么？",
    options: ["继续执行，不需要处理", "插入一个暂停周期", "清空整条流水线", "把后一条指令提前到 MEM 阶段"],
    answer: 1,
    explanation:
      "load 指令的数据通常在 MEM 末尾才可用，后一条指令的 EX 阶段太早使用该值。没有可用转发路径时，需要插入暂停周期，让数据在写回或可转发后再被消费。",
    errorReason:
      "上次把所有数据冒险都当作转发可解决，没有区分 load-use 冒险的数据可用时刻。",
    knowledgePoints: ["数据冒险", "load-use 冒险", "流水线暂停"],
    sourceLinks: [
      {
        id: "m-2-s-1",
        title: "指令流水线",
        location: "数据冒险与暂停",
        excerpt: "load-use 冒险常需要至少一个气泡，除非硬件提供更早的数据转发。",
      },
    ],
  },
  {
    id: "m-3",
    title: "浮点数加减运算规格化",
    topic: "浮点数运算",
    difficulty: "中等",
    wrongCount: 2,
    lastWrong: offsetDateKey(TODAY_DATE_KEY, -8),
    question:
      "浮点数加减运算完成尾数相加后，如果结果尾数出现 10.xxxx 的形式，下一步通常应如何规格化？",
    options: ["尾数右移一位，阶码加 1", "尾数左移一位，阶码减 1", "阶码不变，只舍入尾数", "直接判为溢出"],
    answer: 0,
    explanation:
      "尾数加法产生进位时，结果超出规格化范围，需要将尾数右移一位，并把阶码加 1，以保持数值不变。",
    errorReason:
      "上次只记住了尾数要移动，但方向和阶码补偿方向弄反了。",
    knowledgePoints: ["浮点加减", "尾数规格化", "阶码调整"],
    sourceLinks: [
      {
        id: "m-3-s-1",
        title: "浮点数运算",
        location: "加减法规格化",
        excerpt: "右规对应阶码增加，左规对应阶码减少。",
      },
    ],
  },
  {
    id: "m-4",
    title: "DMA 与中断 I/O 对比选择",
    topic: "总线与I/O",
    difficulty: "简单",
    wrongCount: 1,
    lastWrong: offsetDateKey(TODAY_DATE_KEY, -17),
    question:
      "当外设需要连续传输一大块数据，并希望尽量减少 CPU 对每个字节的干预时，更适合采用哪种 I/O 方式？",
    options: ["程序查询 I/O", "中断 I/O", "DMA", "条件传送"],
    answer: 2,
    explanation:
      "DMA 允许外设和内存之间直接成块传输数据，CPU 主要负责初始化和传输完成后的处理，适合大块连续数据。",
    errorReason:
      "上次只关注了中断能减少轮询等待，忽略了大块数据传输时 DMA 的优势。",
    knowledgePoints: ["DMA", "中断 I/O", "成块数据传输"],
    sourceLinks: [
      {
        id: "m-4-s-1",
        title: "总线与 I/O",
        location: "DMA 工作方式",
        excerpt: "DMA 的核心优势是减少 CPU 逐字节搬运数据的负担。",
      },
    ],
  },
  {
    id: "m-5",
    title: "虚拟地址到物理地址转换",
    topic: "虚拟存储器",
    difficulty: "困难",
    wrongCount: 4,
    lastWrong: offsetDateKey(TODAY_DATE_KEY, -5),
    question:
      "某分页系统页面大小为 4KB，虚拟地址为 0x2A3F。若页表给出虚页号 2 对应物理页框号 7，则该地址对应的物理地址是多少？",
    options: ["0x7A3F", "0x73F", "0x2A3F", "0x7000"],
    answer: 0,
    explanation:
      "4KB 页面大小表示页内偏移为低 12 位。0x2A3F 的虚页号为 0x2，页内偏移为 0xA3F。物理页框号为 0x7，因此物理地址为 0x7000 + 0xA3F = 0x7A3F。",
    errorReason:
      "上次把低 12 位偏移截成了低 8 位，导致页内偏移丢失。",
    knowledgePoints: ["分页地址转换", "页内偏移", "页框号拼接"],
    sourceLinks: [
      {
        id: "m-5-s-1",
        title: "虚拟存储器",
        location: "分页地址结构",
        excerpt: "页面大小决定页内偏移位数，页框号替换虚页号后与偏移拼接。",
      },
    ],
  },
  {
    id: "m-6",
    title: "总线仲裁方式判断",
    topic: "总线与I/O",
    difficulty: "中等",
    wrongCount: 2,
    lastWrong: offsetDateKey(TODAY_DATE_KEY, -11),
    question:
      "在集中式总线仲裁中，若多个设备通过一条授权线串行传递授权信号，越靠近仲裁器的设备优先级越高，这属于哪种仲裁方式？",
    options: ["链式查询", "计数器定时查询", "独立请求", "分布式仲裁"],
    answer: 0,
    explanation:
      "链式查询使用串行授权链，授权信号按物理连接顺序传递，因此靠近仲裁器的设备天然拥有更高优先级。",
    errorReason:
      "上次把“集中式”直接等同于独立请求，忽略了授权线串行传递这个特征。",
    knowledgePoints: ["总线仲裁", "链式查询", "集中式控制"],
    sourceLinks: [
      {
        id: "m-6-s-1",
        title: "总线与 I/O",
        location: "集中式仲裁方式",
        excerpt: "链式查询结构简单，但设备优先级受物理位置影响明显。",
      },
    ],
  },
];
