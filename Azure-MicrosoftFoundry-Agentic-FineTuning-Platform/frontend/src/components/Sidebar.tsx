export type View = "home" | "discovery" | "finetune" | "comparison";

interface SidebarProps {
  active: View;
  onNavigate: (view: View) => void;
  username: string;
  onLogout: () => void;
  demoMode: string;
}

const NAV_ITEMS: { id: View; label: string; icon: string }[] = [
  { id: "home", label: "Home", icon: "🏠" },
];

const WORKFLOW_ITEMS: { id: View; label: string; icon: string }[] = [
  { id: "discovery", label: "Workflow 1 · Model Discovery", icon: "🔎" },
  { id: "finetune", label: "Workflow 2 · Fine-Tuning", icon: "🛠️" },
  { id: "comparison", label: "Workflow 3 · Agentic Comparison", icon: "⚖️" },
];

export default function Sidebar({ active, onNavigate, username, onLogout, demoMode }: SidebarProps) {
  return (
    <nav className="sidebar">
      <div className="sidebar-logo">
        <img src="/contoso.svg" alt="Contoso" />
        <span>Contoso Foundry</span>
      </div>

      <div className="sidebar-nav">
        {NAV_ITEMS.map((item) => (
          <button
            key={item.id}
            className={`sidebar-nav-item ${active === item.id ? "active" : ""}`}
            onClick={() => onNavigate(item.id)}
          >
            <span>{item.icon}</span>
            <span>{item.label}</span>
          </button>
        ))}
      </div>

      <div className="sidebar-section-label">Workflows</div>
      <div className="sidebar-nav">
        {WORKFLOW_ITEMS.map((item) => (
          <button
            key={item.id}
            className={`sidebar-nav-item ${active === item.id ? "active" : ""}`}
            onClick={() => onNavigate(item.id)}
          >
            <span>{item.icon}</span>
            <span>{item.label}</span>
          </button>
        ))}
      </div>

      <div className="sidebar-footer">
        <div style={{ marginBottom: 8 }}>
          Mode: <strong>{demoMode}</strong>
        </div>
        <div className="sidebar-user">
          <span>👤 {username}</span>
          <button className="sidebar-logout" onClick={onLogout}>
            Sign out
          </button>
        </div>
      </div>
    </nav>
  );
}
