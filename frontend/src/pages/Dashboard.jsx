import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import Layout from "../components/Layout";
import SeverityBadge from "../components/SeverityBadge";
import ConfidenceMeter from "../components/ConfidenceMeter";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from "recharts";
import { ArrowUpRight } from "lucide-react";

const SEV_COLORS = { high: "#dc2626", medium: "#f59e0b", low: "#2563eb", unknown: "#64748b" };

export default function Dashboard() {
    const [stats, setStats] = useState(null);
    const [alerts, setAlerts] = useState([]);
    const [recentRecalls, setRecentRecalls] = useState([]);

    useEffect(() => {
        (async () => {
            const [s, a, r] = await Promise.all([
                api.get("/stats/ingestion").then((x) => x.data),
                api.get("/alerts?limit=5").then((x) => x.data),
                api.get("/recalls?limit=6").then((x) => x.data),
            ]);
            setStats(s);
            setAlerts(a.items || []);
            setRecentRecalls(r.items || []);
        })();
    }, []);

    const severityData = stats
        ? Object.entries(stats.severity || {}).map(([k, v]) => ({ name: k, value: v, color: SEV_COLORS[k] || "#64748b" }))
        : [];
    const sourceData = stats
        ? Object.entries(stats.source || {}).map(([k, v]) => ({ name: k, value: v }))
        : [];
    const confData = stats
        ? Object.entries(stats.confidence_buckets || {}).map(([k, v]) => ({ name: k, value: v }))
        : [];

    return (
        <Layout>
            {/* Header */}
            <div className="flex items-end justify-between mb-8" data-testid="dashboard-header">
                <div>
                    <p className="font-mono text-[11px] uppercase tracking-widest text-slate-500">Overview</p>
                    <h2 className="mt-2 font-display font-black tracking-tight text-4xl text-slate-950">
                        Global recall signal
                    </h2>
                </div>
                <p className="font-mono text-xs text-slate-500">
                    {stats ? `${stats.total_normalized.toLocaleString()} normalized records` : "—"}
                </p>
            </div>

            {/* Metrics grid */}
            <div className="grid grid-cols-4 border border-slate-200 mb-8" data-testid="metrics-grid">
                <Metric
                    label="Total recalls"
                    value={stats?.total_normalized?.toLocaleString() || "—"}
                    sub="normalized"
                />
                <Metric
                    label="High severity"
                    value={stats?.severity?.high?.toLocaleString() || "0"}
                    sub="toxic · contamination · prohibited"
                    accent="text-red-700"
                />
                <Metric
                    label="Sources"
                    value={stats ? Object.keys(stats.source || {}).length : "—"}
                    sub="active feeds"
                />
                <Metric
                    label="Regions"
                    value={stats ? Object.keys(stats.region || {}).length : "—"}
                    sub="tracked"
                    last
                />
            </div>

            <div className="grid grid-cols-12 gap-6">
                {/* Severity chart */}
                <div className="col-span-12 lg:col-span-4 border border-slate-200 p-5">
                    <p className="font-mono text-[10px] uppercase tracking-widest text-slate-500 mb-3">
                        [chart 01] Severity mix
                    </p>
                    <div className="h-52">
                        <ResponsiveContainer>
                            <PieChart>
                                <Pie
                                    data={severityData}
                                    innerRadius={40}
                                    outerRadius={70}
                                    dataKey="value"
                                    stroke="#ffffff"
                                    strokeWidth={2}
                                >
                                    {severityData.map((d, i) => (
                                        <Cell key={i} fill={d.color} />
                                    ))}
                                </Pie>
                                <Tooltip
                                    contentStyle={{
                                        border: "1px solid #e2e8f0",
                                        borderRadius: 0,
                                        boxShadow: "none",
                                        fontFamily: "IBM Plex Mono",
                                        fontSize: "11px",
                                    }}
                                />
                            </PieChart>
                        </ResponsiveContainer>
                    </div>
                    <ul className="space-y-1 mt-3">
                        {severityData.map((d) => (
                            <li key={d.name} className="flex items-center justify-between text-xs">
                                <span className="flex items-center gap-2">
                                    <span className="h-2 w-2 block" style={{ background: d.color }} />
                                    <span className="font-mono uppercase">{d.name}</span>
                                </span>
                                <span className="font-mono tabular text-slate-600">{d.value.toLocaleString()}</span>
                            </li>
                        ))}
                    </ul>
                </div>

                {/* Source bar */}
                <div className="col-span-12 lg:col-span-4 border border-slate-200 p-5">
                    <p className="font-mono text-[10px] uppercase tracking-widest text-slate-500 mb-3">
                        [chart 02] Records per source
                    </p>
                    <div className="h-52">
                        <ResponsiveContainer>
                            <BarChart data={sourceData}>
                                <XAxis
                                    dataKey="name"
                                    tick={{ fontSize: 9, fontFamily: "IBM Plex Mono" }}
                                    tickLine={false}
                                    axisLine={{ stroke: "#cbd5e1" }}
                                    interval={0}
                                />
                                <YAxis
                                    tick={{ fontSize: 10, fontFamily: "IBM Plex Mono" }}
                                    tickLine={false}
                                    axisLine={{ stroke: "#cbd5e1" }}
                                />
                                <Tooltip
                                    contentStyle={{
                                        border: "1px solid #e2e8f0",
                                        borderRadius: 0,
                                        boxShadow: "none",
                                        fontFamily: "IBM Plex Mono",
                                        fontSize: "11px",
                                    }}
                                />
                                <Bar dataKey="value" fill="#020617" />
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                </div>

                {/* Confidence distribution */}
                <div className="col-span-12 lg:col-span-4 border border-slate-200 p-5">
                    <p className="font-mono text-[10px] uppercase tracking-widest text-slate-500 mb-3">
                        [chart 03] Confidence distribution
                    </p>
                    <div className="h-52">
                        <ResponsiveContainer>
                            <BarChart data={confData}>
                                <XAxis
                                    dataKey="name"
                                    tick={{ fontSize: 10, fontFamily: "IBM Plex Mono" }}
                                    tickLine={false}
                                    axisLine={{ stroke: "#cbd5e1" }}
                                />
                                <YAxis
                                    tick={{ fontSize: 10, fontFamily: "IBM Plex Mono" }}
                                    tickLine={false}
                                    axisLine={{ stroke: "#cbd5e1" }}
                                />
                                <Tooltip
                                    contentStyle={{
                                        border: "1px solid #e2e8f0",
                                        borderRadius: 0,
                                        boxShadow: "none",
                                        fontFamily: "IBM Plex Mono",
                                        fontSize: "11px",
                                    }}
                                />
                                <Bar dataKey="value" fill="#dc2626" />
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                </div>

                {/* Your alerts */}
                <div className="col-span-12 lg:col-span-6 border border-slate-200">
                    <div className="px-5 py-3 border-b border-slate-200 flex items-center justify-between">
                        <p className="font-mono text-[10px] uppercase tracking-widest text-slate-500">
                            Your alerts
                        </p>
                        <Link
                            to="/alerts"
                            data-testid="view-all-alerts"
                            className="text-xs font-mono text-slate-700 hover:text-slate-950 inline-flex items-center gap-1"
                        >
                            all alerts <ArrowUpRight size={12} />
                        </Link>
                    </div>
                    {alerts.length === 0 ? (
                        <div className="p-8 text-center">
                            <p className="font-mono text-xs text-slate-500 uppercase tracking-widest">
                                No alerts yet
                            </p>
                            <p className="mt-2 text-sm text-slate-600">
                                Add products or ingredients to your{" "}
                                <Link to="/watchlist" className="underline underline-offset-2 font-medium">
                                    watchlist
                                </Link>{" "}
                                to start receiving matches.
                            </p>
                        </div>
                    ) : (
                        <ul>
                            {alerts.map((a) => (
                                <li key={a.alert_id} className="grid-row px-5 py-3">
                                    <div className="flex items-center gap-3">
                                        <SeverityBadge severity={a.severity} size="sm" />
                                        <Link
                                            to={`/recalls/${a.recall_id}`}
                                            className="text-sm text-slate-900 truncate hover:underline"
                                        >
                                            {a.product}
                                        </Link>
                                    </div>
                                    <p className="mt-1 text-[11px] font-mono text-slate-500">
                                        matched on {a.matched_on} · {a.matched_term} · {a.region}
                                    </p>
                                </li>
                            ))}
                        </ul>
                    )}
                </div>

                {/* Latest recalls */}
                <div className="col-span-12 lg:col-span-6 border border-slate-200">
                    <div className="px-5 py-3 border-b border-slate-200 flex items-center justify-between">
                        <p className="font-mono text-[10px] uppercase tracking-widest text-slate-500">
                            Latest recalls
                        </p>
                        <Link
                            to="/recalls"
                            data-testid="view-all-recalls"
                            className="text-xs font-mono text-slate-700 hover:text-slate-950 inline-flex items-center gap-1"
                        >
                            browse all <ArrowUpRight size={12} />
                        </Link>
                    </div>
                    <ul>
                        {recentRecalls.map((r) => (
                            <li key={r.recall_id} className="grid-row px-5 py-3">
                                <div className="flex items-center gap-3">
                                    <SeverityBadge severity={r.severity} size="sm" />
                                    <Link
                                        to={`/recalls/${r.recall_id}`}
                                        className="text-sm text-slate-900 truncate hover:underline"
                                    >
                                        {r.product_name}
                                    </Link>
                                </div>
                                <div className="mt-1 flex items-center justify-between">
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

function Metric({ label, value, sub, accent = "text-slate-950", last = false }) {
    return (
        <div className={`p-5 ${last ? "" : "border-r border-slate-200"}`} data-testid={`metric-${label.toLowerCase().replace(/\s/g, "-")}`}>
            <p className="font-mono text-[10px] uppercase tracking-widest text-slate-500">{label}</p>
            <p className={`mt-2 font-display font-bold text-3xl tabular ${accent}`}>{value}</p>
            <p className="mt-1 text-[11px] text-slate-500">{sub}</p>
        </div>
    );
}
