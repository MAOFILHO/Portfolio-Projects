export type PageId = "capture" | "profile" | "settings" | "observability" | "audit" | "agents";

const NAV_ITEMS: { id: PageId; label: string }[] = [
  { id: "capture", label: "Capture" },
  { id: "profile", label: "Profile" },
  { id: "settings", label: "Settings" },
  { id: "observability", label: "Observability" },
  { id: "agents", label: "AI Agents" },
  { id: "audit", label: "Audit Trail" },
];

interface TopNavProps {
  activePage: PageId;
  onNavigate: (page: PageId) => void;
}

export function TopNav({ activePage, onNavigate }: TopNavProps) {
  return (
    <nav className="top-nav">
      {NAV_ITEMS.map((item) => (
        <button
          key={item.id}
          className={activePage === item.id ? "top-nav-item active" : "top-nav-item"}
          onClick={() => onNavigate(item.id)}
        >
          {item.label}
        </button>
      ))}
    </nav>
  );
}
