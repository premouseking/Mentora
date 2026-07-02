import { Component, type ErrorInfo, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { clearLastCrash, readLastCrash, recordCrash } from "../lib/crashReporter";

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
  crashMessage: string;
}

/** 捕获 React 渲染树异常，避免整页白屏。 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null, crashMessage: "" };

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { error, crashMessage: error.message };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    recordCrash({
      message: error.message,
      stack: [error.stack, info.componentStack].filter(Boolean).join("\n"),
      source: "react",
      at: new Date().toISOString(),
    });
  }

  private handleReload = (): void => {
    clearLastCrash();
    window.location.reload();
  };

  render() {
    if (!this.state.error) {
      return this.props.children;
    }

    const last = readLastCrash();

    return (
      <div className="app-crash-fallback">
        <div className="app-crash-card">
          <h1>页面遇到问题</h1>
          <p>应用遇到未处理的错误。你可以重新加载页面，或返回课程列表继续。</p>
          <p className="app-crash-detail">{this.state.crashMessage || last?.message}</p>
          <div className="app-crash-actions">
            <button className="button primary" onClick={this.handleReload} type="button">
              重新加载
            </button>
            <Link className="button secondary" to="/courses" onClick={clearLastCrash}>
              返回课程
            </Link>
          </div>
        </div>
      </div>
    );
  }
}
