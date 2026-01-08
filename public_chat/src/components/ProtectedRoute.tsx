/**
 * ProtectedRoute - 路由守卫组件
 *
 * 功能：
 * - 未认证时重定向到认证页面
 * - 支持 URL token 参数自动认证（用于 iframe 嵌入）
 */
import { useEffect, useState } from "react";
import { Navigate, useSearchParams } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";

interface ProtectedRouteProps {
  children: React.ReactNode;
}

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { isAuthenticated, verifyToken } = useAuth();
  const [searchParams] = useSearchParams();
  const [isChecking, setIsChecking] = useState(true);

  useEffect(() => {
    const token = searchParams.get("token");
    if (token && !isAuthenticated) {
      verifyToken(token);
    }
    setIsChecking(false);
  }, [searchParams, isAuthenticated, verifyToken]);

  // 正在检查 token，显示空白避免闪烁
  if (isChecking) {
    return null;
  }

  if (!isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
}

export default ProtectedRoute;
