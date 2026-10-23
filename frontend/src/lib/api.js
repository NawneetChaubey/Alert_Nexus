import axios from "axios";

const getBackendUrl = () => {
    if (process.env.REACT_APP_BACKEND_URL) {
        return process.env.REACT_APP_BACKEND_URL;
    }
    const hostname = typeof window !== "undefined" && window.location.hostname ? window.location.hostname : "localhost";
    return `http://${hostname}:8000`;
};

export const API = `${getBackendUrl()}/api`;

export const api = axios.create({
    baseURL: API,
    withCredentials: true,
    headers: { "Content-Type": "application/json" },
});

// Attach bearer token if stored (handles cross-origin localhost cookie restrictions in Chrome/Edge)
api.interceptors.request.use((config) => {
    const token = localStorage.getItem("med_alert_token");
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});
