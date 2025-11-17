import { BrowserRouter, NavLink, Route, Routes } from "react-router-dom";
import DashboardPage from "@/pages/Dashboard";
import ArticlesPage from "@/pages/Articles";
import LogsPage from "@/pages/Logs";
import SchedulerPage from "@/pages/Scheduler";
import ArticleDetailPage from "@/pages/ArticleDetail";
import { useHealth } from "@/hooks/useHealth";

const NAV_ITEMS = [
  { path: "/", label: "概览" },
  { path: "/articles", label: "文章列表" },
  { path: "/logs", label: "运行日志" },
  { path: "/scheduler", label: "任务调度" },
];

function StatusPill({ status }: { status: "loading" | "up" | "down" }) {
  const label = status === "loading" ? "检测中" : status === "up" ? "服务正常" : "异常";
  return <span className={`status-pill ${status === "down" ? "down" : "up"}`}>{label}</span>;
}

export default function App() {
  const { status, lastChecked, refresh } = useHealth();

  return (
    <BrowserRouter>
      <div className="app-shell">
        <aside className="sidebar">
          <div className="sidebar__logo">医药政策聚合后台</div>
          <div style={{ fontSize: 12, color: "#94a3b8" }}>
            API 状态{" "}
            <button className="ghost" style={{ padding: "2px 8px", marginLeft: 6 }} onClick={refresh}>
              重试
            </button>
          </div>
          <StatusPill status={status} />
          {lastChecked ? (
            <span style={{ fontSize: 12, color: "#94a3b8" }}>
              最近检测：{lastChecked.toLocaleTimeString()}
            </span>
          ) : null}
          <nav className="sidebar__nav">
            {NAV_ITEMS.map((item) => (
              <NavLink key={item.path} to={item.path} end={item.path === "/"}>
                {item.label}
              </NavLink>
            ))}
          </nav>
        </aside>
        <main className="content">
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/articles" element={<ArticlesPage />} />
            <Route path="/articles/:articleId" element={<ArticleDetailPage />} />
            <Route path="/logs" element={<LogsPage />} />
            <Route path="/scheduler" element={<SchedulerPage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
