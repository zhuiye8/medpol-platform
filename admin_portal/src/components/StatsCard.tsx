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
      {description ? <div className="muted small">{description}</div> : null}
    </div>
  );
}
