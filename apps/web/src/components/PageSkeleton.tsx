/** 路由切换时的通用页面骨架屏。 */
export function PageSkeleton() {
  return (
    <div className="page-skeleton" aria-busy="true" aria-label="页面加载中">
      <div className="page-skeleton-header" />
      <div className="page-skeleton-body">
        <div className="page-skeleton-line wide" />
        <div className="page-skeleton-line" />
        <div className="page-skeleton-line medium" />
      </div>
    </div>
  );
}

/** 课程工作台首屏骨架。 */
export function WorkspaceSkeleton() {
  return (
    <div className="workspace-skeleton" aria-busy="true" aria-label="工作台加载中">
      <aside className="workspace-skeleton-sidebar">
        <div className="page-skeleton-line wide" />
        <div className="page-skeleton-line" />
        <div className="page-skeleton-line medium" />
      </aside>
      <section className="workspace-skeleton-main">
        <div className="page-skeleton-header" />
        <div className="page-skeleton-line wide" />
        <div className="page-skeleton-line" />
      </section>
    </div>
  );
}
