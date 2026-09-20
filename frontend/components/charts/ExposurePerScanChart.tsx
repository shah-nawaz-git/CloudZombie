"use client";
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
import { historyChartData } from "@/lib/chart-data";
import type { HistoryPoint } from "@/lib/types";
export function ExposurePerScanChart({ points }: { points: HistoryPoint[] }) {
  const data = historyChartData(points);
  return (
    <div className="charts">
      <ResponsiveContainer>
        <LineChart data={data}>
          <CartesianGrid stroke="#252c35" />
          <XAxis dataKey="label" tick={{ fill: "#8b95a5", fontSize: 12 }} />
          <YAxis tick={{ fill: "#8b95a5", fontSize: 12 }} />
          <Tooltip
            contentStyle={{ background: "#181d23", border: "1px solid #354050" }}
            labelStyle={{ color: "#e6e9ee" }}
          />
          <Legend wrapperStyle={{ color: "#8b95a5" }} />
          <Line
            type="monotone"
            dataKey="estimated_exposure"
            name="Estimated exposure"
            stroke="#e0a83a"
            strokeWidth={2}
            dot={{ r: 2 }}
            isAnimationActive={false}
          />
          <Line
            type="monotone"
            dataKey="potential_exposure_low_confidence"
            name="Low-confidence potential"
            stroke="#8b95a5"
            strokeWidth={2}
            strokeDasharray="5 4"
            dot={{ r: 2 }}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
