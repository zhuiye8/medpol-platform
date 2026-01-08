/**
 * useAuth - 访问码认证钩子
 *
 * 功能：
 * - 验证访问码（与环境变量对比）
 * - 认证状态存储在 sessionStorage（关闭浏览器后失效）
 * - 默认访问码：nature@lianhuan
 */
import { useState, useCallback, useEffect } from "react";

const AUTH_STORAGE_KEY = "medpol_chat_auth";
const ACCESS_CODE = import.meta.env.VITE_ACCESS_CODE || "nature@lianhuan";

function getStoredAuth(): boolean {
  try {
    return sessionStorage.getItem(AUTH_STORAGE_KEY) === "true";
  } catch {
    return false;
  }
}

function setStoredAuth(isAuth: boolean): void {
  try {
    if (isAuth) {
      sessionStorage.setItem(AUTH_STORAGE_KEY, "true");
    } else {
      sessionStorage.removeItem(AUTH_STORAGE_KEY);
    }
  } catch (err) {
    console.error("保存认证状态失败:", err);
  }
}

export function useAuth() {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(() => {
    return getStoredAuth();
  });

  // 挂载时同步存储状态
  useEffect(() => {
    const stored = getStoredAuth();
    if (stored !== isAuthenticated) {
      setIsAuthenticated(stored);
    }
  }, []);

  const verify = useCallback((code: string): boolean => {
    const isValid = code === ACCESS_CODE;
    if (isValid) {
      setIsAuthenticated(true);
      setStoredAuth(true);
    }
    return isValid;
  }, []);

  const logout = useCallback(() => {
    setIsAuthenticated(false);
    setStoredAuth(false);
  }, []);

  return {
    isAuthenticated,
    verify,
    verifyToken: verify,  // URL token 认证（与 verify 相同逻辑）
    logout,
  };
}

export default useAuth;
