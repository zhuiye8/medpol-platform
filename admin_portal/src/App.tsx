import { BrowserRouter, NavLink, Route, Routes } from "react-router-dom";
import DashboardPage from "@/pages/Dashboard";
import ArticlesPage from "@/pages/Articles";
import LogsPage from "@/pages/Logs";
import CrawlerManagementPage from "@/pages/CrawlerManagement";
import ArticleDetailPage from "@/pages/ArticleDetail";
import FinanceDataPage from "@/pages/FinanceData";
import EmbeddingsPage from "@/pages/Embeddings";
import EmbedChatPage from "@/pages/EmbedChat";
import MobilePreviewPage from "@/pages/MobilePreview";
import { useHealth } from "@/hooks/useHealth";

const NAV_ITEMS = [
  { path: "/", label: "概览" },
  { path: "/articles", label: "文章列表" },
  { path: "/logs", label: "运行日志" },
  { path: "/crawler-management", label: "爬虫管理" },
  { path: "/finance", label: "财务数据" },
  { path: "/embeddings", label: "向量化" },
  { path: "/mobile-preview", label: "移动端预览" },
];

function StatusPill({ status }: { status: "loading" | "up" | "down" }) {
  const label = status === "loading" ? "检测中" : status === "up" ? "服务正常" : "异常";
  return <span className={`status-pill ${status === "down" ? "down" : "up"}`}>{label}</span>;
}

function AdminLayout() {
  const { status, lastChecked, refresh } = useHealth();

  return (
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
          <Route path="/crawler-management" element={<CrawlerManagementPage />} />
          <Route path="/finance" element={<FinanceDataPage />} />
          <Route path="/embeddings" element={<EmbeddingsPage />} />
          <Route path="/mobile-preview" element={<MobilePreviewPage />} />
        </Routes>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Embed route - full screen, no sidebar */}
        <Route path="/embed/chat" element={<EmbedChatPage />} />
        {/* Admin routes - with sidebar */}
        <Route path="/*" element={<AdminLayout />} />
      </Routes>
    </BrowserRouter>
  );
}
