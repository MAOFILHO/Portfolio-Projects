interface SeverityBadgeProps {
  severity: string | null | undefined;
}

const LABELS: Record<string, string> = {
  critical: "Critical",
  high: "High",
  medium: "Medium",
  low: "Low",
};

export function SeverityBadge({ severity }: SeverityBadgeProps) {
  const normalized = (severity || "").toLowerCase();
  if (!normalized || !LABELS[normalized]) {
    return <span className="severity-badge severity-unknown">-</span>;
  }
  return <span className={`severity-badge severity-${normalized}`}>{LABELS[normalized]}</span>;
}
