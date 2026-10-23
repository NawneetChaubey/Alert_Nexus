import React from "react";

export default function ConfidenceMeter({ value = 0, showLabel = true }) {
    const pct = Math.max(0, Math.min(1, Number(value) || 0));
    const color = pct >= 0.7 ? "bg-emerald-500" : pct >= 0.4 ? "bg-amber-500" : "bg-rose-500";
    return (
        <div className="flex items-center gap-2 min-w-[96px]" data-testid="confidence-meter">
            <div className="h-2 w-16 bg-slate-100 border border-slate-200 rounded-full overflow-hidden relative">
                <div className={`h-full ${color} rounded-full`} style={{ width: `${Math.round(pct * 100)}%` }} />
            </div>
            {showLabel && (
                <span className="font-mono text-[11px] text-slate-600 tabular">{Math.round(pct * 100)}%</span>
            )}
        </div>
    );
}
