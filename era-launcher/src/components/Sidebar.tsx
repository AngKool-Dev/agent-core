import type { Page, LaunchState } from "../types";

interface SidebarProps {
  currentPage: Page;
  onNavigate: (page: Page) => void;
  launchState: LaunchState;
}

const pages: { id: Page; label: string; icon: string }[] = [
  { id: "home", label: "Home", icon: "🏠" },
  { id: "instances", label: "Instances", icon: "📦" },
  { id: "mods", label: "Mods", icon: "🧩" },
  { id: "settings", label: "Settings", icon: "⚙️" },
  { id: "accounts", label: "Accounts", icon: "👤" },
];

export default function Sidebar({ currentPage, onNavigate, launchState }: SidebarProps) {
  const statusColor =
    launchState.status === "running"
      ? "#4ade80"
      : launchState.status === "launching"
        ? "#60a5fa"
        : launchState.status === "failed"
          ? "#f87171"
          : "#9ca3af";

  const statusLabel =
    launchState.status === "running"
      ? "● Running"
      : launchState.status === "launching"
        ? "● Launching..."
        : launchState.status === "failed"
          ? "● Failed"
          : "● Ready";

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <h1 className="logo">EraLauncher</h1>
        <span className="version">v0.1.0</span>
      </div>
      <nav className="nav">
        {pages.map((p) => (
          <button
            key={p.id}
            className={`nav-item ${currentPage === p.id ? "active" : ""}`}
            onClick={() => onNavigate(p.id)}
          >
            <span className="nav-icon">{p.icon}</span>
            <span className="nav-label">{p.label}</span>
          </button>
        ))}
      </nav>
      <div className="sidebar-footer">
        <span className="status" style={{ color: statusColor }}>
          {statusLabel}
        </span>
      </div>
    </aside>
  );
}
