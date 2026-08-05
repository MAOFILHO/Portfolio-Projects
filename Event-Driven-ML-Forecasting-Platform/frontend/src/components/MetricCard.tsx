interface MetricCardProps {
  label: string;
  rmse: number;
  mse: number;
}

export function MetricCard({ label, rmse, mse }: MetricCardProps) {
  return (
    <div className="card metric-card">
      <span className="label">{label}</span>
      <span className="value">{rmse.toFixed(2)}°C</span>
      <span className="sub">RMSE &middot; MSE {mse.toFixed(2)}</span>
    </div>
  );
}
