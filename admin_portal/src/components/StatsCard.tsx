interface StatsCardProps {
  label: string;
  value: string | number;
  description?: string;
}

export function StatsCard({ label, value, description }: StatsCardProps) {
  return (
    <div className="stats-card">
      <div className="stats-card__label">{label}</div>
      <div className="stats-card__value">{value}</div>
      {description ? <div style={{ color: "#94a3b8", marginTop: 4 }}>{description}</div> : null}
    </div>
  );
}
