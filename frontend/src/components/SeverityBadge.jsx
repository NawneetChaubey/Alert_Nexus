import React from "react";

const STYLES = {
    high: "bg-red-50 text-red-700 border border-red-200",
    medium: "bg-amber-50 text-amber-700 border border-amber-200",
    low: "bg-blue-50 text-blue-700 border border-blue-200",
    unknown: "bg-slate-50 text-slate-600 border border-slate-200",
};

export default function SeverityBadge({ severity = "unknown", size = "md" }) {
    const sv = (severity || "unknown").toLowerCase();
    const style = STYLES[sv] || STYLES.unknown;
    const cls = size === "sm" ? "px-1.5 py-0.5 text-[10px]" : "px-2 py-1 text-[11px]";
    return (
        <span
            data-testid={`severity-badge-${sv}`}
            className={`inline-flex items-center ${cls} font-mono font-semibold uppercase tracking-wider rounded-sm ${style}`}
        >
            {sv}
        </span>
    );
}
