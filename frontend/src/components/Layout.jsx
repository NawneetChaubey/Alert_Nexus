import React, { useState, useEffect } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import {
    LayoutGrid,
    BellRing,
    ListChecks,
    ShieldAlert,
    BookOpenCheck,
    Database,
    LogOut,
    Menu,
    X,
} from "lucide-react";
import bgImage from "../assets/Elegant Abstract Waves with Dotted World Map.png";

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
    const [isOpen, setIsOpen] = useState(false);

    const handleLogout = async () => {
        await logout();
        navigate("/login");
    };

    // Close drawer on Escape key press
    useEffect(() => {
        const handleKeyDown = (e) => {
            if (e.key === "Escape" && isOpen) {
                setIsOpen(false);
            }
        };
        window.addEventListener("keydown", handleKeyDown);
        return () => window.removeEventListener("keydown", handleKeyDown);
    }, [isOpen]);

    // Prevent background scroll when overlay drawer is open
    useEffect(() => {
        if (isOpen) {
            document.body.style.overflow = "hidden";
        } else {
            document.body.style.overflow = "";
        }
        return () => {
            document.body.style.overflow = "";
        };
    }, [isOpen]);

    return (
        <div
            className="min-h-screen flex flex-col text-slate-900 bg-cover bg-fixed bg-no-repeat bg-top"
            style={{
                backgroundColor: "#F2F5FA",
                backgroundImage: `linear-gradient(rgba(242, 245, 250, 0.35), rgba(242, 245, 250, 0.50)), url("${bgImage}")`,
            }}
        >
            {/* Top Navigation Bar with Hamburger */}
            <header className="border-b border-[#DCE4EF] bg-white/95 backdrop-blur-md sticky top-0 z-30 shadow-2xs">
                <div className="px-4 sm:px-8 py-3 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <button
                            type="button"
                            data-testid="hamburger-btn"
                            aria-label="Toggle navigation drawer"
                            aria-expanded={isOpen}
                            aria-controls="navigation-drawer"
                            onClick={() => setIsOpen(!isOpen)}
                            className="p-1.5 -ml-1 text-slate-700 hover:text-slate-950 hover:bg-slate-100 rounded-md focus:outline-none focus:ring-2 focus:ring-slate-900 transition"
                        >
                            <Menu size={20} strokeWidth={2} />
                        </button>

                        <div className="flex items-center gap-2.5">
                            <div className="h-2 w-2 bg-red-600 rounded-full pulse-dot" />
                            <span className="font-display font-black tracking-tight text-base sm:text-lg text-slate-950">
                                RECALL NEXUS
                            </span>
                        </div>

                        <div className="hidden md:flex items-center gap-2 pl-3 ml-2 border-l border-[#DCE4EF] text-[11px] font-mono uppercase tracking-widest text-slate-500">
                            <BookOpenCheck size={14} />
                            <span>Global Recall & Compliance Platform</span>
                        </div>
                    </div>

                    <div className="flex items-center gap-4 text-[11px] font-mono text-slate-500">
                        <span className="hidden sm:inline">
                            {new Date().toLocaleDateString("en-GB", {
                                year: "numeric",
                                month: "short",
                                day: "2-digit",
                            })}
                        </span>
                        {user && (
                            <div className="flex items-center gap-2 pl-3 border-l border-[#DCE4EF]">
                                {user.picture ? (
                                    <img
                                        src={user.picture}
                                        alt=""
                                        className="h-6 w-6 object-cover border border-slate-300 rounded-sm"
                                    />
                                ) : (
                                    <div className="h-6 w-6 bg-slate-200 border border-slate-300 flex items-center justify-center text-[10px] font-mono rounded-sm text-slate-700">
                                        {user.name?.[0] || "U"}
                                    </div>
                                )}
                                <span className="hidden sm:inline text-xs font-sans text-slate-700 font-medium truncate max-w-[120px]">
                                    {user.name}
                                </span>
                            </div>
                        )}
                    </div>
                </div>
            </header>

            {/* Backdrop Overlay */}
            {isOpen && (
                <div
                    data-testid="drawer-backdrop"
                    onClick={() => setIsOpen(false)}
                    className="fixed inset-0 bg-slate-950/60 backdrop-blur-xs z-40 transition-opacity"
                    aria-hidden="true"
                />
            )}

            {/* Navigation Drawer */}
            <aside
                id="navigation-drawer"
                data-testid="nav-drawer"
                aria-label="Navigation Drawer"
                aria-hidden={!isOpen}
                className={`fixed inset-y-0 left-0 z-50 w-72 max-w-[85vw] bg-slate-950 text-slate-200 border-r border-slate-800 flex flex-col shadow-2xl transition-transform duration-200 ease-in-out ${
                    isOpen ? "translate-x-0" : "-translate-x-full pointer-events-none"
                }`}
            >
                {/* Drawer Header */}
                <div className="p-5 border-b border-slate-800 flex items-start justify-between">
                    <div>
                        <div className="flex items-center gap-2">
                            <div className="h-2 w-2 bg-red-500 pulse-dot" />
                            <span className="font-mono text-[10px] tracking-[0.25em] text-slate-400">LIVE</span>
                        </div>
                        <h1 className="mt-2 font-display font-black tracking-tight text-xl leading-tight text-white">
                            RECALL<br />NEXUS
                        </h1>
                        <p className="mt-1 text-[11px] text-slate-500 font-mono">
                            v0.1 · REGULATORY INTEL
                        </p>
                    </div>
                    <button
                        type="button"
                        data-testid="close-drawer-btn"
                        aria-label="Close navigation drawer"
                        onClick={() => setIsOpen(false)}
                        className="p-1.5 text-slate-400 hover:text-white hover:bg-slate-900 rounded-sm transition focus:outline-none"
                    >
                        <X size={18} />
                    </button>
                </div>

                {/* Nav Links (Scrollable independently if tall) */}
                <nav className="flex-1 overflow-y-auto p-3 space-y-1">
                    {NAV.map((item) => (
                        <NavLink
                            key={item.to}
                            to={item.to}
                            data-testid={item.testid}
                            onClick={() => setIsOpen(false)}
                            className={({ isActive }) =>
                                `flex items-center gap-3 px-3 py-2.5 text-sm rounded-sm border transition ${
                                    isActive
                                        ? "bg-slate-900 border-slate-700 text-white font-medium"
                                        : "border-transparent text-slate-300 hover:bg-slate-900 hover:border-slate-800 hover:text-white"
                                }`
                            }
                        >
                            <item.icon size={16} strokeWidth={1.75} />
                            <span>{item.label}</span>
                        </NavLink>
                    ))}
                </nav>

                {/* Sign-Out & User Section Anchored at Bottom */}
                <div className="mt-auto p-4 border-t border-slate-800 space-y-3 shrink-0 bg-slate-950">
                    <div className="flex items-center gap-3 px-1">
                        {user?.picture ? (
                            <img
                                src={user.picture}
                                alt=""
                                className="h-8 w-8 object-cover border border-slate-700 rounded-sm shrink-0"
                            />
                        ) : (
                            <div className="h-8 w-8 bg-slate-800 border border-slate-700 flex items-center justify-center text-xs font-mono rounded-sm text-slate-200 shrink-0">
                                {user?.name?.[0] || "U"}
                            </div>
                        )}
                        <div className="min-w-0 flex-1">
                            <p className="text-xs text-white font-medium truncate">{user?.name || "Demo User"}</p>
                            <p className="text-[10px] font-mono text-slate-500 truncate">{user?.email || "user@med-alert.local"}</p>
                        </div>
                    </div>
                    <button
                        type="button"
                        data-testid="logout-btn"
                        onClick={handleLogout}
                        className="w-full flex items-center justify-center gap-2 px-3 py-2.5 text-xs font-mono uppercase tracking-wider text-slate-300 hover:bg-red-950/40 hover:text-red-400 hover:border-red-900 border border-slate-800 rounded-sm transition font-medium"
                    >
                        <LogOut size={14} />
                        <span>SIGN OUT</span>
                    </button>
                </div>
            </aside>

            {/* Main Content Area (Full Width) */}
            <main className="flex-1 min-w-0 w-full p-4 sm:p-8">
                {children}
            </main>
        </div>
    );
}
