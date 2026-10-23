import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import Layout from "../components/Layout";
import SeverityBadge from "../components/SeverityBadge";
import ConfidenceMeter from "../components/ConfidenceMeter";
import { Check, Trash2, RotateCcw, AlertTriangle, ShieldCheck } from "lucide-react";
import { toast } from "sonner";

export default function Alerts() {
    const [items, setItems] = useState([]);
    const [severity, setSeverity] = useState("");
    const [matched, setMatched] = useState("");
    const [statusView, setStatusView] = useState("active"); // "active" | "dismissed"
    const [unread, setUnread] = useState(0);
    const [dismissedCount, setDismissedCount] = useState(0);
    const [loading, setLoading] = useState(false);
    const [actionPendingId, setActionPendingId] = useState(null);

    const load = async () => {
        setLoading(true);
        try {
            const params = [];
            if (severity) params.push(`severity=${severity}`);
            if (matched) params.push(`matched_on=${matched}`);
            if (statusView === "dismissed") {
                params.push("status=dismissed");
            }
            const q = params.length ? `?${params.join("&")}` : "";
            const { data } = await api.get(`/alerts${q}`);
            setItems(data.items || []);
            setUnread(data.unread || 0);
            setDismissedCount(data.dismissed_count || 0);
        } catch (error) {
            console.error("Failed to load alerts:", error);
            toast.error("Failed to load alerts feed.");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        load();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [severity, matched, statusView]);

    const markAllRead = async () => {
        try {
            await api.post("/alerts/read-all");
            toast.success("All active alerts marked as read");
            load();
        } catch (error) {
            console.error(error);
            toast.error("Failed to mark all alerts as read");
        }
    };

    const handleMarkRead = async (e, alertId) => {
        e.preventDefault();
        e.stopPropagation();
        if (actionPendingId) return;

        setActionPendingId(alertId);
        try {
            await api.post(`/alerts/${alertId}/read`);
            setItems((prev) =>
                prev.map((item) =>
                    item.alert_id === alertId ? { ...item, read: true } : item
                )
            );
            setUnread((prev) => Math.max(0, prev - 1));
            toast.success("Alert marked as read");
        } catch (error) {
            console.error(error);
            toast.error("Failed to mark alert as read");
        } finally {
            setActionPendingId(null);
        }
    };

    const handleDismiss = async (e, alertId) => {
        e.preventDefault();
        e.stopPropagation();
        if (actionPendingId) return;

        setActionPendingId(alertId);
        try {
            await api.post(`/alerts/${alertId}/dismiss`);
            // Remove from active view
            const dismissedItem = items.find((i) => i.alert_id === alertId);
            setItems((prev) => prev.filter((item) => item.alert_id !== alertId));
            if (dismissedItem && !dismissedItem.read) {
                setUnread((prev) => Math.max(0, prev - 1));
            }
            setDismissedCount((prev) => prev + 1);
            toast.success("Alert dismissed");
        } catch (error) {
            console.error(error);
            toast.error("Failed to dismiss alert");
        } finally {
            setActionPendingId(null);
        }
    };

    const handleRestore = async (e, alertId) => {
        e.preventDefault();
        e.stopPropagation();
        if (actionPendingId) return;

        setActionPendingId(alertId);
        try {
            await api.post(`/alerts/${alertId}/restore`);
            setItems((prev) => prev.filter((item) => item.alert_id !== alertId));
            setDismissedCount((prev) => Math.max(0, prev - 1));
            toast.success("Alert restored to active feed");
        } catch (error) {
            console.error(error);
            toast.error("Failed to restore alert");
        } finally {
            setActionPendingId(null);
        }
    };

    return (
        <Layout>
            <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 mb-8">
                <div>
                    <p className="font-mono text-[11px] uppercase tracking-widest text-slate-500">Watchlist alerts</p>
                    <h2 className="mt-2 font-display font-black tracking-tight text-3xl sm:text-4xl text-slate-950">
                        Alerts feed
                    </h2>
                </div>
                <div className="flex items-center gap-4">
                    <p className="font-mono text-xs text-slate-500">
                        {items.length} {statusView === "active" ? "active" : "dismissed"} ·{" "}
                        <span className="text-red-600 font-medium">{unread} unread</span>
                    </p>
                    {statusView === "active" && unread > 0 && (
                        <button
                            data-testid="mark-all-read-btn"
                            onClick={markAllRead}
                            className="px-3 py-2 text-xs font-mono bg-white border border-slate-300 hover:border-slate-950 rounded-sm transition shadow-2xs"
                        >
                            Mark all read
                        </button>
                    )}
                </div>
            </div>

            {/* View Tabs & Filters */}
            <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
                <div className="flex items-center border border-slate-200 bg-slate-100 p-0.5 rounded-sm">
                    <button
                        type="button"
                        data-testid="tab-active-alerts"
                        onClick={() => setStatusView("active")}
                        className={`px-3 py-1.5 text-xs font-mono tracking-wider transition ${
                            statusView === "active"
                                ? "bg-white text-slate-950 font-bold shadow-xs"
                                : "text-slate-600 hover:text-slate-950"
                        }`}
                    >
                        ACTIVE ALERTS
                    </button>
                    <button
                        type="button"
                        data-testid="tab-dismissed-alerts"
                        onClick={() => setStatusView("dismissed")}
                        className={`px-3 py-1.5 text-xs font-mono tracking-wider transition flex items-center gap-1.5 ${
                            statusView === "dismissed"
                                ? "bg-white text-slate-950 font-bold shadow-xs"
                                : "text-slate-600 hover:text-slate-950"
                        }`}
                    >
                        <span>DISMISSED</span>
                        {dismissedCount > 0 && (
                            <span className="px-1.5 py-0.2 bg-slate-200 text-slate-700 text-[10px] rounded-full">
                                {dismissedCount}
                            </span>
                        )}
                    </button>
                </div>

                <div className="flex items-center gap-3">
                    <Filter
                        label="SEVERITY"
                        value={severity}
                        setValue={setSeverity}
                        options={["", "high", "medium", "low", "unknown"]}
                        testid="filter-severity"
                    />
                    <Filter
                        label="MATCHED"
                        value={matched}
                        setValue={setMatched}
                        options={["", "product", "ingredient"]}
                        testid="filter-matched"
                    />
                </div>
            </div>

            {/* Alerts Table */}
            <div className="border border-slate-200 overflow-x-auto bg-white" data-testid="alerts-table">
                <div className="min-w-[800px]">
                    <div className="grid grid-cols-12 px-5 py-2.5 border-b border-slate-200 bg-slate-50 text-[10px] font-mono uppercase tracking-widest text-slate-500">
                        <div className="col-span-2">Severity / Status</div>
                        <div className="col-span-3">Product / Issue</div>
                        <div className="col-span-2">Matched Term</div>
                        <div className="col-span-2">Region / Source</div>
                        <div className="col-span-1 text-center">Score</div>
                        <div className="col-span-2 text-right">Actions</div>
                    </div>

                    {loading ? (
                        <div className="p-12 text-center font-mono text-xs uppercase tracking-widest text-slate-400">
                            Loading alerts...
                        </div>
                    ) : items.length === 0 ? (
                        <div className="p-12 text-center">
                            {statusView === "active" ? (
                                <>
                                    <div className="inline-flex p-3 bg-slate-100 rounded-full mb-3 text-slate-400">
                                        <ShieldCheck size={24} />
                                    </div>
                                    <p className="font-mono text-xs uppercase tracking-widest text-slate-500">
                                        No active alerts
                                    </p>
                                    <p className="mt-2 text-sm text-slate-600">
                                        All clear, or try adding terms to your{" "}
                                        <Link to="/watchlist" className="underline font-medium text-slate-900">
                                            watchlist
                                        </Link>.
                                    </p>
                                </>
                            ) : (
                                <>
                                    <p className="font-mono text-xs uppercase tracking-widest text-slate-500">
                                        No dismissed alerts
                                    </p>
                                    <p className="mt-2 text-sm text-slate-600">
                                        Dismissed alerts are archived here to preserve compliance records.
                                    </p>
                                </>
                            )}
                        </div>
                    ) : (
                        items.map((a) => (
                            <div
                                key={a.alert_id}
                                data-testid={`alert-row-${a.alert_id}`}
                                className={`grid grid-cols-12 px-5 py-3.5 items-center border-b border-slate-100 transition hover:bg-slate-50/80 ${
                                    !a.read ? "bg-amber-50/30 font-medium" : ""
                                }`}
                            >
                                {/* Severity & Read Status Indicator */}
                                <div className="col-span-2 flex items-center gap-2">
                                    <SeverityBadge severity={a.severity} size="sm" />
                                    {!a.read && (
                                        <span
                                            data-testid={`unread-dot-${a.alert_id}`}
                                            className="h-2 w-2 rounded-full bg-red-600 shrink-0"
                                            title="Unread alert"
                                        />
                                    )}
                                </div>

                                {/* Product & Reason (Links to Recall Detail) */}
                                <div className="col-span-3 pr-2">
                                    <Link
                                        to={`/recalls/${a.recall_id}`}
                                        className="text-sm text-slate-900 hover:underline hover:text-red-700 truncate block font-medium"
                                        title={a.product}
                                    >
                                        {a.product}
                                    </Link>
                                    <p className="text-[11px] text-slate-500 truncate" title={a.recall_reason}>
                                        {a.recall_reason || "No description provided"}
                                    </p>
                                </div>

                                {/* Matched on Term */}
                                <div className="col-span-2">
                                    <span className="font-mono text-xs text-slate-700 uppercase">
                                        {a.matched_on}
                                    </span>
                                    <span
                                        className="block text-[11px] text-slate-600 truncate font-mono"
                                        title={a.matched_term}
                                    >
                                        &ldquo;{a.matched_term}&rdquo;
                                    </span>
                                    {a.evidence_type === "inferred" && (
                                        <span className="inline-block px-1.5 py-0.2 bg-amber-100 text-amber-800 text-[9px] font-mono rounded mt-0.5">
                                            inferred
                                        </span>
                                    )}
                                </div>

                                {/* Region & Source */}
                                <div className="col-span-2 text-xs font-mono text-slate-600">
                                    <div>{a.region || "Global"}</div>
                                    <div className="text-slate-500 text-[11px] truncate">{a.source}</div>
                                </div>

                                {/* Confidence Score */}
                                <div className="col-span-1 flex justify-center">
                                    <ConfidenceMeter value={a.confidence_score} />
                                </div>

                                {/* Actions Column: Mark Read & Dismiss */}
                                <div className="col-span-2 flex items-center justify-end gap-1.5">
                                    {statusView === "active" ? (
                                        <>
                                            {!a.read && (
                                                <button
                                                    type="button"
                                                    data-testid={`mark-read-${a.alert_id}`}
                                                    onClick={(e) => handleMarkRead(e, a.alert_id)}
                                                    disabled={actionPendingId === a.alert_id}
                                                    title="Mark alert as read"
                                                    className="p-1.5 text-slate-600 hover:text-slate-950 hover:bg-slate-200 border border-slate-200 rounded-sm transition disabled:opacity-40"
                                                >
                                                    <Check size={14} />
                                                </button>
                                            )}
                                            <button
                                                type="button"
                                                data-testid={`dismiss-alert-${a.alert_id}`}
                                                onClick={(e) => handleDismiss(e, a.alert_id)}
                                                disabled={actionPendingId === a.alert_id}
                                                title="Dismiss alert (archive from active feed)"
                                                className="flex items-center gap-1 px-2 py-1 text-[11px] font-mono text-red-700 hover:text-red-950 hover:bg-red-50 border border-red-200 rounded-sm transition disabled:opacity-40"
                                            >
                                                <Trash2 size={13} />
                                                <span className="hidden lg:inline">Dismiss</span>
                                            </button>
                                        </>
                                    ) : (
                                        <button
                                            type="button"
                                            data-testid={`restore-alert-${a.alert_id}`}
                                            onClick={(e) => handleRestore(e, a.alert_id)}
                                            disabled={actionPendingId === a.alert_id}
                                            title="Restore to active alerts"
                                            className="flex items-center gap-1 px-2.5 py-1 text-[11px] font-mono text-slate-700 hover:text-slate-950 hover:bg-slate-200 border border-slate-300 rounded-sm transition disabled:opacity-40"
                                        >
                                            <RotateCcw size={13} />
                                            <span>Restore</span>
                                        </button>
                                    )}
                                </div>
                            </div>
                        ))
                    )}
                </div>
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
