/**
 * Mentora 知识粒子汇聚加载动画。
 *
 * 设计：16 个发光粒子从圆环上各位置向中心汇聚，象征 AI 整合信息。
 * 外层 span 做圆环绝对定位，内层 span 通过 CSS 自定义属性 --mx/--my 做平移动画。
 *
 * @module components/MentoraLoader
 */

import { useMemo, type ReactNode } from "react";

interface MentoraLoaderProps {
  /** 下方提示文字 */
  message?: string;
  /** 粒子环直径（px），默认 160 */
  size?: number;
  /** 额外子元素（如详细描述） */
  children?: ReactNode;
}

function ringPositions(count: number): { x: number; y: number }[] {
  const positions: { x: number; y: number }[] = [];
  for (let i = 0; i < count; i++) {
    const angle = (i / count) * Math.PI * 2;
    positions.push({ x: Math.cos(angle), y: Math.sin(angle) });
  }
  return positions;
}

const PARTICLE_COUNT = 16;

export function MentoraLoader({ message, size = 160, children }: MentoraLoaderProps) {
  const positions = useMemo(() => ringPositions(PARTICLE_COUNT), []);

  return (
    <div className="mentora-loader">
      <div
        className="mentora-loader-ring"
        style={{ width: size, height: size }}
      >
        {positions.map((pos, i) => {
          const r = size / 2 - 10;          // 粒子距环心距离
          const cx = size / 2 + pos.x * r;   // 粒子在环上的 x
          const cy = size / 2 + pos.y * r;   // 粒子在环上的 y
          const dotSize = 5 + (i % 3) * 1.5;

          return (
            <span
              className="mentora-loader-pos"
              key={i}
              style={{
                left: cx,
                top: cy,
                width: dotSize,
                height: dotSize,
              }}
            >
              <span
                className="mentora-loader-particle"
                style={{
                  animationDelay: `${i * 0.09}s`,
                  // 粒子向环心移动的偏移量（负方向 × 距离）
                  "--mx": `${-pos.x * r}px`,
                  "--my": `${-pos.y * r}px`,
                } as React.CSSProperties}
              />
            </span>
          );
        })}
        {/* 中心光核 */}
        <span className="mentora-loader-core" />
      </div>
      {message && <p className="mentora-loader-text">{message}</p>}
      {children}
    </div>
  );
}
