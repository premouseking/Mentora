#!/usr/bin/env node
/**
 * Cursor beforeShellExecution hook：拦截破坏性 shell 命令。
 *
 * 约束：Git 写操作与文件还原类命令须由开发者在本地终端手动执行。
 */

let raw = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (c) => (raw += c));
process.stdin.on("end", () => {
  let command = "";
  try {
    command = (JSON.parse(raw).command || "").toString();
  } catch {
    return allow();
  }

  const cmd = command.trim();

  // ── Git 写操作（add / commit / push / pull / merge / rebase / stash 等）────────
  if (
    /\bgit\b[\s\S]*\b(add|commit|push|pull|merge|rebase|cherry-pick|stash)\b/.test(
      cmd
    )
  ) {
    return deny(
      "⛔ Git 写操作已被 Hook 拦截，请在本地终端手动执行",
      "Git 写操作（add/commit/push/pull/merge/rebase/stash 等）已被安全策略拦截。AI 不得直接提交或推送；请按 git-rules 向开发者提供可复制命令，由开发者在本机执行。"
    );
  }

  // ── git reset（含 --hard / --mixed 等）────────────────────────────────────────
  if (/\bgit\b[\s\S]*\breset\b/.test(cmd)) {
    return deny(
      "⛔ git reset 已被 Hook 拦截",
      "git reset 会改写暂存区或丢弃本地改动，禁止通过 AI 自动执行，请让开发者手动决策。"
    );
  }

  // ── git checkout 还原文件或切换分支 ─────────────────────────────────────────────
  if (/\bgit\b[\s\S]*\bcheckout\b/.test(cmd)) {
    return deny(
      "⛔ git checkout 已被 Hook 拦截",
      "git checkout 可能丢弃本地改动或切换分支，禁止通过 AI 自动执行，请让开发者手动决策。"
    );
  }

  // ── git restore / git switch ───────────────────────────────────────────────────
  if (/\bgit\b[\s\S]*\b(restore|switch)\b/.test(cmd)) {
    return deny(
      "⛔ git restore/switch 已被 Hook 拦截",
      "git restore/switch 会改写工作区或分支，禁止通过 AI 自动执行，请让开发者手动决策。"
    );
  }

  // ── 文件删除（Unix / PowerShell）──────────────────────────────────────────────
  if (/(^|[;&|`|\s])rm(\s|$|-)/.test(cmd)) {
    return deny(
      "⛔ rm 命令已被 Hook 拦截",
      "rm 命令已被安全策略拦截。禁止通过 AI 直接删除文件，请使用 Delete 工具并在开发者明确要求时操作。"
    );
  }
  if (/\b(Remove-Item|ri)\b/i.test(cmd) && /\b(-Recurse|-Force|-rf)\b/i.test(cmd)) {
    return deny(
      "⛔ Remove-Item 删除命令已被 Hook 拦截",
      "PowerShell 递归/强制删除已被安全策略拦截。请让开发者手动决策或使用 Delete 工具。"
    );
  }
  if (/\b(rmdir|rd)\b/i.test(cmd) && /\b(\/s|\/q|-Recurse)\b/i.test(cmd)) {
    return deny(
      "⛔ rmdir/rd 删除命令已被 Hook 拦截",
      "目录删除命令已被安全策略拦截，请让开发者手动决策。"
    );
  }

  return allow();
});

function allow() {
  process.stdout.write(JSON.stringify({ permission: "allow" }));
  process.exit(0);
}

function deny(user_message, agent_message) {
  process.stdout.write(
    JSON.stringify({ permission: "deny", user_message, agent_message })
  );
  process.exit(0);
}
