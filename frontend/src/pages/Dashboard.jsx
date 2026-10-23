import React, { useEffect, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import Layout from "../components/Layout";
import SeverityBadge from "../components/SeverityBadge";
import ConfidenceMeter from "../components/ConfidenceMeter";
import {
    BarChart,
    Bar,
    XAxis,
    YAxis,
    Tooltip,
    ResponsiveContainer,
    PieChart,
    Pie,
    Cell,
} from "recharts";
import {
    ArrowUpRight,
    Database,
    ShieldAlert,
    Radio,
    MapPin,
    Activity,
} from "lucide-react";

const SEV_COLORS = {
    high: "#DC2626",
    medium: "#D97706",
    low: "#2563EB",
    unknown: "#64748B",
};

export default function Dashboard() {
    const [stats, setStats] = useState(null);
    const [alerts, setAlerts] = useState([]);
    const [recentRecalls, setRecentRecalls] = useState([]);

    const fetchDashboardData = useCallback(async () => {
        try {
            const [s, a, r] = await Promise.all([
                api.get("/stats/ingestion").then((x) => x.data),
                api.get("/alerts?limit=5").then((x) => x.data),
                api.get("/recalls?limit=6").then((x) => x.data),
            ]);
            setStats(s);
            setAlerts(a.items || []);
            setRecentRecalls(r.items || []);
        } catch (err) {
            console.error("Dashboard fetch error:", err);
        }
    }, []);

    useEffect(() => {
        fetchDashboardData();
        const handleFocus = () => {
            fetchDashboardData();
        };
        window.addEventListener("focus", handleFocus);
        return () => window.removeEventListener("focus", handleFocus);
    }, [fetchDashboardData]);

    const severityData = stats
        ? Object.entries(stats.severity || {}).map(([k, v]) => ({
              name: k,
              value: v,
              color: SEV_COLORS[k] || "#64748B",
          }))
        : [];

    const sourceData = stats
        ? Object.entries(stats.source || {})
              .map(([k, v]) => ({ name: k, value: v }))
              .sort((a, b) => b.value - a.value)
        : [];

    const confData = stats
        ? Object.entries(stats.confidence_buckets || {}).map(([k, v]) => ({
              name: k,
              value: v,
          }))
        : [];

    return (
        <Layout>
            {/* Header */}
            <div
                className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 mb-8"
                data-testid="dashboard-header"
            >
                <div>
                    <div className="flex items-center gap-2 mb-1.5">
                        <span className="h-2 w-2 rounded-full bg-red-600 pulse-dot" />
                        <p className="font-mono text-[11px] uppercase tracking-widest text-slate-500">
                            Global Regulatory Intel
                        </p>
                    </div>
                    <h2 className="font-display font-black tracking-tight text-3xl sm:text-4xl text-slate-950">
                        Recall Signal Intelligence
                    </h2>
                </div>
                <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-lg border border-[#DCE4EF] bg-white text-xs font-mono text-slate-600 shadow-2xs self-start sm:self-auto">
                    <span className="h-2 w-2 rounded-full bg-emerald-500" />
                    <span>
                        {stats
                            ? `${stats.total_normalized.toLocaleString()} normalized records`
                            : "Loading signals..."}
                    </span>
                </div>
            </div>

            {/* Metrics grid */}
            <div
                className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-5 mb-8"
                data-testid="metrics-grid"
            >
                <MetricCard
                    label="Total recalls"
                    value={stats?.total_normalized?.toLocaleString() || "—"}
                    sub="normalized across all feeds"
                    icon={Database}
                    iconColor="text-slate-700 bg-slate-100"
                    testid="metric-total-recalls"
                />
                <MetricCard
                    label="High severity"
                    value={stats?.severity?.high?.toLocaleString() || "0"}
                    sub="toxic · contamination · critical"
                    accent="text-red-600"
                    icon={ShieldAlert}
                    iconColor="text-red-600 bg-red-50"
                    testid="metric-high-severity"
                />
                <MetricCard
                    label="Sources"
                    value={stats ? Object.keys(stats.source || {}).length : "—"}
                    sub="active regulatory feeds"
                    icon={Radio}
                    iconColor="text-blue-600 bg-blue-50"
                    testid="metric-sources"
                />
                <MetricCard
                    label="Regions"
                    value={stats ? Object.keys(stats.region || {}).length : "—"}
                    sub="global jurisdictions tracked"
                    icon={MapPin}
                    iconColor="text-emerald-600 bg-emerald-50"
                    testid="metric-regions"
                />
            </div>

            <div className="grid grid-cols-12 gap-6 mb-8">
                {/* Severity Mix Donut Chart */}
                <div className="col-span-12 lg:col-span-4 bg-white border border-[#DCE4EF] rounded-xl p-5 shadow-2xs flex flex-col justify-between">
                    <div>
                        <div className="flex items-center justify-between mb-3">
                            <p className="font-mono text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                                Severity Mix
                            </p>
                            <span className="font-mono text-[10px] text-slate-400">CHART 01</span>
                        </div>
                        <div className="relative h-52 flex items-center justify-center">
                            <ResponsiveContainer width="100%" height="100%">
                                <PieChart>
                                    <Pie
                                        data={severityData}
                                        innerRadius={46}
                                        outerRadius={72}
                                        paddingAngle={2}
                                        dataKey="value"
                                        stroke="#FFFFFF"
                                        strokeWidth={2}
                                    >
                                        {severityData.map((d, i) => (
                                            <Cell key={i} fill={d.color} />
                                        ))}
                                    </Pie>
                                    <Tooltip
                                        contentStyle={{
                                            backgroundColor: "#FFFFFF",
                                            border: "1px solid #DCE4EF",
                                            borderRadius: "8px",
                                            boxShadow: "0 2px 4px rgba(0,0,0,0.04)",
                                            fontFamily: "IBM Plex Mono",
                                            fontSize: "11px",
                                        }}
                                    />
                                </PieChart>
                            </ResponsiveContainer>
                            {/* Centered Total Recall Counter */}
                            <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                                <span className="text-xl font-display font-bold text-slate-900">
                                    {stats?.total_normalized?.toLocaleString() || "0"}
                                </span>
                                <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400">
                                    Total
                                </span>
                            </div>
                        </div>
                    </div>
                    <ul className="space-y-1.5 mt-4 pt-3 border-t border-[#DCE4EF]">
                        {severityData.map((d) => (
                            <li key={d.name} className="flex items-center justify-between text-xs">
                                <span className="flex items-center gap-2">
                                    <span
                                        className="h-2 w-2 rounded-full block"
                                        style={{ background: d.color }}
                                    />
                                    <span className="font-mono uppercase text-slate-700">
                                        {d.name}
                                    </span>
                                </span>
                                <span className="font-mono tabular text-slate-600 font-medium">
                                    {d.value.toLocaleString()}
                                </span>
                            </li>
                        ))}
                    </ul>
                </div>

                {/* Records per Source (Horizontal Bar Chart) */}
                <div className="col-span-12 lg:col-span-4 bg-white border border-[#DCE4EF] rounded-xl p-5 shadow-2xs flex flex-col justify-between">
                    <div>
                        <div className="flex items-center justify-between mb-3">
                            <p className="font-mono text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                                Records per Source
                            </p>
                            <span className="font-mono text-[10px] text-slate-400">CHART 02</span>
                        </div>
                        <div className="h-64">
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart
                                    layout="vertical"
                                    data={sourceData}
                                    margin={{ top: 5, right: 30, left: 10, bottom: 5 }}
                                >
                                    <XAxis
                                        type="number"
                                        tick={{
                                            fontSize: 10,
                                            fill: "#64748B",
                                            fontFamily: "IBM Plex Mono",
                                        }}
                                        tickLine={false}
                                        axisLine={{ stroke: "#E2E8F0" }}
                                    />
                                    <YAxis
                                        type="category"
                                        dataKey="name"
                                        width={110}
                                        tick={{
                                            fontSize: 10,
                                            fill: "#334155",
                                            fontFamily: "IBM Plex Mono",
                                        }}
                                        tickLine={false}
                                        axisLine={{ stroke: "#E2E8F0" }}
                                    />
                                    <Tooltip
                                        contentStyle={{
                                            backgroundColor: "#FFFFFF",
                                            border: "1px solid #DCE4EF",
                                            borderRadius: "8px",
                                            boxShadow: "0 2px 4px rgba(0,0,0,0.04)",
                                            fontFamily: "IBM Plex Mono",
                                            fontSize: "11px",
                                        }}
                                    />
                                    <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                                        {sourceData.map((entry, idx) => (
                                            <Cell
                                                key={idx}
                                                fill={idx === 0 ? "#DC2626" : "#475569"}
                                            />
                                        ))}
                                    </Bar>
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                    <p className="text-[11px] font-mono text-slate-400 mt-2 text-right">
                        Dominant: {sourceData[0]?.name || "None"}
                    </p>
                </div>

                {/* Confidence Distribution Chart */}
                <div className="col-span-12 lg:col-span-4 bg-white border border-[#DCE4EF] rounded-xl p-5 shadow-2xs flex flex-col justify-between">
                    <div>
                        <div className="flex items-center justify-between mb-3">
                            <p className="font-mono text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                                Confidence Distribution
                            </p>
                            <span className="font-mono text-[10px] text-slate-400">CHART 03</span>
                        </div>
                        <div className="h-64">
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart
                                    data={confData}
                                    margin={{ top: 5, right: 10, left: -10, bottom: 5 }}
                                >
                                    <XAxis
                                        dataKey="name"
                                        tick={{
                                            fontSize: 10,
                                            fill: "#64748B",
                                            fontFamily: "IBM Plex Mono",
                                        }}
                                        tickLine={false}
                                        axisLine={{ stroke: "#E2E8F0" }}
                                    />
                                    <YAxis
                                        tick={{
                                            fontSize: 10,
                                            fill: "#64748B",
                                            fontFamily: "IBM Plex Mono",
                                        }}
                                        tickLine={false}
                                        axisLine={{ stroke: "#E2E8F0" }}
                                    />
                                    <Tooltip
                                        contentStyle={{
                                            backgroundColor: "#FFFFFF",
                                            border: "1px solid #DCE4EF",
                                            borderRadius: "8px",
                                            boxShadow: "0 2px 4px rgba(0,0,0,0.04)",
                                            fontFamily: "IBM Plex Mono",
                                            fontSize: "11px",
                                        }}
                                    />
                                    <Bar dataKey="value" fill="#DC2626" radius={[4, 4, 0, 0]} />
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                    <p className="text-[11px] font-mono text-slate-400 mt-2 text-right">
                        Data completeness scores
                    </p>
                </div>

                {/* Your alerts */}
                <div className="col-span-12 lg:col-span-6 bg-white border border-[#DCE4EF] rounded-xl shadow-2xs overflow-hidden">
                    <div className="px-5 py-3.5 border-b border-[#DCE4EF] flex items-center justify-between bg-slate-50/50">
                        <div className="flex items-center gap-2">
                            <Activity size={15} className="text-red-600" />
                            <p className="font-mono text-[11px] font-semibold uppercase tracking-wider text-slate-600">
                                Your alerts
                            </p>
                        </div>
                        <Link
                            to="/alerts"
                            data-testid="view-all-alerts"
                            className="text-xs font-mono text-slate-600 hover:text-slate-950 inline-flex items-center gap-1 font-medium transition-colors"
                        >
                            all alerts <ArrowUpRight size={13} />
                        </Link>
                    </div>
                    {alerts.length === 0 ? (
                        <div className="p-8 text-center">
                            <p className="font-mono text-xs text-slate-500 uppercase tracking-widest">
                                No active alerts
                            </p>
                            <p className="mt-2 text-sm text-slate-600">
                                Add products or ingredients to your{" "}
                                <Link
                                    to="/watchlist"
                                    className="underline underline-offset-2 font-medium text-slate-900 hover:text-red-600"
                                >
                                    watchlist
                                </Link>{" "}
                                to start receiving matches.
                            </p>
                        </div>
                    ) : (
                        <ul className="divide-y divide-[#DCE4EF]">
                            {alerts.map((a) => (
                                <li
                                    key={a.alert_id}
                                    className="px-5 py-3.5 hover:bg-slate-50/70 transition-colors"
                                >
                                    <div className="flex items-center gap-3">
                                        <SeverityBadge severity={a.severity} size="sm" />
                                        <Link
                                            to={`/recalls/${a.recall_id}`}
                                            className="text-sm font-medium text-slate-900 truncate hover:text-red-600 transition-colors"
                                        >
                                            {a.product}
                                        </Link>
                                    </div>
                                    <p className="mt-1.5 text-[11px] font-mono text-slate-500">
                                        matched on {a.matched_on} · {a.matched_term} · {a.region}
                                    </p>
                                </li>
                            ))}
                        </ul>
                    )}
                </div>

                {/* Latest recalls */}
                <div className="col-span-12 lg:col-span-6 bg-white border border-[#DCE4EF] rounded-xl shadow-2xs overflow-hidden">
                    <div className="px-5 py-3.5 border-b border-[#DCE4EF] flex items-center justify-between bg-slate-50/50">
                        <div className="flex items-center gap-2">
                            <Database size={15} className="text-slate-600" />
                            <p className="font-mono text-[11px] font-semibold uppercase tracking-wider text-slate-600">
                                Latest recalls
                            </p>
                        </div>
                        <Link
                            to="/recalls"
                            data-testid="view-all-recalls"
                            className="text-xs font-mono text-slate-600 hover:text-slate-950 inline-flex items-center gap-1 font-medium transition-colors"
                        >
                            browse all <ArrowUpRight size={13} />
                        </Link>
                    </div>
                    <ul className="divide-y divide-[#DCE4EF]">
                        {recentRecalls.map((r) => (
                            <li
                                key={r.recall_id}
                                className="px-5 py-3.5 hover:bg-slate-50/70 transition-colors"
                            >
                                <div className="flex items-center gap-3">
                                    <SeverityBadge severity={r.severity} size="sm" />
                                    <Link
                                        to={`/recalls/${r.recall_id}`}
                                        className="text-sm font-medium text-slate-900 truncate hover:text-red-600 transition-colors"
                                    >
                                        {r.product_name}
                                    </Link>
                                </div>
                                <div className="mt-1.5 flex items-center justify-between gap-4">
                                    <p className="text-[11px] font-mono text-slate-500 truncate">
                                        {r.source} · {r.region} · {r.category}
                                    </p>
                                    <ConfidenceMeter value={r.confidence_score} showLabel={false} />
                                </div>
                            </li>
                        ))}
                    </ul>
                </div>
            </div>
        </Layout>
    );
}

function MetricCard({
    label,
    value,
    sub,
    accent = "text-slate-950",
    icon: Icon,
    iconColor,
    testid,
}) {
    return (
        <div
            data-testid={testid}
            className="bg-white border border-[#DCE4EF] rounded-xl p-5 shadow-2xs flex flex-col justify-between transition-all hover:border-slate-300"
        >
            <div className="flex items-center justify-between">
                <p className="font-mono text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                    {label}
                </p>
                {Icon && (
                    <div className={`p-1.5 rounded-lg ${iconColor || "text-slate-700 bg-slate-100"}`}>
                        <Icon size={16} strokeWidth={2} />
                    </div>
                )}
            </div>
            <div className="mt-3">
                <p className={`font-display font-bold text-3xl tabular ${accent}`}>{value}</p>
                <p className="mt-1 text-[11px] text-slate-500 font-mono">{sub}</p>
            </div>
        </div>
    );
}
