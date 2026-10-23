import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import Layout from "../components/Layout";
import { Plus, X } from "lucide-react";
import { toast } from "sonner";

export default function Watchlist() {
    const [wl, setWl] = useState({ products: [], ingredients: [] });
    const [suggestions, setSuggestions] = useState([]);
    const [newProduct, setNewProduct] = useState("");
    const [newIngredient, setNewIngredient] = useState("");

    const load = async () => {
        const [w, s] = await Promise.all([
            api.get("/watchlist").then((x) => x.data),
            api.get("/watchlist/suggestions").then((x) => x.data),
        ]);
        setWl(w);
        setSuggestions(s.ingredients || []);
    };
    useEffect(() => {
        load();
    }, []);

    const addProduct = async (e) => {
        e.preventDefault();
        const v = newProduct.trim();
        if (!v) return;
        const { data } = await api.post("/watchlist/products", { value: v });
        setWl(data.watchlist);
        setNewProduct("");
        toast.success(
            data.alerts_created > 0 ? `${data.alerts_created} new alerts triggered` : `Added "${v}" to watchlist`
        );
    };
    const removeProduct = async (v) => {
        const { data } = await api.delete(`/watchlist/products/${encodeURIComponent(v)}`);
        setWl(data);
    };

    const addIngredient = async (value) => {
        const v = (value || newIngredient).trim();
        if (!v) return;
        const { data } = await api.post("/watchlist/ingredients", { value: v });
        setWl(data.watchlist);
        setNewIngredient("");
        toast.success(
            data.alerts_created > 0 ? `${data.alerts_created} new alerts triggered` : `Added "${v}" to watchlist`
        );
    };
    const removeIngredient = async (v) => {
        const { data } = await api.delete(`/watchlist/ingredients/${encodeURIComponent(v)}`);
        setWl(data);
    };

    return (
        <Layout>
            <div className="mb-8">
                <p className="font-mono text-[11px] uppercase tracking-widest text-slate-500">Signals</p>
                <h2 className="mt-2 font-display font-black tracking-tight text-4xl text-slate-950">
                    Watchlist
                </h2>
                <p className="mt-2 text-sm text-slate-600 max-w-2xl">
                    Add products you sell, buy or use — and ingredients you want to track. Every new regulatory recall
                    is matched against this list. High-confidence matches trigger alerts.
                </p>
            </div>

            <div className="grid grid-cols-12 gap-6">
                {/* Products */}
                <section className="col-span-12 lg:col-span-6 border border-slate-200" data-testid="products-section">
                    <div className="px-5 py-3 border-b border-slate-200 bg-slate-50">
                        <p className="font-mono text-[10px] uppercase tracking-widest text-slate-500">
                            PRODUCTS · {wl.products.length}
                        </p>
                    </div>
                    <form onSubmit={addProduct} className="p-5 border-b border-slate-200 flex gap-2">
                        <input
                            data-testid="product-input"
                            value={newProduct}
                            onChange={(e) => setNewProduct(e.target.value)}
                            placeholder="e.g. Tylenol, Lipstick, Sunscreen..."
                            className="flex-1 px-3 py-2 text-sm border border-slate-200 focus:border-slate-950 outline-none rounded-sm"
                        />
                        <button
                            type="submit"
                            data-testid="add-product-btn"
                            className="px-4 py-2 text-xs font-mono bg-slate-950 text-white hover:bg-slate-800 inline-flex items-center gap-1 rounded-sm"
                        >
                            <Plus size={12} /> ADD
                        </button>
                    </form>
                    <div className="p-5 flex flex-wrap gap-2 min-h-[120px]" data-testid="products-chips">
                        {wl.products.length === 0 ? (
                            <p className="font-mono text-xs uppercase tracking-widest text-slate-400">
                                No products — add the ones you want to monitor.
                            </p>
                        ) : (
                            wl.products.map((p) => (
                                <Chip key={p} value={p} onRemove={() => removeProduct(p)} testid={`chip-product-${p}`} />
                            ))
                        )}
                    </div>
                </section>

                {/* Ingredients */}
                <section className="col-span-12 lg:col-span-6 border border-slate-200" data-testid="ingredients-section">
                    <div className="px-5 py-3 border-b border-slate-200 bg-slate-50">
                        <p className="font-mono text-[10px] uppercase tracking-widest text-slate-500">
                            INGREDIENTS · {wl.ingredients.length}
                        </p>
                    </div>
                    <form onSubmit={(e) => { e.preventDefault(); addIngredient(); }} className="p-5 border-b border-slate-200 flex gap-2">
                        <input
                            data-testid="ingredient-input"
                            list="ingredient-suggestions"
                            value={newIngredient}
                            onChange={(e) => setNewIngredient(e.target.value)}
                            placeholder="e.g. hydroquinone, mercury, parabens..."
                            className="flex-1 px-3 py-2 text-sm border border-slate-200 focus:border-slate-950 outline-none rounded-sm"
                        />
                        <datalist id="ingredient-suggestions">
                            {suggestions.map((s) => (
                                <option key={s} value={s} />
                            ))}
                        </datalist>
                        <button
                            type="submit"
                            data-testid="add-ingredient-btn"
                            className="px-4 py-2 text-xs font-mono bg-slate-950 text-white hover:bg-slate-800 inline-flex items-center gap-1 rounded-sm"
                        >
                            <Plus size={12} /> ADD
                        </button>
                    </form>
                    <div className="p-5 flex flex-wrap gap-2 min-h-[120px]" data-testid="ingredients-chips">
                        {wl.ingredients.length === 0 ? (
                            <p className="font-mono text-xs uppercase tracking-widest text-slate-400">
                                Quick picks →
                            </p>
                        ) : (
                            wl.ingredients.map((i) => (
                                <Chip key={i} value={i} onRemove={() => removeIngredient(i)} testid={`chip-ingredient-${i}`} variant="amber" />
                            ))
                        )}
                    </div>
                    {wl.ingredients.length === 0 && (
                        <div className="px-5 pb-5 flex flex-wrap gap-2">
                            {["hydroquinone", "mercury", "parabens", "formaldehyde", "asbestos", "benzene"].map((s) => (
                                <button
                                    key={s}
                                    data-testid={`suggest-${s}`}
                                    onClick={() => addIngredient(s)}
                                    className="px-2 py-1 text-xs font-mono border border-dashed border-slate-300 hover:border-slate-950 text-slate-600 hover:text-slate-950 rounded-sm"
                                >
                                    + {s}
                                </button>
                            ))}
                        </div>
                    )}
                </section>
            </div>
        </Layout>
    );
}

function Chip({ value, onRemove, testid, variant = "default" }) {
    const cls =
        variant === "amber"
            ? "bg-amber-50 border-amber-200 text-amber-900"
            : "bg-slate-100 border-slate-200 text-slate-900";
    return (
        <span
            data-testid={testid}
            className={`inline-flex items-center gap-1.5 pl-3 pr-1.5 py-1 text-xs font-mono border rounded-full ${cls}`}
        >
            {value}
            <button
                onClick={onRemove}
                data-testid={`${testid}-remove`}
                className="h-4 w-4 inline-flex items-center justify-center hover:bg-slate-950 hover:text-white rounded-full"
                aria-label={`Remove ${value}`}
            >
                <X size={10} />
            </button>
        </span>
    );
}
