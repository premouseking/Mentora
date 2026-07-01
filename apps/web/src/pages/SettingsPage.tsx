import { useState } from "react";
import { Bell, Database, Info, ListChecks, User } from "lucide-react";
import { AppShell } from "../components/AppShell";

type SettingsSection = "quiz" | "notifications" | "storage" | "account" | "about";

type SectionDef = { key: SettingsSection; label: string; icon: typeof ListChecks };

const sections: SectionDef[] = [
  { key: "quiz", label: "刷题设置", icon: ListChecks },
  { key: "notifications", label: "消息通知", icon: Bell },
  { key: "storage", label: "存储管理", icon: Database },
  { key: "account", label: "账号管理", icon: User },
  { key: "about", label: "关于", icon: Info },
];

/* ── 各面板（占位） ── */

const panels: Record<SettingsSection, () => React.JSX.Element> = {
  quiz: () => (
    <div className="settings-panel">
      <h2 className="settings-panel-title">刷题设置</h2>
      <p className="settings-placeholder">刷题设置项待添加。</p>
    </div>
  ),
  notifications: () => (
    <div className="settings-panel">
      <h2 className="settings-panel-title">消息通知</h2>
      <p className="settings-placeholder">消息通知设置项待添加。</p>
    </div>
  ),
  storage: () => (
    <div className="settings-panel">
      <h2 className="settings-panel-title">存储管理</h2>
      <p className="settings-placeholder">存储管理设置项待添加。</p>
    </div>
  ),
  account: () => (
    <div className="settings-panel">
      <h2 className="settings-panel-title">账号管理</h2>
      <p className="settings-placeholder">账号管理设置项待添加。</p>
    </div>
  ),
  about: () => (
    <div className="settings-panel">
      <h2 className="settings-panel-title">关于</h2>
      <p className="settings-placeholder">版本与许可信息待添加。</p>
    </div>
  ),
};

export function SettingsPage() {
  const [active, setActive] = useState<SettingsSection>("quiz");

  const PanelComponent = panels[active];

  return (
    <AppShell>
      <div className="settings-page">
        <nav className="settings-nav" aria-label="设置目录">
          {sections.map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              className={`settings-nav-item${active === key ? " active" : ""}`}
              onClick={() => setActive(key)}
              type="button"
            >
              <Icon size={17} strokeWidth={1.8} />
              {label}
            </button>
          ))}
        </nav>
        <section className="settings-content">
          <PanelComponent />
        </section>
      </div>
    </AppShell>
  );
}
