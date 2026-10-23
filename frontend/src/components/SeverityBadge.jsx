import React from "react";

const STYLES = {
    high: "bg-red-600 text-white",
    medium: "bg-amber-500 text-white",
    low: "bg-blue-600 text-white",
    unknown: "bg-slate-500 text-white",
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
