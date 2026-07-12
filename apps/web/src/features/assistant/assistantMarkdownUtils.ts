export function normalizeAssistantMarkdown(value?: string | null): string {
  const raw = String(value ?? "").trim();
  if (!raw) return "";

  return raw
    .replace(/\\\[([\s\S]*?)\\\]/g, (_match, latex: string) => {
      const content = String(latex).trim();
      return content ? `$$\n${content}\n$$` : "";
    })
    .replace(/\\\(([\s\S]*?)\\\)/g, (_match, latex: string) => {
      const content = String(latex).trim();
      return content ? `$${content}$` : "";
    });
}
