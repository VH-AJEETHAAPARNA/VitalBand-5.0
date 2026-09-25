// src/components/VitalsChart.tsx – interactive Recharts dual-axis line chart for Heart Rate & SpO2
import React from "react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ReferenceLine,
} from "recharts";
import type { VitalsReading } from "../lib/types";

interface VitalsChartProps {
  data: VitalsReading[];
}

export function VitalsChart({ data }: VitalsChartProps) {
  if (!data || data.length === 0) {
    return (
      <div className="flex items-center justify-center h-64 bg-gray-50 border rounded-lg text-gray-400 text-sm">
        No historical readings yet. Stream data from the wrist patch simulator.
      </div>
    );
  }

  // Format timestamp for display
  const chartData = data.map((d, index) => {
    const timeStr = d.timestamp
      ? new Date(d.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })
      : `#${index + 1}`;
    return {
      time: timeStr,
      heartRate: d.heart_rate ?? null,
      spo2: d.spo2 ?? null,
    };
  });

  return (
    <div className="w-full h-72">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis dataKey="time" tick={{ fontSize: 11 }} stroke="#6b7280" />
          
          {/* Left Y Axis: Heart Rate (BPM) */}
          <YAxis
            yAxisId="hr"
            domain={[40, 160]}
            tick={{ fontSize: 11, fill: "#dc2626" }}
            stroke="#dc2626"
            label={{ value: "HR (BPM)", angle: -90, position: "insideLeft", fill: "#dc2626", fontSize: 12 }}
          />

          {/* Right Y Axis: SpO2 (%) */}
          <YAxis
            yAxisId="spo2"
            orientation="right"
            domain={[70, 100]}
            tick={{ fontSize: 11, fill: "#2563eb" }}
            stroke="#2563eb"
            label={{ value: "SpO2 (%)", angle: 90, position: "insideRight", fill: "#2563eb", fontSize: 12 }}
          />

          <Tooltip
            contentStyle={{ backgroundColor: "#ffffff", borderRadius: "8px", border: "1px solid #e5e7eb" }}
            formatter={(value: any, name: string) => [
              value !== null ? `${value}${name === "SpO2" ? "%" : " BPM"}` : "--",
              name,
            ]}
          />
          <Legend verticalAlign="top" height={36} />

          {/* Clinical Threshold Guides */}
          <ReferenceLine yAxisId="hr" y={120} stroke="#f87171" strokeDasharray="4 4" label={{ value: "HR High (120)", fill: "#f87171", fontSize: 10 }} />
          <ReferenceLine yAxisId="hr" y={50} stroke="#f87171" strokeDasharray="4 4" label={{ value: "HR Low (50)", fill: "#f87171", fontSize: 10 }} />
          <ReferenceLine yAxisId="spo2" y={92} stroke="#60a5fa" strokeDasharray="4 4" label={{ value: "SpO2 Low (92%)", fill: "#60a5fa", fontSize: 10 }} />

          {/* Lines */}
          <Line
            yAxisId="hr"
            type="monotone"
            dataKey="heartRate"
            name="Heart Rate"
            stroke="#dc2626"
            strokeWidth={2}
            dot={{ r: 3, fill: "#dc2626" }}
            activeDot={{ r: 5 }}
            isAnimationActive={false}
          />
          <Line
            yAxisId="spo2"
            type="monotone"
            dataKey="spo2"
            name="SpO2"
            stroke="#2563eb"
            strokeWidth={2}
            dot={{ r: 3, fill: "#2563eb" }}
            activeDot={{ r: 5 }}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
