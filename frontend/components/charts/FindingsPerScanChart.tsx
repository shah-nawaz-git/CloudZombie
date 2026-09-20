"use client";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { historyChartData } from "@/lib/chart-data";
import type { HistoryPoint } from "@/lib/types";
export function FindingsPerScanChart({ points }: { points: HistoryPoint[] }) {
  const data = historyChartData(points);
  return (
    <div className="charts">
      <ResponsiveContainer>
        <BarChart data={data}>
          <CartesianGrid stroke="#252c35" />
          <XAxis dataKey="label" tick={{ fill: "#8b95a5", fontSize: 12 }} />
          <YAxis tick={{ fill: "#8b95a5", fontSize: 12 }} />
          <Tooltip
            contentStyle={{ background: "#181d23", border: "1px solid #354050" }}
            labelStyle={{ color: "#e6e9ee" }}
          />
          <Legend wrapperStyle={{ color: "#8b95a5" }} />
          <Bar
            stackId="findings"
            dataKey="ebs_volume"
            name="EBS volumes"
            fill="#e0a83a"
            isAnimationActive={false}
          />
          <Bar
            stackId="findings"
            dataKey="elastic_ip"
            name="Elastic IPs"
            fill="#58a6ff"
            isAnimationActive={false}
          />
          <Bar
            stackId="findings"
            dataKey="ec2_instance"
            name="EC2 instances"
            fill="#8b95a5"
            isAnimationActive={false}
          />
          <Bar
            stackId="findings"
            dataKey="ebs_snapshot"
            name="Snapshots"
            fill="#f85149"
            isAnimationActive={false}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
