"use client";

import React from "react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  LineChart,
  Line,
  AreaChart,
  Area,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";
import { ChartConfig, QueryDataRow } from "../../types/chat";

interface DataChartProps {
  config: ChartConfig;
  data: QueryDataRow[];
}

const PALETTE = [
  "#FEC50B", // Primary Golden Yellow
  "#38BDF8", // Sky Blue
  "#818CF8", // Indigo
  "#34D399", // Emerald
  "#FB7185", // Rose
  "#FB923C", // Amber
  "#C084FC", // Purple
  "#2DD4BF", // Teal
];

// Helper to format values for currency vs regular numbers
const formatValue = (val: any, keyName: string = ""): string => {
  if (typeof val !== "number") return String(val ?? "");

  const k = keyName.toLowerCase();
  const isCurrency =
    k.includes("revenue") ||
    k.includes("spend") ||
    k.includes("price") ||
    k.includes("amount") ||
    k.includes("cost") ||
    k.includes("refund") ||
    k.includes("discount");

  if (!isCurrency) {
    return val.toLocaleString("en-IN");
  }

  if (Math.abs(val) >= 10000000) {
    return `₹${(val / 10000000).toFixed(2)} Cr`;
  }
  if (Math.abs(val) >= 100000) {
    return `₹${(val / 100000).toFixed(2)} L`;
  }
  return `₹${val.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
};

// Compact Axis Label Formatter
const formatAxisValue = (val: any): string => {
  if (typeof val !== "number") {
    const s = String(val ?? "");
    return s.length > 14 ? `${s.slice(0, 12)}...` : s;
  }
  if (Math.abs(val) >= 10000000) return `₹${(val / 10000000).toFixed(1)}Cr`;
  if (Math.abs(val) >= 100000) return `₹${(val / 100000).toFixed(0)}L`;
  if (Math.abs(val) >= 1000) return `₹${(val / 1000).toFixed(0)}k`;
  return String(val);
};

// Custom Dark Tooltip
const CustomTooltip = ({ active, payload, label, yKey }: any) => {
  if (active && payload && payload.length) {
    const item = payload[0];
    const rawVal = item.value;
    const name = label || item.name || item.payload?.name || "";

    return (
      <div className="bg-[#1E222B] border border-[#323849] rounded-xl px-3.5 py-2.5 shadow-xl text-xs backdrop-blur-md">
        <div className="text-[#94A3B8] font-medium mb-1 truncate max-w-[220px]">
          {name}
        </div>
        <div className="text-white font-semibold font-mono text-[13px] flex items-center gap-1.5">
          <span
            className="w-2 h-2 rounded-full inline-block"
            style={{ backgroundColor: item.color || "#FEC50B" }}
          />
          <span>{formatValue(rawVal, yKey || item.dataKey)}</span>
        </div>
      </div>
    );
  }
  return null;
};

export const DataChart: React.FC<DataChartProps> = ({ config, data }) => {
  if (!data || data.length === 0) return null;

  const type = config.type || "bar";
  const xKey = config.x_key || Object.keys(data[0])[0];
  const yKey =
    config.y_key ||
    Object.keys(data[0]).find(
      (k) => typeof data[0][k] === "number" && k !== xKey
    ) ||
    Object.keys(data[0])[1];

  // Limit chart data points for visual cleanliness
  const chartData = data.slice(0, 15);

  return (
    <div className="w-full bg-[#181A20] border border-[#2E3444] rounded-xl p-4 mt-2 select-none">
      {config.title && (
        <div className="text-xs font-semibold text-[#CBD5E1] tracking-wide mb-3 flex items-center justify-between">
          <span>{config.title}</span>
          <span className="text-[10px] text-[#94A3B8] font-mono uppercase">
            {type} chart
          </span>
        </div>
      )}

      <div className="w-full h-56">
        <ResponsiveContainer width="100%" height="100%">
          {type === "donut" ? (
            <PieChart>
              <Tooltip
                content={<CustomTooltip yKey={yKey} />}
                cursor={{ fill: "rgba(254, 197, 11, 0.05)" }}
              />
              <Pie
                data={chartData}
                dataKey={yKey}
                nameKey={xKey}
                cx="50%"
                cy="50%"
                innerRadius={50}
                outerRadius={80}
                paddingAngle={3}
                stroke="#181A20"
                strokeWidth={2}
              >
                {chartData.map((_, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={PALETTE[index % PALETTE.length]}
                  />
                ))}
              </Pie>
            </PieChart>
          ) : type === "line" ? (
            <LineChart
              data={chartData}
              margin={{ top: 10, right: 10, left: -10, bottom: 5 }}
            >
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="#2E3444"
                vertical={false}
              />
              <XAxis
                dataKey={xKey}
                stroke="#94A3B8"
                fontSize={11}
                tickLine={false}
                axisLine={{ stroke: "#2E3444" }}
                tickFormatter={formatAxisValue}
              />
              <YAxis
                stroke="#94A3B8"
                fontSize={11}
                tickLine={false}
                axisLine={{ stroke: "#2E3444" }}
                tickFormatter={formatAxisValue}
              />
              <Tooltip
                content={<CustomTooltip yKey={yKey} />}
                cursor={{ stroke: "#FEC50B", strokeWidth: 1, strokeDasharray: "4 4" }}
              />
              <Line
                type="monotone"
                dataKey={yKey}
                stroke="#FEC50B"
                strokeWidth={2.5}
                dot={{ fill: "#FEC50B", strokeWidth: 0, r: 3.5 }}
                activeDot={{ r: 6, fill: "#FFFFFF", stroke: "#FEC50B", strokeWidth: 2 }}
              />
            </LineChart>
          ) : type === "area" ? (
            <AreaChart
              data={chartData}
              margin={{ top: 10, right: 10, left: -10, bottom: 5 }}
            >
              <defs>
                <linearGradient id="areaGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#FEC50B" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="#FEC50B" stopOpacity={0.0} />
                </linearGradient>
              </defs>
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="#2E3444"
                vertical={false}
              />
              <XAxis
                dataKey={xKey}
                stroke="#94A3B8"
                fontSize={11}
                tickLine={false}
                axisLine={{ stroke: "#2E3444" }}
                tickFormatter={formatAxisValue}
              />
              <YAxis
                stroke="#94A3B8"
                fontSize={11}
                tickLine={false}
                axisLine={{ stroke: "#2E3444" }}
                tickFormatter={formatAxisValue}
              />
              <Tooltip
                content={<CustomTooltip yKey={yKey} />}
                cursor={{ stroke: "#FEC50B", strokeWidth: 1, strokeDasharray: "4 4" }}
              />
              <Area
                type="monotone"
                dataKey={yKey}
                stroke="#FEC50B"
                strokeWidth={2.5}
                fillOpacity={1}
                fill="url(#areaGradient)"
              />
            </AreaChart>
          ) : (
            <BarChart
              data={chartData}
              margin={{ top: 10, right: 10, left: -10, bottom: 5 }}
            >
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="#2E3444"
                vertical={false}
              />
              <XAxis
                dataKey={xKey}
                stroke="#94A3B8"
                fontSize={11}
                tickLine={false}
                axisLine={{ stroke: "#2E3444" }}
                tickFormatter={formatAxisValue}
              />
              <YAxis
                stroke="#94A3B8"
                fontSize={11}
                tickLine={false}
                axisLine={{ stroke: "#2E3444" }}
                tickFormatter={formatAxisValue}
              />
              <Tooltip
                content={<CustomTooltip yKey={yKey} />}
                cursor={{ fill: "rgba(254, 197, 11, 0.06)" }}
              />
              <Bar
                dataKey={yKey}
                fill="#FEC50B"
                radius={[4, 4, 0, 0]}
                maxBarSize={48}
              >
                {chartData.map((_, index) => (
                  <Cell
                    key={`bar-${index}`}
                    fill={index === 0 ? "#FEC50B" : "#F4B900"}
                  />
                ))}
              </Bar>
            </BarChart>
          )}
        </ResponsiveContainer>
      </div>
    </div>
  );
};
