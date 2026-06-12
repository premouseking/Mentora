import { BookOpen, MessageSquare, Plus, Upload } from "lucide-react";

const courses = [
  {
    name: "计算机系统基础",
    intent: "7 天期末速通",
    next: "继续学习 Cache 地址映射",
    progress: 42,
  },
];

export function App() {
  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Mentora</p>
          <h1>我的课程</h1>
        </div>
        <button className="button secondary" type="button">
          <Plus size={18} />
          创建课程
        </button>
      </header>

      <section className="course-grid" aria-label="课程列表">
        {courses.map((course) => (
          <article className="course-card" key={course.name}>
            <div className="course-heading">
              <BookOpen size={22} />
              <div>
                <h2>{course.name}</h2>
                <p>{course.intent}</p>
              </div>
            </div>
            <div className="progress-track" aria-label={`学习进度 ${course.progress}%`}>
              <span style={{ width: `${course.progress}%` }} />
            </div>
            <p className="next-task">{course.next}</p>
            <button className="button primary" type="button">
              继续学习
            </button>
            <div className="quick-actions">
              <button type="button" title="上传资料">
                <Upload size={17} />
                上传资料
              </button>
              <button type="button" title="向课程助手提问">
                <MessageSquare size={17} />
                问 AI
              </button>
            </div>
          </article>
        ))}
      </section>
    </main>
  );
}

