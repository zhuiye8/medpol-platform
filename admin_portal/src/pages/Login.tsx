/**
 * Login page for admin portal.
 */

import { useState, type FormEvent } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";

export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { login, isLoading } = useAuth();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  // Get the intended destination after login
  const from = (location.state as { from?: { pathname: string } })?.from?.pathname || "/";

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");

    if (!username.trim() || !password.trim()) {
      setError("请输入用户名和密码");
      return;
    }

    try {
      await login(username, password);
      navigate(from, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "登录失败");
    }
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-header">
          <h1>医药政策管理平台</h1>
          <p className="muted">管理后台登录</p>
        </div>

        {error && <div className="error-banner">{error}</div>}

        <form onSubmit={handleSubmit} className="login-form">
          <label>
            <span>用户名</span>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="请输入用户名"
              autoComplete="username"
              autoFocus
            />
          </label>

          <label>
            <span>密码</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="请输入密码"
              autoComplete="current-password"
            />
          </label>

          <button type="submit" className="primary login-btn" disabled={isLoading}>
            {isLoading ? "登录中..." : "登录"}
          </button>
        </form>
      </div>

      <style>{`
        .login-page {
          min-height: 100vh;
          display: flex;
          align-items: center;
          justify-content: center;
          background: linear-gradient(135deg, #f4f6fb 0%, #e0f2fe 100%);
          padding: 24px;
        }

        .login-card {
          width: 100%;
          max-width: 400px;
          background: #fff;
          border-radius: 16px;
          padding: 32px;
          box-shadow: 0 12px 40px rgba(15, 23, 42, 0.12);
        }

        .login-header {
          text-align: center;
          margin-bottom: 24px;
        }

        .login-header h1 {
          margin: 0 0 8px 0;
          font-size: 24px;
          color: #0f172a;
        }

        .login-form {
          display: flex;
          flex-direction: column;
          gap: 16px;
        }

        .login-form label {
          display: flex;
          flex-direction: column;
          gap: 6px;
          font-size: 14px;
          color: #334155;
        }

        .login-form input {
          height: 42px;
          border: 1px solid #e2e8f0;
          border-radius: 8px;
          padding: 0 12px;
          font-size: 14px;
          transition: border-color 0.2s;
        }

        .login-form input:focus {
          outline: none;
          border-color: #2563eb;
          box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
        }

        .login-btn {
          height: 42px;
          margin-top: 8px;
          font-size: 15px;
          font-weight: 500;
        }

        .login-btn:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }
      `}</style>
    </div>
  );
}
