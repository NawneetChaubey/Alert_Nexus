import React from "react";
import "./App.css";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Toaster } from "sonner";
import { AuthProvider } from "./contexts/AuthContext";
import ProtectedRoute from "./components/ProtectedRoute";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Alerts from "./pages/Alerts";
import Recalls from "./pages/Recalls";
import RecallDetail from "./pages/RecallDetail";
import Watchlist from "./pages/Watchlist";
import Compliance from "./pages/Compliance";
import { GoogleOAuthProvider } from "@react-oauth/google";

function AppRouter() {
    return (
        <Routes>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/login" element={<Login />} />
            <Route
                path="/dashboard"
                element={
                    <ProtectedRoute>
                        <Dashboard />
                    </ProtectedRoute>
                }
            />
            <Route
                path="/alerts"
                element={
                    <ProtectedRoute>
                        <Alerts />
                    </ProtectedRoute>
                }
            />
            <Route
                path="/recalls"
                element={
                    <ProtectedRoute>
                        <Recalls />
                    </ProtectedRoute>
                }
            />
            <Route
                path="/recalls/:id"
                element={
                    <ProtectedRoute>
                        <RecallDetail />
                    </ProtectedRoute>
                }
            />
            <Route
                path="/watchlist"
                element={
                    <ProtectedRoute>
                        <Watchlist />
                    </ProtectedRoute>
                }
            />
            <Route
                path="/compliance"
                element={
                    <ProtectedRoute>
                        <Compliance />
                    </ProtectedRoute>
                }
            />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
    );
}

function App() {
    const clientId = process.env.REACT_APP_GOOGLE_CLIENT_ID || "placeholder-client-id.apps.googleusercontent.com";
    return (
        <GoogleOAuthProvider clientId={clientId}>
            <AuthProvider>
                <BrowserRouter>
                    <AppRouter />
                    <Toaster position="top-right" />
                </BrowserRouter>
            </AuthProvider>
        </GoogleOAuthProvider>
    );
}

export default App;
