import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Point } from "../types";

interface Series {
  name: string;
  data: Point[];
  color: string;
  dashed?: boolean;
}

interface ForecastChartProps {
  title: string;
  series: Series[];
  observedSince?: string;
}

interface ChartRow {
  date: string;
  [seriesName: string]: string | number | undefined;
}

function mergeSeries(series: Series[], observedSince?: string): ChartRow[] {
  const rows = new Map<string, ChartRow>();

  for (const s of series) {
    for (const point of s.data) {
      if (observedSince && s.name === "Observed" && point.date < observedSince) {
        continue;
      }
      const row = rows.get(point.date) ?? { date: point.date };
      row[s.name] = point.value;
      rows.set(point.date, row);
    }
  }

  return Array.from(rows.values()).sort((a, b) => a.date.localeCompare(b.date));
}

export function ForecastChart({ title, series, observedSince }: ForecastChartProps) {
  const data = mergeSeries(series, observedSince);

  return (
    <div className="card chart-card">
      <div className="chart-title">{title}</div>
      <ResponsiveContainer width="100%" height={340}>
        <LineChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--contoso-border)" />
          <XAxis dataKey="date" tick={{ fontSize: 11 }} minTickGap={40} />
          <YAxis
            tick={{ fontSize: 11 }}
            label={{ value: "°C", angle: -90, position: "insideLeft", fontSize: 11 }}
          />
          <Tooltip />
          <Legend />
          {series.map((s) => (
            <Line
              key={s.name}
              type="monotone"
              dataKey={s.name}
              stroke={s.color}
              strokeWidth={2}
              strokeDasharray={s.dashed ? "6 4" : undefined}
              dot={false}
              connectNulls
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
