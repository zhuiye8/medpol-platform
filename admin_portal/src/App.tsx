import { lazy, Suspense } from "react";
import { BrowserRouter, NavLink, Route, Routes, Navigate, useLocation } from "react-router-dom";
import { useHealth } from "@/hooks/useHealth";
import { AuthProvider, useAuth, useIsAdmin } from "@/context/AuthContext";

// 首屏关键页面：静态导入（立即加载）
import DashboardPage from "@/pages/Dashboard";
import ArticlesPage from "@/pages/Articles";
import LoginPage from "@/pages/Login";

// 次要页面：懒加载（按需加载）
const LogsPage = lazy(() => import("@/pages/Logs"));
const CrawlerManagementPage = lazy(() => import("@/pages/CrawlerManagement"));
const ArticleDetailPage = lazy(() => import("@/pages/ArticleDetail"));
const FinanceDataPage = lazy(() => import("@/pages/FinanceData"));
const EmbeddingsPage = lazy(() => import("@/pages/Embeddings"));
const EmbedChatPage = lazy(() => import("@/pages/EmbedChat"));
const MobilePreviewPage = lazy(() => import("@/pages/MobilePreview"));
const UsersPage = lazy(() => import("@/pages/Users"));
const RolesPage = lazy(() => import("@/pages/Roles"));
const EmployeeImportPage = lazy(() => import("@/pages/EmployeeImport"));

// 页面加载占位符
function PageLoader() {
  return <div className="panel" style={{ textAlign: "center", padding: "2rem" }}>加载中...</div>;
}

// 路由守卫组件
function RequireAuth({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return <PageLoader />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
}

// 管理员路由守卫
function RequireAdmin({ children }: { children: React.ReactNode }) {
  const isAdmin = useIsAdmin();

  if (!isAdmin) {
    return (
      <div className="panel" style={{ textAlign: "center", padding: "2rem" }}>
        <h2>权限不足</h2>
        <p className="muted">您没有权限访问此页面</p>
      </div>
    );
  }

  return <>{children}</>;
}

const NAV_ITEMS = [
  { path: "/", label: "概览" },
  { path: "/articles", label: "文章列表" },
  { path: "/logs", label: "运行日志" },
  { path: "/crawler-management", label: "爬虫管理" },
  { path: "/finance", label: "财务数据" },
  { path: "/embeddings", label: "向量化" },
  { path: "/mobile-preview", label: "移动端预览" },
];

// 管理员专属菜单
const ADMIN_NAV_ITEMS = [
  { path: "/users", label: "用户管理" },
  { path: "/roles", label: "角色管理" },
  { path: "/employee-import", label: "员工导入" },
];

function StatusPill({ status }: { status: "loading" | "up" | "down" }) {
  const label = status === "loading" ? "检测中" : status === "up" ? "服务正常" : "异常";
  return <span className={`status-pill ${status === "down" ? "down" : "up"}`}>{label}</span>;
}

function AdminLayout() {
  const { status, lastChecked, refresh } = useHealth();
  const { user, logout } = useAuth();
  const isAdmin = useIsAdmin();

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
          {isAdmin && ADMIN_NAV_ITEMS.map((item) => (
            <NavLink key={item.path} to={item.path}>
              {item.label}
            </NavLink>
          ))}
        </nav>

        {/* 用户信息和登出 */}
        <div style={{ marginTop: "auto", paddingTop: 16, borderTop: "1px solid rgba(255,255,255,0.1)" }}>
          <div style={{ fontSize: 13, color: "#cbd5f5", marginBottom: 8 }}>
            {user?.display_name || user?.username}
            {user?.roles.includes("admin") && (
              <span style={{ marginLeft: 6, fontSize: 11, color: "#94a3b8" }}>(管理员)</span>
            )}
          </div>
          <button
            className="ghost"
            style={{ width: "100%", fontSize: 13 }}
            onClick={logout}
          >
            退出登录
          </button>
        </div>
      </aside>
      <main className="content">
        <Suspense fallback={<PageLoader />}>
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/articles" element={<ArticlesPage />} />
            <Route path="/articles/:articleId" element={<ArticleDetailPage />} />
            <Route path="/logs" element={<LogsPage />} />
            <Route path="/crawler-management" element={<CrawlerManagementPage />} />
            <Route path="/finance" element={<FinanceDataPage />} />
            <Route path="/embeddings" element={<EmbeddingsPage />} />
            <Route path="/mobile-preview" element={<MobilePreviewPage />} />
            <Route
              path="/users"
              element={
                <RequireAdmin>
                  <UsersPage />
                </RequireAdmin>
              }
            />
            <Route
              path="/roles"
              element={
                <RequireAdmin>
                  <RolesPage />
                </RequireAdmin>
              }
            />
            <Route
              path="/employee-import"
              element={
                <RequireAdmin>
                  <EmployeeImportPage />
                </RequireAdmin>
              }
            />
          </Routes>
        </Suspense>
      </main>
    </div>
  );
}

function AppRoutes() {
  const { isAuthenticated, isLoading } = useAuth();

  // Show loading while checking auth
  if (isLoading) {
    return <PageLoader />;
  }

  return (
    <Suspense fallback={<PageLoader />}>
      <Routes>
        {/* Login route */}
        <Route
          path="/login"
          element={isAuthenticated ? <Navigate to="/" replace /> : <LoginPage />}
        />
        {/* Embed route - full screen, no sidebar, no auth required */}
        <Route path="/embed/chat" element={<EmbedChatPage />} />
        {/* Admin routes - with sidebar, auth required */}
        <Route
          path="/*"
          element={
            <RequireAuth>
              <AdminLayout />
            </RequireAuth>
          }
        />
      </Routes>
    </Suspense>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}
