import React, { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../lib/api";
import Layout from "../components/Layout";
import SeverityBadge from "../components/SeverityBadge";
import ConfidenceMeter from "../components/ConfidenceMeter";
import { Sparkles, ArrowLeft, ExternalLink } from "lucide-react";

export default function RecallDetail() {
    const { id } = useParams();
    const [data, setData] = useState(null);
    const [explanation, setExplanation] = useState(null);
    const [loadingExpl, setLoadingExpl] = useState(false);

    useEffect(() => {
        (async () => {
            const { data } = await api.get(`/recalls/${id}`);
            setData(data);
        })();
    }, [id]);

    const loadExplanation = async () => {
        setLoadingExpl(true);
        try {
            const { data } = await api.post(`/recalls/${id}/explain`);
            setExplanation(data.explanation);
        } catch (e) {
            setExplanation("AI explanation unavailable. Please try again.");
        } finally {
            setLoadingExpl(false);
        }
    };

    if (!data) {
        return (
            <Layout>
                <p className="font-mono text-xs uppercase tracking-widest text-slate-500">Loading recall...</p>
            </Layout>
        );
    }

    const r = data.recall;
    const inferredSet = new Set(r.inferred_fields || []);

    return (
        <Layout>
            <Link
                to="/recalls"
                data-testid="back-to-recalls"
                className="inline-flex items-center gap-2 text-xs font-mono text-slate-500 hover:text-slate-950 mb-6"
            >
                <ArrowLeft size={12} /> BACK TO RECALLS
            </Link>

            {/* Header */}
            <div className="border border-slate-200 p-6 mb-6" data-testid="recall-header">
                <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-3 mb-3">
                            <SeverityBadge severity={r.severity} />
                            <span className="font-mono text-xs text-slate-500 uppercase tracking-wider">
                                {r.category} · {r.region} · {r.source}
                            </span>
                        </div>
                        <h2 className="font-display font-bold tracking-tight text-2xl text-slate-950">
                            {r.product_name}
                        </h2>
                        <p className="mt-3 text-sm text-slate-600 leading-relaxed max-w-3xl">{r.recall_reason}</p>
                    </div>
                    <div className="text-right shrink-0">
                        <p className="font-mono text-[10px] uppercase tracking-widest text-slate-500 mb-1">
                            Confidence
                        </p>
                        <ConfidenceMeter value={r.confidence_score} />
                        <p className="font-mono text-[10px] text-slate-500 mt-2">
                            {r.inferred_fields.length} inferred fields
                        </p>
                    </div>
                </div>
            </div>

            <div className="grid grid-cols-12 gap-6">
                {/* AI explanation */}
                <div className="col-span-12 lg:col-span-7" data-testid="ai-block">
                    <div className="ai-block p-6">
                        <div className="flex items-center justify-between mb-4">
                            <span className="ai-label">[AI SUMMARY · CLAUDE SONNET 4.5]</span>
                            {!explanation && (
                                <button
                                    data-testid="generate-explanation-btn"
                                    onClick={loadExplanation}
                                    disabled={loadingExpl}
                                    className="inline-flex items-center gap-2 px-3 py-1.5 text-xs font-mono bg-slate-950 text-white hover:bg-slate-800 disabled:opacity-50 rounded-sm"
                                >
                                    <Sparkles size={12} />
                                    {loadingExpl ? "GENERATING..." : "GENERATE"}
                                </button>
                            )}
                        </div>
                        {explanation ? (
                            <div className="text-[15px] text-slate-900 leading-relaxed">{explanation}</div>
                        ) : loadingExpl ? (
                            <div className="font-mono text-xs text-slate-500 animate-pulse">
                                Asking the model to explain this recall...
                            </div>
                        ) : (
                            <div className="text-sm text-slate-700 leading-relaxed">
                                Generate a human-readable explanation of this recall — what happened, risk level,
                                who is affected and what to do. Explanations respect confidence scores and never
                                provide medical advice.
                            </div>
                        )}
                    </div>

                    {/* Lineage */}
                    <div className="mt-6 border border-slate-200">
                        <div className="px-5 py-3 border-b border-slate-200 bg-slate-50">
                            <p className="font-mono text-[10px] uppercase tracking-widest text-slate-500">
                                Data lineage · original → normalized
                            </p>
                        </div>
                        <div className="grid grid-cols-12 px-5 py-2 border-b border-slate-200 bg-slate-50 text-[10px] font-mono uppercase tracking-widest text-slate-500">
                            <div className="col-span-3">Field</div>
                            <div className="col-span-4">Original</div>
                            <div className="col-span-3">Normalized / Inferred</div>
                            <div className="col-span-2">Method</div>
                        </div>
                        {data.lineage.length === 0 ? (
                            <div className="p-5 text-xs text-slate-500">No inference required — all fields were present in the source.</div>
                        ) : (
                            data.lineage.map((l, i) => (
                                <div key={i} className="grid grid-cols-12 px-5 py-3 grid-row text-sm">
                                    <div className="col-span-3 font-mono text-xs text-slate-700 uppercase tracking-wider">
                                        {l.field_name}
                                    </div>
                                    <div className="col-span-4 text-slate-500 italic truncate">
                                        {l.original_value || <span className="text-slate-400">— empty —</span>}
                                    </div>
                                    <div className="col-span-3 font-medium text-slate-900 truncate">
                                        {l.inferred_value}
                                    </div>
                                    <div className="col-span-2 font-mono text-[10px] text-amber-700 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded-sm self-start">
                                        {l.inference_method}
                                    </div>
                                </div>
                            ))
                        )}
                    </div>
                </div>

                {/* Sidebar facts */}
                <div className="col-span-12 lg:col-span-5 space-y-6" data-testid="recall-facts">
                    <FactBox title="INGREDIENTS">
                        {r.ingredients.length === 0 ? (
                            <p className="text-xs text-slate-500">unknown</p>
                        ) : (
                            <div className="flex flex-wrap gap-1.5">
                                {r.ingredients.map((i, idx) => {
                                    const isPlaceholder = i.startsWith("unknown_compound_");
                                    return (
                                        <span
                                            key={idx}
                                            className={`px-2 py-1 text-xs font-mono rounded-sm border ${
                                                isPlaceholder
                                                    ? "bg-slate-50 border-dashed border-slate-300 text-slate-500"
                                                    : inferredSet.has("ingredients")
                                                    ? "bg-amber-50 border-amber-200 text-amber-800"
                                                    : "bg-slate-100 border-slate-200 text-slate-800"
                                            }`}
                                        >
                                            {i}
                                        </span>
                                    );
                                })}
                            </div>
                        )}
                    </FactBox>

                    <FactBox title="CORRECTIVE ACTION">
                        <p className="text-sm text-slate-700 leading-relaxed">
                            {r.corrective_action || <span className="text-slate-400">not specified</span>}
                        </p>
                    </FactBox>

                    <FactBox title="METADATA">
                        <dl className="grid grid-cols-3 gap-y-2 text-xs font-mono">
                            <dt className="col-span-1 text-slate-500">RECALL ID</dt>
                            <dd className="col-span-2 truncate">{r.recall_id}</dd>
                            <dt className="col-span-1 text-slate-500">EXTERNAL</dt>
                            <dd className="col-span-2 truncate">{r.external_id || "—"}</dd>
                            <dt className="col-span-1 text-slate-500">BARCODE</dt>
                            <dd className="col-span-2 truncate">{r.barcode || "—"}</dd>
                            <dt className="col-span-1 text-slate-500">BATCH</dt>
                            <dd className="col-span-2 truncate">{r.batch_number || "—"}</dd>
                            <dt className="col-span-1 text-slate-500">TIMESTAMP</dt>
                            <dd className="col-span-2">{new Date(r.timestamp).toLocaleString()}</dd>
                            {r.source_url && (
                                <>
                                    <dt className="col-span-1 text-slate-500">SOURCE</dt>
                                    <dd className="col-span-2">
                                        <a
                                            href={r.source_url}
                                            target="_blank"
                                            rel="noreferrer"
                                            className="inline-flex items-center gap-1 underline text-slate-900 hover:text-slate-600"
                                        >
                                            view <ExternalLink size={10} />
                                        </a>
                                    </dd>
                                </>
                            )}
                        </dl>
                    </FactBox>
                </div>
            </div>
        </Layout>
    );
}

function FactBox({ title, children }) {
    return (
        <div className="border border-slate-200">
            <div className="px-4 py-2.5 border-b border-slate-200 bg-slate-50">
                <p className="font-mono text-[10px] uppercase tracking-widest text-slate-500">{title}</p>
            </div>
            <div className="p-4">{children}</div>
        </div>
    );
}
