import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import Layout from "../components/Layout";
import SeverityBadge from "../components/SeverityBadge";
import ConfidenceMeter from "../components/ConfidenceMeter";

export default function Alerts() {
    const [items, setItems] = useState([]);
    const [severity, setSeverity] = useState("");
    const [matched, setMatched] = useState("");
    const [unread, setUnread] = useState(0);

    const load = async () => {
        const params = [];
        if (severity) params.push(`severity=${severity}`);
        if (matched) params.push(`matched_on=${matched}`);
        const q = params.length ? `?${params.join("&")}` : "";
        const { data } = await api.get(`/alerts${q}`);
        setItems(data.items || []);
        setUnread(data.unread || 0);
    };

    useEffect(() => {
        load();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [severity, matched]);

    const markAllRead = async () => {
        await api.post("/alerts/read-all");
        load();
    };

    return (
        <Layout>
            <div className="flex items-end justify-between mb-8">
                <div>
                    <p className="font-mono text-[11px] uppercase tracking-widest text-slate-500">Watchlist alerts</p>
                    <h2 className="mt-2 font-display font-black tracking-tight text-4xl text-slate-950">
                        Alerts feed
                    </h2>
                </div>
                <div className="flex items-center gap-4">
                    <p className="font-mono text-xs text-slate-500">
                        {items.length} total · <span className="text-red-600">{unread} unread</span>
                    </p>
                    <button
                        data-testid="mark-all-read-btn"
                        onClick={markAllRead}
                        className="px-3 py-2 text-xs font-mono bg-white border border-slate-200 hover:border-slate-950 rounded-sm"
                    >
                        Mark all read
                    </button>
                </div>
            </div>

            <div className="flex items-center gap-3 mb-4">
                <Filter label="SEVERITY" value={severity} setValue={setSeverity} options={["", "high", "medium", "low", "unknown"]} testid="filter-severity" />
                <Filter label="MATCHED" value={matched} setValue={setMatched} options={["", "product", "ingredient"]} testid="filter-matched" />
            </div>

            <div className="border border-slate-200" data-testid="alerts-table">
                <div className="grid grid-cols-12 px-5 py-2 border-b border-slate-200 bg-slate-50 text-[10px] font-mono uppercase tracking-widest text-slate-500">
                    <div className="col-span-2">Severity</div>
                    <div className="col-span-4">Product</div>
                    <div className="col-span-2">Matched on</div>
                    <div className="col-span-2">Region / Source</div>
                    <div className="col-span-2 text-right">Confidence</div>
                </div>
                {items.length === 0 ? (
                    <div className="p-12 text-center">
                        <p className="font-mono text-xs uppercase tracking-widest text-slate-500">No alerts</p>
                        <p className="mt-2 text-sm text-slate-600">
                            Try adding products or ingredients to your{" "}
                            <Link to="/watchlist" className="underline font-medium">watchlist</Link>.
                        </p>
                    </div>
                ) : (
                    items.map((a) => (
                        <Link
                            to={`/recalls/${a.recall_id}`}
                            key={a.alert_id}
                            data-testid={`alert-row-${a.alert_id}`}
                            className="grid grid-cols-12 px-5 py-3 items-center grid-row hover:bg-slate-50"
                        >
                            <div className="col-span-2"><SeverityBadge severity={a.severity} size="sm" /></div>
                            <div className="col-span-4">
                                <p className="text-sm text-slate-900 truncate">{a.product}</p>
                                <p className="text-[11px] text-slate-500 truncate">{a.recall_reason}</p>
                            </div>
                            <div className="col-span-2">
                                <span className="font-mono text-xs text-slate-700">{a.matched_on}</span>
                                <span className="block text-[11px] text-slate-500 truncate">{a.matched_term}</span>
                            </div>
                            <div className="col-span-2 text-xs font-mono text-slate-600">
                                <div>{a.region}</div>
                                <div className="text-slate-500 truncate">{a.source}</div>
                            </div>
                            <div className="col-span-2 flex justify-end"><ConfidenceMeter value={a.confidence_score} /></div>
                        </Link>
                    ))
                )}
            </div>
        </Layout>
    );
}

function Filter({ label, value, setValue, options, testid }) {
    return (
        <div className="flex items-center gap-2">
            <span className="font-mono text-[10px] uppercase tracking-widest text-slate-500">{label}</span>
            <select
                data-testid={testid}
                value={value}
                onChange={(e) => setValue(e.target.value)}
                className="px-2 py-1.5 text-xs font-mono border border-slate-200 bg-white hover:border-slate-950 focus:border-slate-950 outline-none rounded-sm"
            >
                {options.map((o) => (
                    <option key={o} value={o}>
                        {o || "all"}
                    </option>
                ))}
            </select>
        </div>
    );
}
