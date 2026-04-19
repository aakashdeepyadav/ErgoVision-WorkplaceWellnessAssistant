import { Area, AreaChart, ResponsiveContainer, YAxis } from "recharts";

export default function SparklineChart({
  data,
  dataKey,
  color,
  gradientId,
  height = 90,
  yDomain = [0, "auto"],
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data}>
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor={color} stopOpacity={0.35} />
            <stop offset="95%" stopColor={color} stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <Area
          type="monotone"
          dataKey={dataKey}
          stroke={color}
          fill={`url(#${gradientId})`}
          strokeWidth={2}
          dot={false}
        />
        <YAxis hide domain={yDomain} />
      </AreaChart>
    </ResponsiveContainer>
  );
}
