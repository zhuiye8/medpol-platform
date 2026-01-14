/**
 * Hook for user management operations.
 */

import { useCallback, useEffect, useState } from "react";
import {
  getUsers,
  getRoles,
  createUser,
  updateUser,
  deleteUser,
  type UserInfo,
  type CreateUserRequest,
  type UpdateUserRequest,
} from "@/services/auth";

interface Role {
  id: string;
  name: string;
  description?: string;
}

interface UseUsersResult {
  users: UserInfo[];
  roles: Role[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  create: (data: CreateUserRequest) => Promise<UserInfo>;
  update: (userId: string, data: UpdateUserRequest) => Promise<UserInfo>;
  remove: (userId: string) => Promise<void>;
}

export function useUsers(): UseUsersResult {
  const [users, setUsers] = useState<UserInfo[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [usersData, rolesData] = await Promise.all([getUsers(), getRoles()]);
      setUsers(usersData);
      setRoles(rolesData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const create = useCallback(
    async (data: CreateUserRequest): Promise<UserInfo> => {
      const user = await createUser(data);
      setUsers((prev) => [...prev, user]);
      return user;
    },
    []
  );

  const update = useCallback(
    async (userId: string, data: UpdateUserRequest): Promise<UserInfo> => {
      const user = await updateUser(userId, data);
      setUsers((prev) => prev.map((u) => (u.id === userId ? user : u)));
      return user;
    },
    []
  );

  const remove = useCallback(
    async (userId: string): Promise<void> => {
      await deleteUser(userId);
      // Update local state - mark as inactive
      setUsers((prev) =>
        prev.map((u) => (u.id === userId ? { ...u, is_active: false } : u))
      );
    },
    []
  );

  return {
    users,
    roles,
    loading,
    error,
    refresh: fetchData,
    create,
    update,
    remove,
  };
}
