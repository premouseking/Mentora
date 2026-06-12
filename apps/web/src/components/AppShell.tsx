import type { ReactNode } from "react";
import {
  Bell,
  BookOpen,
  Bot,
  Check,
  ChevronLeft,
  FolderClosed,
  GraduationCap,
  History,
  Settings,
} from "lucide-react";
import { Link, NavLink } from "react-router-dom";

const navItems = [
  { to: "/courses", label: "课程", icon: BookOpen },
  { to: "/library", label: "资源库", icon: FolderClosed },
  { to: "/history", label: "学习记录", icon: History },
  { to: "/notifications", label: "通知", icon: Bell },
  { to: "/settings", label: "设置", icon: Settings },
];

const setupSteps = ["描述目标", "补充信息", "添加资料", "确认需求", "确认方案"];

function Brand() {
  return (
    <Link className="brand" to="/courses" aria-label="Mentora 课程首页">
      <span className="brand-mark">
        <GraduationCap size={18} strokeWidth={2.2} />
      </span>
      <span>Mentora</span>
    </Link>
  );
}

function WindowBar() {
  return (
    <div className="window-bar">
      <Brand />
      <div className="window-controls" aria-hidden="true">
        <span>−</span>
        <span>□</span>
        <span>×</span>
      </div>
    </div>
  );
}

function AppSidebar() {
  return (
    <aside className="sidebar">
      <nav className="primary-nav" aria-label="主导航">
        {navItems.map(({ to, label, icon: Icon }) => (
          <NavLink
            className={({ isActive }) => `nav-item${isActive ? " active" : ""}`}
            key={to}
            to={to}
          >
            <Icon size={19} strokeWidth={1.9} />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>
      <button className="ask-ai-button" type="button">
        <Bot size={18} />
        <span>问 AI</span>
      </button>
    </aside>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="desktop-app">
      <WindowBar />
      <div className="app-body">
        <AppSidebar />
        <section className="page-surface">{children}</section>
      </div>
    </div>
  );
}

function SetupProgress({ current }: { current: number }) {
  return (
    <ol className="setup-progress" aria-label="创建课程进度">
      {setupSteps.map((step, index) => {
        const number = index + 1;
        const completed = number < current;
        const active = number === current;
        return (
          <li className={active ? "active" : completed ? "completed" : ""} key={step}>
            <span className="step-marker">{completed ? <Check size={13} /> : number}</span>
            <span className="step-label">{step}</span>
          </li>
        );
      })}
    </ol>
  );
}

export function SetupShell({
  current,
  children,
}: {
  current: number;
  children: ReactNode;
}) {
  return (
    <div className="desktop-app setup-app">
      <WindowBar />
      <header className="setup-header">
        <Link className="back-link" to="/courses">
          <ChevronLeft size={18} />
          返回课程
        </Link>
        <SetupProgress current={current} />
        <Link className="cancel-link" to="/courses">
          取消
        </Link>
      </header>
      <main className="setup-main">{children}</main>
    </div>
  );
}
