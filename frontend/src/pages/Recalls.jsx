import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import Layout from "../components/Layout";
import SeverityBadge from "../components/SeverityBadge";
import ConfidenceMeter from "../components/ConfidenceMeter";
import { Search } from "lucide-react";

const SEVERITIES = ["", "high", "medium", "low", "unknown"];
const CATEGORIES = ["", "cosmetic", "drug", "device", "food", "unknown"];
const REGIONS = ["", "EU", "US"];
const SOURCES = ["", "EU Safety Gate", "Master Recall List", "Product Recalls", "Combined Product Recalls"];

const PAGE = 25;

export default function Recalls() {
    const [items, setItems] = useState([]);
    const [total, setTotal] = useState(0);
    const [skip, setSkip] = useState(0);
    const [q, setQ] = useState("");
    const [severity, setSeverity] = useState("");
    const [category, setCategory] = useState("");
    const [region, setRegion] = useState("");
    const [source, setSource] = useState("");

    const load = async () => {
        const params = new URLSearchParams();
        params.set("limit", String(PAGE));
        params.set("skip", String(skip));
        if (q) params.set("q", q);
        if (severity) params.set("severity", severity);
        if (category) params.set("category", category);
        if (region) params.set("region", region);
        if (source) params.set("source", source);
        const { data } = await api.get(`/recalls?${params.toString()}`);
        setItems(data.items || []);
        setTotal(data.total || 0);
    };

    useEffect(() => {
        load();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [skip, severity, category, region, source]);

    const onSearch = (e) => {
        e.preventDefault();
        setSkip(0);
        load();
    };

    return (
        <Layout>
            <div className="flex items-end justify-between mb-8">
                <div>
                    <p className="font-mono text-[11px] uppercase tracking-widest text-slate-500">Explorer</p>
                    <h2 className="mt-2 font-display font-black tracking-tight text-4xl text-slate-950">
                        All recalls
                    </h2>
                </div>
                <p className="font-mono text-xs text-slate-500 tabular">
                    {total.toLocaleString()} records
                </p>
            </div>

            {/* Filters */}
            <div className="border border-slate-200 p-4 mb-4 bg-slate-50">
                <form onSubmit={onSearch} className="flex gap-3 items-center">
                    <div className="flex-1 relative">
                        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                        <input
                            data-testid="recalls-search-input"
                            value={q}
                            onChange={(e) => setQ(e.target.value)}
                            placeholder="Search by product, ingredient, or recall reason..."
                            className="w-full pl-9 pr-3 py-2 text-sm bg-white border border-slate-200 hover:border-slate-400 focus:border-slate-950 outline-none rounded-sm"
                        />
                    </div>
                    <button
                        type="submit"
                        data-testid="recalls-search-btn"
                        className="px-4 py-2 text-xs font-mono bg-slate-950 text-white hover:bg-slate-800 rounded-sm"
                    >
                        SEARCH
                    </button>
                </form>
                <div className="flex gap-3 mt-3 flex-wrap">
                    <Select label="SEVERITY" value={severity} setValue={(v) => { setSeverity(v); setSkip(0); }} options={SEVERITIES} testid="filter-severity" />
                    <Select label="CATEGORY" value={category} setValue={(v) => { setCategory(v); setSkip(0); }} options={CATEGORIES} testid="filter-category" />
                    <Select label="REGION" value={region} setValue={(v) => { setRegion(v); setSkip(0); }} options={REGIONS} testid="filter-region" />
                    <Select label="SOURCE" value={source} setValue={(v) => { setSource(v); setSkip(0); }} options={SOURCES} testid="filter-source" />
                </div>
            </div>

            {/* Table */}
            <div className="border border-slate-200" data-testid="recalls-table">
                <div className="grid grid-cols-12 px-5 py-2 border-b border-slate-200 bg-slate-50 text-[10px] font-mono uppercase tracking-widest text-slate-500">
                    <div className="col-span-2">Severity</div>
                    <div className="col-span-4">Product</div>
                    <div className="col-span-2">Category · Region</div>
                    <div className="col-span-2">Source</div>
                    <div className="col-span-2 text-right">Confidence</div>
                </div>
                {items.length === 0 ? (
                    <div className="p-12 text-center font-mono text-xs uppercase tracking-widest text-slate-500">No recalls match filters</div>
                ) : (
                    items.map((r) => (
                        <Link
                            to={`/recalls/${r.recall_id}`}
                            key={r.recall_id}
                            data-testid={`recall-row-${r.recall_id}`}
                            className="grid grid-cols-12 px-5 py-3 items-center grid-row"
                        >
                            <div className="col-span-2"><SeverityBadge severity={r.severity} size="sm" /></div>
                            <div className="col-span-4">
                                <p className="text-sm text-slate-900 truncate">{r.product_name}</p>
                                <p className="text-[11px] text-slate-500 truncate">{r.recall_reason}</p>
                            </div>
                            <div className="col-span-2 text-xs font-mono text-slate-700">
                                <div className="uppercase">{r.category}</div>
                                <div className="text-slate-500">{r.region}</div>
                            </div>
                            <div className="col-span-2 text-xs font-mono text-slate-600 truncate">{r.source}</div>
                            <div className="col-span-2 flex justify-end"><ConfidenceMeter value={r.confidence_score} /></div>
                        </Link>
                    ))
                )}
            </div>

            {/* Pagination */}
            <div className="flex items-center justify-between mt-4 font-mono text-xs text-slate-600">
                <span>
                    {total === 0 ? 0 : skip + 1}–{Math.min(total, skip + items.length)} of {total.toLocaleString()}
                </span>
                <div className="flex gap-2">
                    <button
                        data-testid="prev-page-btn"
                        onClick={() => setSkip(Math.max(0, skip - PAGE))}
                        disabled={skip === 0}
                        className="px-3 py-1.5 border border-slate-200 disabled:opacity-40 hover:border-slate-950 rounded-sm"
                    >
                        ← Prev
                    </button>
                    <button
                        data-testid="next-page-btn"
                        onClick={() => setSkip(skip + PAGE)}
                        disabled={skip + PAGE >= total}
                        className="px-3 py-1.5 border border-slate-200 disabled:opacity-40 hover:border-slate-950 rounded-sm"
                    >
                        Next →
                    </button>
                </div>
            </div>
        </Layout>
    );
}

function Select({ label, value, setValue, options, testid }) {
    return (
        <div className="flex items-center gap-2">
            <span className="font-mono text-[10px] uppercase tracking-widest text-slate-500">{label}</span>
            <select
                data-testid={testid}
                value={value}
                onChange={(e) => setValue(e.target.value)}
                className="px-2 py-1.5 text-xs font-mono bg-white border border-slate-200 hover:border-slate-950 outline-none rounded-sm"
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
