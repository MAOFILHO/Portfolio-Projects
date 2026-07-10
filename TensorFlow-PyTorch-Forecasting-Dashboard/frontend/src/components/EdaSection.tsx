import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { MovingAveragesResponse, Point, SeasonalDecompositionResponse } from "../types";
import { ForecastChart } from "./ForecastChart";

interface EdaSectionProps {
  movingAverages: MovingAveragesResponse;
  seasonalDecomposition: SeasonalDecompositionResponse;
}

function MiniChart({
  title,
  data,
  color,
}: {
  title: string;
  data: Point[];
  color: string;
}) {
  return (
    <div className="card">
      <div className="chart-title">{title}</div>
      <ResponsiveContainer width="100%" height={180}>
        <LineChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--contoso-border)" />
          <XAxis dataKey="date" tick={{ fontSize: 10 }} minTickGap={60} />
          <YAxis tick={{ fontSize: 10 }} />
          <Tooltip />
          <Line
            type="monotone"
            dataKey="value"
            stroke={color}
            strokeWidth={1.75}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function EdaSection({ movingAverages, seasonalDecomposition }: EdaSectionProps) {
  return (
    <>
      <ForecastChart
        title="Moving Averages (12-Month vs 5-Year)"
        series={[
          { name: "12-Month MA", data: movingAverages.twelve_month, color: "#2e6fd9" },
          { name: "5-Year MA", data: movingAverages.five_year, color: "#ff8c00" },
        ]}
      />
      <div className="section-title">Seasonal Decomposition</div>
      <div className="eda-grid">
        <MiniChart title="Trend" data={seasonalDecomposition.trend} color="#1c8a4b" />
        <MiniChart title="Seasonal" data={seasonalDecomposition.seasonal} color="#0b2545" />
        <MiniChart title="Residual" data={seasonalDecomposition.residual} color="#c62828" />
      </div>
    </>
  );
}
