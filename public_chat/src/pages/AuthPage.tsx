/**
 * AuthPage - 访问码认证页面
 *
 * 功能：
 * - 居中卡片布局
 * - 密码输入框（支持显示/隐藏）
 * - 主题感知样式
 * - 认证成功后跳转到对话页面
 */
import { useState, useCallback, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";
import { useTheme } from "@/stores/themeStore";
import { ThemeToggle } from "@/components/ThemeToggle";
import "./AuthPage.css";

export function AuthPage() {
  // 初始化主题
  useTheme();

  const navigate = useNavigate();
  const { isAuthenticated, verify } = useAuth();

  const [accessCode, setAccessCode] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  // 已认证则跳转
  useEffect(() => {
    if (isAuthenticated) {
      navigate("/chat", { replace: true });
    }
  }, [isAuthenticated, navigate]);

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();

      if (!accessCode.trim()) {
        setError("请输入访问码");
        return;
      }

      setIsLoading(true);
      setError("");

      // 短暂延迟优化体验
      await new Promise((resolve) => setTimeout(resolve, 300));

      const isValid = verify(accessCode.trim());

      if (isValid) {
        navigate("/chat", { replace: true });
      } else {
        setError("访问码错误，请重试");
        setIsLoading(false);
      }
    },
    [accessCode, verify, navigate]
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !isLoading) {
        handleSubmit(e);
      }
    },
    [handleSubmit, isLoading]
  );

  return (
    <div className="auth-page">
      {/* 右上角主题切换 */}
      <div className="auth-page__theme-toggle">
        <ThemeToggle />
      </div>

      {/* 主卡片 */}
      <div className="auth-card">
        {/* 图标 */}
        <div className="auth-card__logo">
          <div className="auth-card__logo-icon">
            <svg
              width="48"
              height="48"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
              <circle cx="9" cy="10" r="1" fill="currentColor" />
              <circle cx="12" cy="10" r="1" fill="currentColor" />
              <circle cx="15" cy="10" r="1" fill="currentColor" />
            </svg>
          </div>
        </div>

        {/* 标题 */}
        <h1 className="auth-card__title">数智联环平台</h1>
        <p className="auth-card__subtitle">
          基于知识库的智能政策问答系统
        </p>

        {/* 表单 */}
        <form className="auth-card__form" onSubmit={handleSubmit}>
          <div className="auth-card__input-wrapper">
            <input
              type={showPassword ? "text" : "password"}
              className={`auth-card__input ${error ? "auth-card__input--error" : ""}`}
              placeholder="请输入访问码"
              value={accessCode}
              onChange={(e) => {
                setAccessCode(e.target.value);
                setError("");
              }}
              onKeyDown={handleKeyDown}
              autoFocus
              disabled={isLoading}
            />
            <button
              type="button"
              className="auth-card__toggle-password"
              onClick={() => setShowPassword(!showPassword)}
              title={showPassword ? "隐藏" : "显示"}
              tabIndex={-1}
            >
              {showPassword ? (
                <svg
                  width="20"
                  height="20"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                  <line x1="1" y1="1" x2="23" y2="23" />
                </svg>
              ) : (
                <svg
                  width="20"
                  height="20"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                  <circle cx="12" cy="12" r="3" />
                </svg>
              )}
            </button>
          </div>

          {/* 错误提示 */}
          {error && <p className="auth-card__error">{error}</p>}

          {/* 提交按钮 */}
          <button
            type="submit"
            className="auth-card__submit"
            disabled={isLoading}
          >
            {isLoading ? (
              <span className="auth-card__loading">
                <svg
                  className="auth-card__spinner"
                  width="20"
                  height="20"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M21 12a9 9 0 1 1-6.219-8.56" />
                </svg>
                验证中...
              </span>
            ) : (
              "进入系统"
            )}
          </button>
        </form>

        {/* 底部提示 */}
        <p className="auth-card__footer">
          访问码请联系管理员获取
        </p>
      </div>
    </div>
  );
}

export default AuthPage;
