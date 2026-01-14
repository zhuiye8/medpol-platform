/**
 * 角色展示页面 - 展示系统角色及其 AI 对话权限
 */

// 角色权限定义（与后端 Roles 类保持一致）
const ROLES_DATA = [
  {
    name: "admin",
    label: "管理员",
    description: "系统管理员，拥有全部权限",
    permissions: {
      finance: true,
      employeeFull: true,
      employeeBasic: true,
      policySearch: true,
    },
    usage: "移动端 hybrid 模式",
  },
  {
    name: "finance",
    label: "财务人员",
    description: "仅可查询财务数据",
    permissions: {
      finance: true,
      employeeFull: false,
      employeeBasic: false,
      policySearch: false,
    },
    usage: "移动端 sql 模式",
  },
  {
    name: "viewer",
    label: "普通用户",
    description: "可查询政策和员工基础信息",
    permissions: {
      finance: false,
      employeeFull: false,
      employeeBasic: true,
      policySearch: true,
    },
    usage: "移动端 rag 模式、PC 对话",
  },
];

const PERMISSION_LABELS = {
  finance: "财务查询",
  employeeFull: "员工全字段",
  employeeBasic: "员工基础",
  policySearch: "政策检索",
};

function PermissionBadge({ allowed }: { allowed: boolean }) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        width: 24,
        height: 24,
        borderRadius: "50%",
        backgroundColor: allowed ? "rgba(16, 185, 129, 0.15)" : "rgba(148, 163, 184, 0.15)",
        color: allowed ? "#047857" : "#94a3b8",
        fontSize: 14,
      }}
    >
      {allowed ? "✓" : "✗"}
    </span>
  );
}

export default function RolesPage() {
  return (
    <div>
      <div className="page-header">
        <h1>角色管理</h1>
        <span style={{ color: "#64748b" }}>查看系统角色及其 AI 对话权限</span>
      </div>

      <div className="panel">
        <table className="list-table">
          <thead>
            <tr>
              <th>角色</th>
              <th>描述</th>
              <th style={{ textAlign: "center" }}>{PERMISSION_LABELS.finance}</th>
              <th style={{ textAlign: "center" }}>{PERMISSION_LABELS.employeeFull}</th>
              <th style={{ textAlign: "center" }}>{PERMISSION_LABELS.employeeBasic}</th>
              <th style={{ textAlign: "center" }}>{PERMISSION_LABELS.policySearch}</th>
              <th>使用场景</th>
            </tr>
          </thead>
          <tbody>
            {ROLES_DATA.map((role) => (
              <tr key={role.name}>
                <td>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span
                      className={`pill ${role.name === "admin" ? "pill--info" : ""}`}
                    >
                      {role.label}
                    </span>
                    <span className="muted small">{role.name}</span>
                  </div>
                </td>
                <td>{role.description}</td>
                <td style={{ textAlign: "center" }}>
                  <PermissionBadge allowed={role.permissions.finance} />
                </td>
                <td style={{ textAlign: "center" }}>
                  <PermissionBadge allowed={role.permissions.employeeFull} />
                </td>
                <td style={{ textAlign: "center" }}>
                  <PermissionBadge allowed={role.permissions.employeeBasic} />
                </td>
                <td style={{ textAlign: "center" }}>
                  <PermissionBadge allowed={role.permissions.policySearch} />
                </td>
                <td>
                  <span className="muted small">{role.usage}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="panel" style={{ marginTop: 24 }}>
        <h3 style={{ margin: "0 0 12px 0" }}>权限说明</h3>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 16 }}>
          <div className="stat-card">
            <div className="stat-card__label">财务查询</div>
            <p style={{ margin: "8px 0 0", fontSize: 13, color: "#475569" }}>
              查询财务报表数据，包括营业收入、利润、资产负债等
            </p>
          </div>
          <div className="stat-card">
            <div className="stat-card__label">员工全字段</div>
            <p style={{ margin: "8px 0 0", fontSize: 13, color: "#475569" }}>
              查询员工所有信息，包括身份证号、手机号等敏感字段
            </p>
          </div>
          <div className="stat-card">
            <div className="stat-card__label">员工基础</div>
            <p style={{ margin: "8px 0 0", fontSize: 13, color: "#475569" }}>
              查询员工基础信息，如姓名、部门、职位、学历等（不含敏感字段）
            </p>
          </div>
          <div className="stat-card">
            <div className="stat-card__label">政策检索</div>
            <p style={{ margin: "8px 0 0", fontSize: 13, color: "#475569" }}>
              检索医药政策文档，支持语义搜索和问答
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
