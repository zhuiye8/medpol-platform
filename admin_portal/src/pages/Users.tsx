/**
 * User management page (admin only).
 */

import { useState } from "react";
import { useUsers } from "@/hooks/useUsers";
import { useAuth } from "@/context/AuthContext";
import type { UserInfo, CreateUserRequest, UpdateUserRequest } from "@/services/auth";

// Role display names
const ROLE_LABELS: Record<string, string> = {
  admin: "管理员",
  finance: "财务",
  viewer: "普通用户",
};

export default function UsersPage() {
  const { user: currentUser } = useAuth();
  const { users, roles, loading, error, refresh, create, update, remove } = useUsers();

  const [showModal, setShowModal] = useState(false);
  const [editingUser, setEditingUser] = useState<UserInfo | null>(null);
  const [formError, setFormError] = useState("");
  const [saving, setSaving] = useState(false);

  // Form state
  const [formData, setFormData] = useState({
    username: "",
    password: "",
    display_name: "",
    email: "",
    company_no: "",
    roles: ["viewer"] as string[],
  });

  const resetForm = () => {
    setFormData({
      username: "",
      password: "",
      display_name: "",
      email: "",
      company_no: "",
      roles: ["viewer"],
    });
    setEditingUser(null);
    setFormError("");
  };

  const openCreateModal = () => {
    resetForm();
    setShowModal(true);
  };

  const openEditModal = (user: UserInfo) => {
    setEditingUser(user);
    setFormData({
      username: user.username,
      password: "",
      display_name: user.display_name || "",
      email: user.email || "",
      company_no: user.company_no || "",
      roles: user.roles.length > 0 ? user.roles : ["viewer"],
    });
    setFormError("");
    setShowModal(true);
  };

  const handleSubmit = async () => {
    setFormError("");

    if (!editingUser && (!formData.username.trim() || !formData.password.trim())) {
      setFormError("用户名和密码必填");
      return;
    }

    setSaving(true);
    try {
      if (editingUser) {
        const updateData: UpdateUserRequest = {
          display_name: formData.display_name || undefined,
          email: formData.email || undefined,
          company_no: formData.company_no || undefined,
          roles: formData.roles,
        };
        await update(editingUser.id, updateData);
      } else {
        const createData: CreateUserRequest = {
          username: formData.username,
          password: formData.password,
          display_name: formData.display_name || undefined,
          email: formData.email || undefined,
          company_no: formData.company_no || undefined,
          roles: formData.roles,
        };
        await create(createData);
      }
      setShowModal(false);
      resetForm();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "操作失败");
    } finally {
      setSaving(false);
    }
  };

  const handleDisable = async (user: UserInfo) => {
    if (user.id === currentUser?.id) {
      alert("不能禁用自己");
      return;
    }
    if (!confirm(`确定要禁用用户 "${user.username}" 吗？`)) {
      return;
    }
    try {
      await remove(user.id);
    } catch (err) {
      alert(err instanceof Error ? err.message : "禁用失败");
    }
  };

  const handleToggleActive = async (user: UserInfo) => {
    if (user.id === currentUser?.id) {
      alert("不能修改自己的状态");
      return;
    }
    try {
      await update(user.id, { is_active: !user.is_active });
    } catch (err) {
      alert(err instanceof Error ? err.message : "操作失败");
    }
  };

  return (
    <div>
      <div className="page-header">
        <h1>用户管理</h1>
        <span style={{ color: "#64748b" }}>管理系统用户和权限</span>
      </div>

      <div className="toolbar">
        <button className="primary" onClick={openCreateModal}>
          新建用户
        </button>
        <button className="ghost" onClick={refresh}>
          刷新
        </button>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {loading ? (
        <div className="empty-state">加载中...</div>
      ) : users.length === 0 ? (
        <div className="empty-state">暂无用户</div>
      ) : (
        <div className="panel">
          <table className="list-table">
            <thead>
              <tr>
                <th>用户名</th>
                <th>显示名</th>
                <th>角色</th>
                <th>公司编号</th>
                <th>状态</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.id}>
                  <td>
                    <strong>{user.username}</strong>
                    {user.email && (
                      <div className="muted small">{user.email}</div>
                    )}
                  </td>
                  <td>{user.display_name || "-"}</td>
                  <td>
                    {user.roles.map((role) => (
                      <span
                        key={role}
                        className={`pill ${role === "admin" ? "pill--info" : ""}`}
                        style={{ marginRight: 4 }}
                      >
                        {ROLE_LABELS[role] || role}
                      </span>
                    ))}
                  </td>
                  <td>{user.company_no || "-"}</td>
                  <td>
                    <span className={`pill ${user.is_active ? "pill--ok" : "pill--warn"}`}>
                      {user.is_active ? "启用" : "禁用"}
                    </span>
                  </td>
                  <td className="table-actions">
                    <button className="link-btn" onClick={() => openEditModal(user)}>
                      编辑
                    </button>
                    {user.id !== currentUser?.id && (
                      <button
                        className="link-btn"
                        onClick={() => handleToggleActive(user)}
                      >
                        {user.is_active ? "禁用" : "启用"}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Create/Edit Modal */}
      {showModal && (
        <div className="modal-backdrop" onClick={() => setShowModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal__header">
              <h2 style={{ margin: 0 }}>{editingUser ? "编辑用户" : "新建用户"}</h2>
              <button className="ghost" onClick={() => setShowModal(false)}>
                关闭
              </button>
            </div>

            {formError && <div className="error-banner">{formError}</div>}

            <div className="form-grid">
              <label>
                <span>用户名 {!editingUser && "*"}</span>
                <input
                  type="text"
                  value={formData.username}
                  onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                  disabled={!!editingUser}
                  placeholder="登录用户名"
                />
              </label>

              {!editingUser && (
                <label>
                  <span>密码 *</span>
                  <input
                    type="password"
                    value={formData.password}
                    onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                    placeholder="设置密码"
                  />
                </label>
              )}

              <label>
                <span>显示名</span>
                <input
                  type="text"
                  value={formData.display_name}
                  onChange={(e) => setFormData({ ...formData, display_name: e.target.value })}
                  placeholder="显示名称"
                />
              </label>

              <label>
                <span>邮箱</span>
                <input
                  type="email"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  placeholder="邮箱地址"
                />
              </label>

              <label>
                <span>公司编号</span>
                <input
                  type="text"
                  value={formData.company_no}
                  onChange={(e) => setFormData({ ...formData, company_no: e.target.value })}
                  placeholder="所属公司编号"
                />
              </label>

              <label>
                <span>角色</span>
                <select
                  value={formData.roles[0] || "viewer"}
                  onChange={(e) => setFormData({ ...formData, roles: [e.target.value] })}
                >
                  {roles.map((role) => (
                    <option key={role.id} value={role.name}>
                      {ROLE_LABELS[role.name] || role.name}
                      {role.description ? ` - ${role.description}` : ""}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <div style={{ display: "flex", gap: 12, justifyContent: "flex-end", marginTop: 16 }}>
              <button className="ghost" onClick={() => setShowModal(false)}>
                取消
              </button>
              <button className="primary" onClick={handleSubmit} disabled={saving}>
                {saving ? "保存中..." : "保存"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
