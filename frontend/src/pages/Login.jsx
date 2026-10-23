import React from "react";
import { useAuth } from "../contexts/AuthContext";
import { Navigate, useNavigate } from "react-router-dom";
import { GoogleLogin } from "@react-oauth/google";
import { api } from "../lib/api";
import { toast } from "sonner";

export default function Login() {
    const { user, loading, refresh } = useAuth();
    const navigate = useNavigate();

    if (!loading && user) return <Navigate to="/dashboard" replace />;

    const handleGoogleSuccess = async (credentialResponse) => {
        try {
            const { data } = await api.post("/auth/session", { id_token: credentialResponse.credential });
            if (data?.session_token) {
                localStorage.setItem("med_alert_token", data.session_token);
            }
            await refresh();
            navigate("/dashboard");
        } catch (error) {
            toast.error("Authentication failed. Please try again.");
            console.error(error);
        }
    };

    const handleGoogleError = () => {
        toast.error("Google Sign-In failed.");
    };

    const handleDemoLogin = async () => {
        try {
            const { data } = await api.post("/auth/demo-session");
            if (data?.session_token) {
                localStorage.setItem("med_alert_token", data.session_token);
            }
            const loggedInUser = await refresh();
            if (loggedInUser) {
                toast.success("Logged in as Demo User");
                navigate("/dashboard");
            } else {
                toast.error("Failed to verify demo session. Is the backend running?");
            }
        } catch (error) {
            const detail = error.response?.data?.detail || error.message || "Failed to connect to server";
            toast.error(`Demo login failed: ${detail}`);
            console.error("Demo login error:", error);
        }
    };

    return (
        <div className="min-h-screen grid grid-cols-1 md:grid-cols-2 bg-white" data-testid="login-page">
            {/* Left: content */}
            <div className="flex flex-col justify-between p-10 md:p-14 border-r border-slate-200">
                <div className="flex items-center gap-2">
                    <div className="h-2 w-2 bg-red-500 pulse-dot" />
                    <span className="font-mono text-[11px] tracking-[0.3em] text-slate-500">
                        LIVE · REGULATORY SIGNAL
                    </span>
                </div>

                <div className="max-w-xl">
                    <p className="font-mono text-xs uppercase tracking-widest text-slate-500 mb-6">
                        [01] Recall Nexus
                    </p>
                    <h1 className="font-display font-black tracking-tight text-5xl md:text-6xl leading-[0.95] text-slate-950">
                        When the<br />
                        world issues<br />
                        a <span className="bg-red-600 text-white px-2">recall</span>,
                        <br />
                        you know<br />first.
                    </h1>
                    <p className="mt-8 text-base text-slate-600 leading-relaxed max-w-lg">
                        Aggregating fragmented FDA, EU Safety Gate and third-country regulatory data into a single,
                        confidence-scored feed. Watch the products and ingredients you care about —
                        we reconcile inconsistent sources so you don&apos;t have to.
                    </p>

                    <div className="mt-10 flex flex-wrap items-center gap-4">
                        <GoogleLogin
                            onSuccess={handleGoogleSuccess}
                            onError={handleGoogleError}
                            theme="filled_black"
                            size="large"
                            text="continue_with"
                            shape="rectangular"
                        />
                        <button
                            type="button"
                            onClick={handleDemoLogin}
                            data-testid="demo-login-btn"
                            className="font-mono text-xs uppercase tracking-wider px-5 py-2.5 bg-slate-900 text-white hover:bg-slate-800 transition font-medium border border-slate-900"
                        >
                            Quick Demo Access →
                        </button>
                    </div>
                </div>

                <div className="grid grid-cols-3 gap-6 pt-10 border-t border-slate-200">
                    <Stat label="Sources" value="4" />
                    <Stat label="Regions" value="24+" />
                    <Stat label="Records ingested" value="4,750" />
                </div>
            </div>

            {/* Right: hero visual */}
            <div className="relative hidden md:block overflow-hidden bg-slate-950">
                <img
                    src={`${process.env.PUBLIC_URL || ""}/15e8835d7f038df3eafb5878f98de1c2d68d389692c8561ddeedd909c02a5e9b.png`}
                    alt="Regulatory signal visualization"
                    className="absolute inset-0 w-full h-full object-cover opacity-80"
                />
                <div className="absolute inset-0 bg-gradient-to-br from-slate-950/60 via-transparent to-slate-950/80" />
                <div className="relative z-10 h-full flex flex-col justify-between p-10 text-slate-100">
                    <div className="flex items-center justify-between">
                        <p className="font-mono text-[11px] tracking-widest text-slate-400">
                            STREAM 01 / GLOBAL FEED
                        </p>
                        <div className="flex gap-1 font-mono text-[10px] text-slate-500">
                            <span className="px-2 py-0.5 border border-slate-700">FDA</span>
                            <span className="px-2 py-0.5 border border-slate-700">EU</span>
                            <span className="px-2 py-0.5 border border-slate-700">WHO</span>
                        </div>
                    </div>
                    <div>
                        <p className="font-mono text-[11px] tracking-widest text-red-400 mb-4">
                            &gt; LATEST RECALL · 08:57 UTC
                        </p>
                        <blockquote className="font-display text-2xl leading-snug max-w-md">
                            &ldquo;Serious chemical risk: contains <span className="text-red-400">hydroquinone</span>,
                            prohibited in cosmetics.&rdquo;
                        </blockquote>
                        <p className="mt-3 font-mono text-[11px] text-slate-400">
                            EU_SAFETY_GATE · CONFIDENCE 0.80
                        </p>
                    </div>
                </div>
            </div>
        </div>
    );
}

function Stat({ label, value }) {
    return (
        <div>
            <p className="font-display text-3xl font-bold text-slate-950 tabular">{value}</p>
            <p className="mt-1 font-mono text-[10px] tracking-widest uppercase text-slate-500">{label}</p>
        </div>
    );
}
