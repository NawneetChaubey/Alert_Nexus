import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import Layout from "../components/Layout";

export default function Compliance() {
    const [items, setItems] = useState([]);
    const [regions, setRegions] = useState([]);
    const [region, setRegion] = useState("");

    useEffect(() => {
        (async () => {
            const q = region ? `?region=${region}` : "";
            const { data } = await api.get(`/compliance${q}`);
            setItems(data.items || []);
            setRegions(data.regions || []);
        })();
    }, [region]);

    return (
        <Layout>
            <div className="flex items-end justify-between mb-8">
                <div>
                    <p className="font-mono text-[11px] uppercase tracking-widest text-slate-500">Regulatory seed</p>
                    <h2 className="mt-2 font-display font-black tracking-tight text-4xl text-slate-950">
                        Banned substances
                    </h2>
                    <p className="mt-2 text-sm text-slate-600 max-w-2xl">
                        A seed of known banned or conditionally-restricted substances per region. The matching engine
                        uses this list to flag recalls where a prohibited ingredient is detected.
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    <span className="font-mono text-[10px] uppercase tracking-widest text-slate-500">REGION</span>
                    <select
                        data-testid="region-filter"
                        value={region}
                        onChange={(e) => setRegion(e.target.value)}
                        className="px-2 py-1.5 text-xs font-mono bg-white border border-slate-200 hover:border-slate-950 rounded-sm"
                    >
                        <option value="">all</option>
                        {regions.map((r) => (
                            <option key={r} value={r}>
                                {r}
                            </option>
                        ))}
                    </select>
                </div>
            </div>

            <div className="border border-slate-200" data-testid="compliance-table">
                <div className="grid grid-cols-12 px-5 py-2 border-b border-slate-200 bg-slate-50 text-[10px] font-mono uppercase tracking-widest text-slate-500">
                    <div className="col-span-2">Region</div>
                    <div className="col-span-3">Substance</div>
                    <div className="col-span-7">Regulatory basis</div>
                </div>
                {items.map((it, i) => (
                    <div key={i} className="grid grid-cols-12 px-5 py-3 grid-row text-sm" data-testid={`compliance-row-${it.substance}`}>
                        <div className="col-span-2">
                            <span className="inline-block px-2 py-0.5 text-[10px] font-mono bg-slate-950 text-white rounded-sm">
                                {it.region}
                            </span>
                        </div>
                        <div className="col-span-3 font-mono text-sm text-slate-900">{it.substance}</div>
                        <div className="col-span-7 text-slate-700 leading-relaxed">{it.reason}</div>
                    </div>
                ))}
            </div>
        </Layout>
    );
}
