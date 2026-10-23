import React from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { LayoutGrid, BellRing, ListChecks, ShieldAlert, BookOpenCheck, Database, LogOut } from "lucide-react";

const NAV = [
    { to: "/dashboard", label: "Overview", icon: LayoutGrid, testid: "nav-dashboard" },
    { to: "/alerts", label: "Alerts", icon: BellRing, testid: "nav-alerts" },
    { to: "/recalls", label: "Recalls", icon: Database, testid: "nav-recalls" },
    { to: "/watchlist", label: "Watchlist", icon: ListChecks, testid: "nav-watchlist" },
    { to: "/compliance", label: "Compliance", icon: ShieldAlert, testid: "nav-compliance" },
];

export default function Layout({ children }) {
    const { user, logout } = useAuth();
    const navigate = useNavigate();

    const handleLogout = async () => {
        await logout();
        navigate("/login");
    };

    return (
        <div className="min-h-screen flex bg-white text-slate-950">
            {/* Sidebar */}
            <aside className="w-64 shrink-0 bg-slate-950 text-slate-200 border-r border-slate-800 flex flex-col">
                <div className="p-6 border-b border-slate-800">
                    <div className="flex items-center gap-2">
                        <div className="h-2 w-2 bg-red-500 pulse-dot" />
                        <span className="font-mono text-[10px] tracking-[0.25em] text-slate-400">LIVE</span>
                    </div>
                    <h1 className="mt-3 font-display font-black tracking-tight text-xl leading-tight">
                        RECALL<br />NEXUS
                    </h1>
                    <p className="mt-1 text-[11px] text-slate-500 font-mono">
                        v0.1 · REGULATORY INTEL
                    </p>
                </div>
                <nav className="flex-1 p-3 space-y-0.5">
                    {NAV.map((item) => (
                        <NavLink
                            key={item.to}
                            to={item.to}
                            data-testid={item.testid}
                            className={({ isActive }) =>
                                `flex items-center gap-3 px-3 py-2.5 text-sm rounded-sm border ${
                                    isActive
                                        ? "bg-slate-900 border-slate-700 text-white"
                                        : "border-transparent text-slate-300 hover:bg-slate-900 hover:border-slate-800 hover:text-white"
                                }`
                            }
                        >
                            <item.icon size={16} strokeWidth={1.75} />
                            <span className="font-medium">{item.label}</span>
                        </NavLink>
                    ))}
                </nav>
                <div className="p-3 border-t border-slate-800 space-y-2">
                    <div className="flex items-center gap-3 px-2">
                        {user?.picture ? (
                            <img
                                src={user.picture}
                                alt=""
                                className="h-8 w-8 object-cover border border-slate-700 rounded-sm"
                            />
                        ) : (
                            <div className="h-8 w-8 bg-slate-800 border border-slate-700 flex items-center justify-center text-xs font-mono rounded-sm">
                                {user?.name?.[0] || "U"}
                            </div>
                        )}
                        <div className="min-w-0">
                            <p className="text-xs text-white truncate">{user?.name}</p>
                            <p className="text-[10px] font-mono text-slate-500 truncate">{user?.email}</p>
                        </div>
                    </div>
                    <button
                        data-testid="logout-btn"
                        onClick={handleLogout}
                        className="w-full flex items-center gap-2 px-3 py-2 text-xs text-slate-300 hover:bg-slate-900 hover:text-white border border-slate-800 rounded-sm"
                    >
                        <LogOut size={14} />
                        SIGN OUT
                    </button>
                </div>
            </aside>

            <main className="flex-1 min-w-0">
                <div className="border-b border-slate-200 bg-slate-50">
                    <div className="px-8 py-3 flex items-center justify-between">
                        <div className="flex items-center gap-3 text-[11px] font-mono uppercase tracking-widest text-slate-500">
                            <BookOpenCheck size={14} />
                            <span>Global Recall & Compliance Platform</span>
                        </div>
                        <div className="text-[11px] font-mono text-slate-500">
                            {new Date().toLocaleDateString("en-GB", {
                                year: "numeric",
                                month: "short",
                                day: "2-digit",
                            })}
                        </div>
                    </div>
                </div>
                <div className="p-8">{children}</div>
            </main>
        </div>
    );
}
