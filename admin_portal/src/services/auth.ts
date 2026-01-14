/**
 * Authentication API service
 */

const DEFAULT_BASE = "http://localhost:8000";
const API_BASE_URL = (import.meta.env.VITE_API_BASE || DEFAULT_BASE).replace(/\/$/, "");

// Token storage key
const TOKEN_KEY = "auth_token";

// ======================== Types ========================

export interface UserInfo {
  id: string;
  username: string;
  display_name?: string;
  email?: string;
  company_no?: string;
  roles: string[];
  is_active: boolean;
}

export interface LoginResponse {
  code: number;
  message: string;
  data?: {
    token: string;
    user: UserInfo;
  };
}

export interface UsersResponse {
  code: number;
  message: string;
  data?: {
    users: UserInfo[];
  };
}

export interface RolesResponse {
  code: number;
  message: string;
  data?: {
    roles: Array<{
      id: string;
      name: string;
      description?: string;
    }>;
  };
}

export interface CreateUserRequest {
  username: string;
  password: string;
  display_name?: string;
  email?: string;
  company_no?: string;
  roles?: string[];
}

export interface UpdateUserRequest {
  display_name?: string;
  email?: string;
  company_no?: string;
  roles?: string[];
  is_active?: boolean;
}

// ======================== Token Management ========================

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function removeToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

// ======================== API Helpers ========================

async function authRequest<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.detail || data.message || `请求失败: ${response.status}`);
  }

  return data as T;
}

// ======================== Auth API ========================

export async function login(
  username: string,
  password: string
): Promise<{ token: string; user: UserInfo }> {
  const response = await authRequest<LoginResponse>("/v1/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });

  if (response.code !== 0 || !response.data) {
    throw new Error(response.message || "登录失败");
  }

  const { token, user } = response.data;
  setToken(token);
  return { token, user };
}

export async function getCurrentUser(): Promise<UserInfo> {
  const response = await authRequest<{
    code: number;
    message: string;
    data?: { user: UserInfo };
  }>("/v1/auth/me");

  if (response.code !== 0 || !response.data) {
    throw new Error(response.message || "获取用户信息失败");
  }

  return response.data.user;
}

export function logout(): void {
  removeToken();
}

// ======================== User Management API ========================

export async function getUsers(): Promise<UserInfo[]> {
  const response = await authRequest<UsersResponse>("/v1/auth/users");

  if (response.code !== 0 || !response.data) {
    throw new Error(response.message || "获取用户列表失败");
  }

  return response.data.users;
}

export async function getRoles(): Promise<
  Array<{ id: string; name: string; description?: string }>
> {
  const response = await authRequest<RolesResponse>("/v1/auth/roles");

  if (response.code !== 0 || !response.data) {
    throw new Error(response.message || "获取角色列表失败");
  }

  return response.data.roles;
}

export async function createUser(data: CreateUserRequest): Promise<UserInfo> {
  const response = await authRequest<{
    code: number;
    message: string;
    data?: { user: UserInfo };
  }>("/v1/auth/users", {
    method: "POST",
    body: JSON.stringify(data),
  });

  if (response.code !== 0 || !response.data) {
    throw new Error(response.message || "创建用户失败");
  }

  return response.data.user;
}

export async function updateUser(
  userId: string,
  data: UpdateUserRequest
): Promise<UserInfo> {
  const response = await authRequest<{
    code: number;
    message: string;
    data?: { user: UserInfo };
  }>(`/v1/auth/users/${userId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });

  if (response.code !== 0 || !response.data) {
    throw new Error(response.message || "更新用户失败");
  }

  return response.data.user;
}

export async function deleteUser(userId: string): Promise<void> {
  const response = await authRequest<{
    code: number;
    message: string;
  }>(`/v1/auth/users/${userId}`, {
    method: "DELETE",
  });

  if (response.code !== 0) {
    throw new Error(response.message || "删除用户失败");
  }
}
