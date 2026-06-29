import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import rehypeKatex from "rehype-katex";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import "katex/dist/katex.min.css";

import { normalizeAssistantMarkdown } from "./assistantMarkdownUtils";

interface AssistantMarkdownProps {
  content: string;
}

function flattenChildren(children: ReactNode): string {
  if (children == null || typeof children === "boolean") return "";
  if (typeof children === "string" || typeof children === "number") return String(children);
  if (Array.isArray(children)) return children.map(flattenChildren).join("");
  if (typeof children === "object" && "props" in children) {
    return flattenChildren((children as { props?: { children?: ReactNode } }).props?.children);
  }
  return "";
}

function CodeBlock({
  className,
  children,
  inline,
  ...props
}: React.ComponentProps<"code"> & { inline?: boolean }) {
  const code = flattenChildren(children).replace(/\n$/, "");
  const language = /language-(\w+)/.exec(className ?? "")?.[1] ?? "text";
  const [copied, setCopied] = useState(false);

  if (inline) {
    return (
      <code className="assistant-md-inline-code" {...props}>
        {children}
      </code>
    );
  }

  async function copyCode() {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1200);
  }

  return (
    <div className="assistant-md-code-block">
      <div className="assistant-md-code-head">
        <span>{language}</span>
        <button type="button" onClick={copyCode}>
          {copied ? "已复制" : "复制"}
        </button>
      </div>
      <pre>
        <code className={className}>{code}</code>
      </pre>
    </div>
  );
}

function attachFormulaCopyButtons(root: HTMLDivElement) {
  root.querySelectorAll<HTMLElement>(".katex-display").forEach((display) => {
    if (display.querySelector(".assistant-md-math-copy")) return;
    const annotation = display.querySelector<HTMLElement>(
      'annotation[encoding="application/x-tex"]',
    );
    const latex = annotation?.textContent?.trim();
    if (!latex) return;

    display.classList.add("assistant-md-math-wrap");
    const button = document.createElement("button");
    button.type = "button";
    button.className = "assistant-md-math-copy";
    button.textContent = "复制公式";
    button.addEventListener("click", async (event) => {
      event.preventDefault();
      event.stopPropagation();
      await navigator.clipboard.writeText(latex);
      button.textContent = "已复制";
      window.setTimeout(() => {
        button.textContent = "复制公式";
      }, 1200);
    });
    display.appendChild(button);
  });
}

function getKatexTexFromElement(element: Element | null): string {
  const katex = element?.closest(".katex");
  const annotation = katex?.querySelector<HTMLElement>('annotation[encoding="application/x-tex"]');
  return annotation?.textContent?.trim() ?? "";
}

function getSelectedKatexTex(root: HTMLElement): string {
  const selection = window.getSelection();
  if (!selection || selection.isCollapsed) return "";
  const formulas = Array.from(root.querySelectorAll<HTMLElement>(".katex"));
  const selectedTex = formulas
    .filter((formula) => selection.containsNode(formula, true))
    .map((formula) => getKatexTexFromElement(formula))
    .filter(Boolean);
  return selectedTex.join("\n");
}

const markdownComponents: Components = {
  code: CodeBlock,
  pre: ({ children }) => <>{children}</>,
  table: ({ children, ...props }) => (
    <div className="assistant-md-table-wrap">
      <table {...props}>{children}</table>
    </div>
  ),
  a: ({ children, href, ...props }) => (
    <a href={href} target="_blank" rel="noreferrer" {...props}>
      {children}
    </a>
  ),
};

export function AssistantMarkdown({ content }: AssistantMarkdownProps) {
  const rootRef = useRef<HTMLDivElement | null>(null);
  const normalized = useMemo(() => normalizeAssistantMarkdown(content), [content]);

  useEffect(() => {
    if (!rootRef.current) return;
    const root = rootRef.current;
    attachFormulaCopyButtons(root);

    const handleFormulaClick = async (event: MouseEvent) => {
      const target = event.target instanceof Element ? event.target : null;
      if (target?.closest(".assistant-md-math-copy")) return;
      const tex = getKatexTexFromElement(target);
      if (!tex) return;
      await navigator.clipboard.writeText(tex);
    };

    const handleCopy = (event: ClipboardEvent) => {
      const tex = getSelectedKatexTex(root);
      if (!tex || !event.clipboardData) return;
      event.preventDefault();
      event.clipboardData.setData("text/plain", tex);
    };

    root.addEventListener("click", handleFormulaClick);
    root.addEventListener("copy", handleCopy, true);
    return () => {
      root.removeEventListener("click", handleFormulaClick);
      root.removeEventListener("copy", handleCopy, true);
    };
  }, [normalized]);

  if (!normalized) return null;

  return (
    <div ref={rootRef} className="assistant-md-root">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={markdownComponents}
      >
        {normalized}
      </ReactMarkdown>
    </div>
  );
}
