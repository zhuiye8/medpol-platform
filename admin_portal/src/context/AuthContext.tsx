/**
 * Authentication Context for admin portal.
 */

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  type ReactNode,
} from "react";

import {
  login as apiLogin,
  logout as apiLogout,
  getCurrentUser,
  getToken,
  type UserInfo,
} from "../services/auth";

// ======================== Types ========================

interface AuthState {
  user: UserInfo | null;
  isLoading: boolean;
  isAuthenticated: boolean;
}

interface AuthContextValue extends AuthState {
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

// ======================== Context ========================

const AuthContext = createContext<AuthContextValue | null>(null);

// ======================== Provider ========================

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [state, setState] = useState<AuthState>({
    user: null,
    isLoading: true,
    isAuthenticated: false,
  });

  // Check authentication on mount
  useEffect(() => {
    const token = getToken();
    if (token) {
      getCurrentUser()
        .then((user) => {
          setState({
            user,
            isLoading: false,
            isAuthenticated: true,
          });
        })
        .catch(() => {
          // Token invalid, clear it
          apiLogout();
          setState({
            user: null,
            isLoading: false,
            isAuthenticated: false,
          });
        });
    } else {
      setState({
        user: null,
        isLoading: false,
        isAuthenticated: false,
      });
    }
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    setState((prev) => ({ ...prev, isLoading: true }));
    try {
      const { user } = await apiLogin(username, password);
      setState({
        user,
        isLoading: false,
        isAuthenticated: true,
      });
    } catch (error) {
      setState((prev) => ({ ...prev, isLoading: false }));
      throw error;
    }
  }, []);

  const logout = useCallback(() => {
    apiLogout();
    setState({
      user: null,
      isLoading: false,
      isAuthenticated: false,
    });
  }, []);

  const refreshUser = useCallback(async () => {
    try {
      const user = await getCurrentUser();
      setState((prev) => ({
        ...prev,
        user,
        isAuthenticated: true,
      }));
    } catch {
      logout();
    }
  }, [logout]);

  const value: AuthContextValue = {
    ...state,
    login,
    logout,
    refreshUser,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// ======================== Hook ========================

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}

// ======================== Permission Helpers ========================

export function useIsAdmin(): boolean {
  const { user } = useAuth();
  return user?.roles.includes("admin") ?? false;
}

export function useHasRole(role: string): boolean {
  const { user } = useAuth();
  return user?.roles.includes(role) ?? false;
}

export function useHasAnyRole(...roles: string[]): boolean {
  const { user } = useAuth();
  return roles.some((role) => user?.roles.includes(role)) ?? false;
}
