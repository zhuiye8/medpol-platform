/**
 * useAuth - 访问码认证钩子
 *
 * 功能：
 * - 验证访问码（前端仅验证非空，真正权限验证由后端完成）
 * - 认证状态存储在 sessionStorage（关闭浏览器后失效）
 * - 访问码存储供后续请求使用
 */
import { useState, useCallback, useEffect } from "react";

const AUTH_STORAGE_KEY = "medpol_chat_auth";
const ACCESS_CODE_STORAGE_KEY = "medpol_access_code";

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
    // 前端只验证非空，真正的权限验证由后端完成
    const isValid = code.trim().length > 0;
    if (isValid) {
      setIsAuthenticated(true);
      // 存储访问码，供后续聊天请求使用
      sessionStorage.setItem(ACCESS_CODE_STORAGE_KEY, code.trim());
      setStoredAuth(true);
    }
    return isValid;
  }, []);

  const logout = useCallback(() => {
    setIsAuthenticated(false);
    setStoredAuth(false);
    // 清空访问码
    sessionStorage.removeItem(ACCESS_CODE_STORAGE_KEY);
  }, []);

  return {
    isAuthenticated,
    verify,
    verifyToken: verify,  // URL token 认证（与 verify 相同逻辑）
    logout,
  };
}

export default useAuth;
