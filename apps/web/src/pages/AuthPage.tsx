import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useAuth } from "../hooks/useAuth";
import { isDevAuthBypassStatus } from "../lib/desktop";
import { DesktopTitleBar } from "../components/DesktopTitleBar";

type AuthMode = "login" | "register";

function MentoraMark() {
  return (
    <svg
      aria-hidden="true"
      className="mentora-mark"
      fill="none"
      viewBox="0 0 24 24"
    >
      <path
        d="M5 18.5V5.5l7 5 7-5v13"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="2"
      />
      <path
        d="M12 10.5V20.5l2-1.45 2 1.45V8.65"
        stroke="currentColor"
        strokeLinejoin="round"
        strokeWidth="1.55"
      />
      <path
        d="M8 17.5h8"
        stroke="currentColor"
        strokeLinecap="round"
        strokeWidth="1.8"
      />
    </svg>
  );
}

export function AuthPage() {
  const navigate = useNavigate();
  const { status, desktop, login, register } = useAuth();
  const [mode, setMode] = useState<AuthMode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (status.state === "signed-in") {
      navigate("/courses", { replace: true });
    }
  }, [navigate, status.state]);

  function switchMode(next: AuthMode) {
    setMode(next);
    setError(null);
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      if (mode === "login") {
        await login({ email: email.trim(), password });
      } else {
        const trimmedName = displayName.trim();
        await register({
          email: email.trim(),
          password,
          displayName: trimmedName || undefined,
        });
      }
      navigate("/courses", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "操作失败，请稍后重试");
    } finally {
      setSubmitting(false);
    }
  }

  const canSubmit =
    email.trim().length > 0 &&
    password.length >= 8 &&
    !submitting &&
    status.state !== "signing-in";

  const busy = submitting || status.state === "signing-in";
  const devBypass = !desktop || isDevAuthBypassStatus(status);

  return (
    <div className="desktop-app auth-app">
      <DesktopTitleBar />
      <main className="auth-page">
        <div className="auth-card">
        <div className="auth-brand">
          <span className="auth-brand-mark">
            <MentoraMark />
          </span>
          <strong>Mentora</strong>
        </div>

        <div className="auth-heading">
          <h1>{mode === "login" ? "登录" : "注册"}</h1>
        </div>

        <div className="auth-tabs" role="tablist" aria-label="认证方式">
          <button
            className={mode === "login" ? "active" : ""}
            type="button"
            role="tab"
            aria-selected={mode === "login"}
            onClick={() => switchMode("login")}
          >
            登录
          </button>
          <button
            className={mode === "register" ? "active" : ""}
            type="button"
            role="tab"
            aria-selected={mode === "register"}
            onClick={() => switchMode("register")}
          >
            注册
          </button>
        </div>

        <form className="auth-form" onSubmit={handleSubmit}>
          {devBypass && (
            <p className="auth-dev-hint">
              {desktop
                ? "开发环境已跳过认证门禁。设置 MENTORA_DEV_AUTH_BYPASS=0 可验证完整登录流程。"
                : "当前为浏览器预览模式，认证门禁已跳过。请在桌面客户端中体验完整登录流程。"}
            </p>
          )}

          {mode === "register" && (
            <label className="auth-field">
              <span>昵称（可选）</span>
              <input
                autoComplete="name"
                maxLength={64}
                onChange={(event) => setDisplayName(event.target.value)}
                placeholder="如何称呼你"
                value={displayName}
              />
            </label>
          )}

          <label className="auth-field">
            <span>邮箱</span>
            <input
              autoComplete="email"
              onChange={(event) => setEmail(event.target.value)}
              placeholder="you@example.com"
              required
              type="email"
              value={email}
            />
          </label>

          <label className="auth-field">
            <span>密码</span>
            <div className="auth-password">
              <input
                autoComplete={
                  mode === "login" ? "current-password" : "new-password"
                }
                minLength={8}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="至少 8 位"
                required
                type={showPassword ? "text" : "password"}
                value={password}
              />
              <button
                aria-label={showPassword ? "隐藏密码" : "显示密码"}
                className="auth-password-toggle"
                onClick={() => setShowPassword((prev) => !prev)}
                type="button"
              >
                {showPassword ? "隐藏" : "显示"}
              </button>
            </div>
          </label>

          {error && <p className="auth-error">{error}</p>}

          <button
            className="button primary auth-submit"
            disabled={!canSubmit}
            type="submit"
          >
            {busy ? "处理中…" : mode === "login" ? "登录" : "注册"}
          </button>
        </form>
        </div>
      </main>
    </div>
  );
}
