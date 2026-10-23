import React, { useEffect, useState, useRef } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import Layout from "../components/Layout";
import SeverityBadge from "../components/SeverityBadge";
import ConfidenceMeter from "../components/ConfidenceMeter";
import {
    Search,
    Upload,
    FileSpreadsheet,
    AlertCircle,
    CheckCircle2,
    Loader2,
    X,
    Database,
    ShieldAlert,
} from "lucide-react";
import { toast } from "sonner";

const SEVERITIES = ["", "high", "medium", "low", "unknown"];
const CATEGORIES = ["", "cosmetic", "drug", "device", "food", "unknown"];
const REGIONS = ["", "EU", "US"];
const SOURCES = [
    "",
    "EU Safety Gate",
    "Master Recall List",
    "Product Recalls",
    "Combined Product Recalls",
    "Recall Master",
    "Safety Alerts",
    "NSQ Product Quality Failures",
    "Market Actions",
];

const PAGE = 25;
const MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024; // 50 MB
const ALLOWED_EXTENSIONS = [".csv", ".xlsx", ".xls"];

export default function Recalls() {
    const [items, setItems] = useState([]);
    const [total, setTotal] = useState(0);
    const [skip, setSkip] = useState(0);
    const [q, setQ] = useState("");
    const [severity, setSeverity] = useState("");
    const [category, setCategory] = useState("");
    const [region, setRegion] = useState("");
    const [source, setSource] = useState("");
    const [loading, setLoading] = useState(false);

    // Ingestion modal state
    const [isUploadOpen, setIsUploadOpen] = useState(false);
    const [uploadFile, setUploadFile] = useState(null);
    const [uploadValidation, setUploadValidation] = useState(null); // { valid: bool, error?: string }
    const [uploadState, setUploadState] = useState("idle"); // "idle" | "uploading" | "success" | "partial_success" | "error"
    const [uploadResult, setUploadResult] = useState(null);
    const [uploadError, setUploadError] = useState(null);
    const fileInputRef = useRef(null);
    const loadSeqRef = useRef(0);

    const load = async (overrideSkip = skip, overrideQ = q) => {
        const seq = ++loadSeqRef.current;
        setLoading(true);
        try {
            const params = new URLSearchParams();
            params.set("limit", String(PAGE));
            params.set("skip", String(overrideSkip));
            if (overrideQ) params.set("q", overrideQ);
            if (severity) params.set("severity", severity);
            if (category) params.set("category", category);
            if (region) params.set("region", region);
            if (source) params.set("source", source);
            const { data } = await api.get(`/recalls?${params.toString()}`);
            if (seq !== loadSeqRef.current) return;
            setItems(data.items || []);
            setTotal(data.total || 0);
        } catch (error) {
            if (seq === loadSeqRef.current) {
                console.error("Failed to load recalls:", error);
                toast.error("Failed to load recalls list");
            }
        } finally {
            if (seq === loadSeqRef.current) {
                setLoading(false);
            }
        }
    };

    useEffect(() => {
        load(skip, q);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [skip, severity, category, region, source]);

    const onSearch = (e) => {
        e.preventDefault();
        setSkip(0);
        load(0, q);
    };

    // Client-side file validation
    const validateFile = (file) => {
        if (!file) {
            return { valid: false, error: "No file selected." };
        }
        const name = file.name.toLowerCase();
        const hasValidExt = ALLOWED_EXTENSIONS.some((ext) => name.endsWith(ext));
        if (!hasValidExt) {
            return {
                valid: false,
                error: `Unsupported file type. Supported formats: ${ALLOWED_EXTENSIONS.join(", ")}`,
            };
        }
        if (file.size === 0) {
            return { valid: false, error: "Selected file is empty (0 bytes)." };
        }
        if (file.size > MAX_FILE_SIZE_BYTES) {
            return {
                valid: false,
                error: `File size exceeds the 50 MB limit (${(file.size / (1024 * 1024)).toFixed(1)} MB).`,
            };
        }
        return { valid: true };
    };

    const handleFileChange = (e) => {
        const file = e.target.files?.[0];
        if (file) {
            setUploadFile(file);
            const val = validateFile(file);
            setUploadValidation(val);
            setUploadState("idle");
            setUploadResult(null);
            setUploadError(null);
        }
    };

    const handleStartUpload = async () => {
        if (!uploadFile) return;
        const validation = validateFile(uploadFile);
        if (!validation.valid) {
            setUploadValidation(validation);
            return;
        }

        setUploadState("uploading");
        setUploadError(null);

        const formData = new FormData();
        formData.append("file", uploadFile);

        try {
            const response = await api.post("/ingest/upload", formData, {
                headers: {
                    "Content-Type": "multipart/form-data",
                },
            });
            const data = response.data;
            setUploadResult(data);
            if (data.status === "partial_success") {
                setUploadState("partial_success");
                toast.warning(`Partial success: ${data.normalized || 0} saved to backend, ${data.failed_rows || 0} rows rejected.`);
            } else if (data.status === "failed" || (data.normalized === 0 && (data.raw_rows || 0) > 0)) {
                setUploadState("error");
                setUploadError(data.errors?.[0]?.error || "No valid rows could be imported.");
                toast.error(data.persisted
                    ? "No valid recalls created; the source file and raw rows were saved to the backend"
                    : "Ingestion failed: no usable records found");
            } else {
                setUploadState("success");
                toast.success(`Saved ${data.normalized || 0} recalls to the backend`);
            }
            // Deterministically refresh recall table at skip 0
            setSkip(0);
            load(0, q);
        } catch (error) {
            console.error("Upload error:", error);
            const detail =
                error.response?.data?.detail || error.message || "Failed to process uploaded file";
            setUploadError(detail);
            setUploadState("error");
            toast.error(`Ingestion failed: ${detail}`);
        }
    };

    const handleResetUpload = () => {
        setUploadFile(null);
        setUploadValidation(null);
        setUploadState("idle");
        setUploadResult(null);
        setUploadError(null);
        if (fileInputRef.current) {
            fileInputRef.current.value = "";
        }
    };

    const handleCloseModal = () => {
        setIsUploadOpen(false);
        handleResetUpload();
    };

    const formatBytes = (bytes) => {
        if (!bytes || bytes === 0) return "0 B";
        const k = 1024;
        const sizes = ["B", "KB", "MB", "GB"];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
    };

    return (
        <Layout>
            {/* Header with Title, Stats, and Upload Action */}
            <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 mb-8">
                <div>
                    <p className="font-mono text-[11px] uppercase tracking-widest text-slate-500">Explorer</p>
                    <h2 className="mt-2 font-display font-black tracking-tight text-3xl sm:text-4xl text-slate-950">
                        All recalls
                    </h2>
                </div>
                <div className="flex items-center gap-4">
                    <p className="font-mono text-xs text-slate-500 tabular">
                        {total.toLocaleString()} records
                    </p>
                    <button
                        type="button"
                        data-testid="upload-recalls-btn"
                        onClick={() => setIsUploadOpen(true)}
                        className="flex items-center gap-2 px-3.5 py-2 text-xs font-mono uppercase tracking-wider bg-slate-950 text-white hover:bg-slate-800 rounded-sm border border-slate-950 transition shadow-2xs font-medium"
                    >
                        <Upload size={14} />
                        <span>Upload Recalls</span>
                    </button>
                </div>
            </div>

            {/* Filters */}
            <div className="border border-slate-200 p-4 mb-4 bg-slate-50">
                <form onSubmit={onSearch} className="flex gap-3 items-center">
                    <div className="flex-1 relative">
                        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                        <input
                            data-testid="recalls-search-input"
                            value={q}
                            onChange={(e) => setQ(e.target.value)}
                            placeholder="Search by product, ingredient, or recall reason..."
                            className="w-full pl-9 pr-3 py-2 text-sm bg-white border border-slate-200 hover:border-slate-400 focus:border-slate-950 outline-none rounded-sm transition"
                        />
                    </div>
                    <button
                        type="submit"
                        data-testid="recalls-search-btn"
                        className="px-4 py-2 text-xs font-mono bg-slate-950 text-white hover:bg-slate-800 rounded-sm transition font-medium"
                    >
                        SEARCH
                    </button>
                </form>
                <div className="flex gap-3 mt-3 flex-wrap">
                    <Select
                        label="SEVERITY"
                        value={severity}
                        setValue={(v) => { setSeverity(v); setSkip(0); }}
                        options={SEVERITIES}
                        testid="filter-severity"
                    />
                    <Select
                        label="CATEGORY"
                        value={category}
                        setValue={(v) => { setCategory(v); setSkip(0); }}
                        options={CATEGORIES}
                        testid="filter-category"
                    />
                    <Select
                        label="REGION"
                        value={region}
                        setValue={(v) => { setRegion(v); setSkip(0); }}
                        options={REGIONS}
                        testid="filter-region"
                    />
                    <Select
                        label="SOURCE"
                        value={source}
                        setValue={(v) => { setSource(v); setSkip(0); }}
                        options={SOURCES}
                        testid="filter-source"
                    />
                </div>
            </div>

            {/* Table */}
            <div className="border border-slate-200 overflow-x-auto bg-white" data-testid="recalls-table">
                <div className="min-w-[760px]">
                    <div className="grid grid-cols-12 px-5 py-2.5 border-b border-slate-200 bg-slate-50 text-[10px] font-mono uppercase tracking-widest text-slate-500">
                        <div className="col-span-2">Severity</div>
                        <div className="col-span-4">Product</div>
                        <div className="col-span-2">Category · Region</div>
                        <div className="col-span-2">Source</div>
                        <div className="col-span-2 text-right">Confidence</div>
                    </div>
                    {loading ? (
                        <div className="p-12 text-center font-mono text-xs uppercase tracking-widest text-slate-400">
                            Loading recalls...
                        </div>
                    ) : items.length === 0 ? (
                        <div className="p-12 text-center font-mono text-xs uppercase tracking-widest text-slate-500">
                            No recalls match filters
                        </div>
                    ) : (
                        items.map((r) => (
                            <Link
                                to={`/recalls/${r.recall_id}`}
                                key={r.recall_id}
                                data-testid={`recall-row-${r.recall_id}`}
                                className="grid grid-cols-12 px-5 py-3 items-center border-b border-slate-100 hover:bg-slate-50/80 transition"
                            >
                                <div className="col-span-2">
                                    <SeverityBadge severity={r.severity} size="sm" />
                                </div>
                                <div className="col-span-4 pr-2">
                                    <p className="text-sm text-slate-900 font-medium truncate">{r.product_name}</p>
                                    <p className="text-[11px] text-slate-500 truncate">{r.recall_reason}</p>
                                </div>
                                <div className="col-span-2 text-xs font-mono text-slate-700">
                                    <div className="uppercase">{r.category}</div>
                                    <div className="text-slate-500">{r.region}</div>
                                </div>
                                <div className="col-span-2 text-xs font-mono text-slate-600 truncate">
                                    {r.source}
                                </div>
                                <div className="col-span-2 flex justify-end">
                                    <ConfidenceMeter value={r.confidence_score} />
                                </div>
                            </Link>
                        ))
                    )}
                </div>
            </div>

            {/* Pagination */}
            <div className="flex items-center justify-between mt-4 font-mono text-xs text-slate-600">
                <span>
                    {total === 0 ? 0 : skip + 1}–{Math.min(total, skip + items.length)} of {total.toLocaleString()}
                </span>
                <div className="flex gap-2">
                    <button
                        data-testid="prev-page-btn"
                        onClick={() => setSkip(Math.max(0, skip - PAGE))}
                        disabled={skip === 0}
                        className="px-3 py-1.5 border border-slate-200 disabled:opacity-40 hover:border-slate-950 rounded-sm transition"
                    >
                        ← Prev
                    </button>
                    <button
                        data-testid="next-page-btn"
                        onClick={() => setSkip(skip + PAGE)}
                        disabled={skip + PAGE >= total}
                        className="px-3 py-1.5 border border-slate-200 disabled:opacity-40 hover:border-slate-950 rounded-sm transition"
                    >
                        Next →
                    </button>
                </div>
            </div>

            {/* Ingestion Modal / Drawer */}
            {isUploadOpen && (
                <div
                    data-testid="upload-modal"
                    className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/60 backdrop-blur-xs"
                >
                    <div className="bg-white border border-slate-300 w-full max-w-lg shadow-2xl rounded-sm overflow-hidden flex flex-col">
                        {/* Modal Header */}
                        <div className="p-5 border-b border-slate-200 flex items-center justify-between bg-slate-50">
                            <div>
                                <div className="flex items-center gap-2">
                                    <Database size={16} className="text-slate-700" />
                                    <h3 className="font-display font-black text-lg text-slate-950">
                                        Import Recall Dataset
                                    </h3>
                                </div>
                                <p className="mt-1 text-xs text-slate-500 font-mono">
                                    CSV & Excel Ingestion Pipeline
                                </p>
                            </div>
                            <button
                                type="button"
                                data-testid="close-upload-modal-btn"
                                onClick={handleCloseModal}
                                disabled={uploadState === "uploading"}
                                className="p-1 text-slate-400 hover:text-slate-950 rounded-sm transition"
                            >
                                <X size={18} />
                            </button>
                        </div>

                        {/* Modal Body */}
                        <div className="p-6 space-y-5">
                            {uploadState === "idle" && (
                                <>
                                    <div
                                        onClick={() => fileInputRef.current?.click()}
                                        className="border-2 border-dashed border-slate-300 hover:border-slate-900 bg-slate-50/50 p-6 text-center cursor-pointer transition rounded-sm"
                                    >
                                        <input
                                            ref={fileInputRef}
                                            type="file"
                                            accept=".csv,.xlsx,.xls"
                                            onChange={handleFileChange}
                                            className="hidden"
                                            data-testid="recall-file-input"
                                        />
                                        <div className="mx-auto w-10 h-10 bg-slate-100 border border-slate-200 flex items-center justify-center text-slate-600 rounded-full mb-3">
                                            <FileSpreadsheet size={20} />
                                        </div>
                                        <p className="text-sm font-medium text-slate-900">
                                            Click to browse or drop recall dataset
                                        </p>
                                        <p className="mt-1 text-xs text-slate-500 font-mono">
                                            Supported: .csv, .xlsx, .xls (Max 50 MB)
                                        </p>
                                    </div>

                                    {uploadFile && (
                                        <div className="p-3 bg-slate-50 border border-slate-200 rounded-sm flex items-center justify-between">
                                            <div className="min-w-0 pr-2">
                                                <p className="text-xs font-mono font-medium text-slate-900 truncate">
                                                    {uploadFile.name}
                                                </p>
                                                <p className="text-[11px] font-mono text-slate-500">
                                                    {formatBytes(uploadFile.size)}
                                                </p>
                                            </div>
                                            {uploadValidation?.valid ? (
                                                <span className="px-2 py-0.5 bg-green-100 text-green-800 text-[10px] font-mono rounded shrink-0">
                                                    VALID
                                                </span>
                                            ) : (
                                                <span className="px-2 py-0.5 bg-red-100 text-red-800 text-[10px] font-mono rounded shrink-0">
                                                    INVALID
                                                </span>
                                            )}
                                        </div>
                                    )}

                                    {uploadValidation && !uploadValidation.valid && (
                                        <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 text-red-800 text-xs font-mono rounded-sm">
                                            <AlertCircle size={15} className="shrink-0" />
                                            <span>{uploadValidation.error}</span>
                                        </div>
                                    )}
                                </>
                            )}

                            {uploadState === "uploading" && (
                                <div className="py-8 text-center space-y-3">
                                    <div className="inline-flex p-3 bg-slate-100 rounded-full animate-spin text-slate-900">
                                        <Loader2 size={24} />
                                    </div>
                                    <h4 className="font-display font-bold text-base text-slate-950">
                                        Processing Dataset...
                                    </h4>
                                    <p className="text-xs font-mono text-slate-500 max-w-sm mx-auto">
                                        Parsing raw rows, mapping canonical columns, inferring missing attributes, and checking watchlists.
                                    </p>
                                </div>
                            )}

                            {/* Success or Partial Success State */}
                            {(uploadState === "success" || uploadState === "partial_success") && uploadResult && (
                                <div className="space-y-4">
                                    <div
                                        className={`flex items-center gap-2 p-3 border rounded-sm ${
                                            uploadState === "partial_success"
                                                ? "bg-amber-50 border-amber-200 text-amber-900"
                                                : "bg-green-50 border-green-200 text-green-800"
                                        }`}
                                    >
                                        <CheckCircle2 size={18} className="shrink-0" />
                                        <span className="text-xs font-mono font-medium">
                                            {uploadState === "partial_success"
                                                ? `Partial ingestion: ${uploadResult.normalized} saved to backend, ${uploadResult.failed_rows} rejected`
                                                : uploadResult.persisted
                                                    ? "Saved to backend successfully"
                                                    : "Ingestion completed successfully"}
                                        </span>
                                    </div>

                                    <div className="grid grid-cols-2 gap-3 p-4 bg-slate-50 border border-slate-200 rounded-sm font-mono text-xs">
                                        <div>
                                            <span className="text-slate-500 text-[10px] uppercase block">Source File</span>
                                            <span className="font-bold text-slate-900 truncate block">
                                                {uploadResult.source_file}
                                            </span>
                                        </div>
                                        <div>
                                            <span className="text-slate-500 text-[10px] uppercase block">Raw Rows</span>
                                            <span className="font-bold text-slate-900">
                                                {uploadResult.raw_rows}
                                            </span>
                                        </div>
                                        <div>
                                            <span className="text-slate-500 text-[10px] uppercase block">Normalized</span>
                                            <span className="font-bold text-green-700">
                                                {uploadResult.normalized}
                                            </span>
                                        </div>
                                        <div>
                                            <span className="text-slate-500 text-[10px] uppercase block">Rejected Rows</span>
                                            <span className={`font-bold ${uploadResult.failed_rows > 0 ? "text-amber-700" : "text-slate-500"}`}>
                                                {uploadResult.failed_rows || 0}
                                            </span>
                                        </div>
                                        <div>
                                            <span className="text-slate-500 text-[10px] uppercase block">Lineage Logged</span>
                                            <span className="font-bold text-slate-900">
                                                {uploadResult.lineage_rows}
                                            </span>
                                        </div>
                                        <div>
                                            <span className="text-slate-500 text-[10px] uppercase block">Alerts Created</span>
                                            <span className="font-bold text-red-600">
                                                {uploadResult.alerts_created}
                                            </span>
                                        </div>
                                    </div>

                                    {/* Row Error Details on Partial Success */}
                                    {uploadResult.errors?.length > 0 && (
                                        <div className="p-3 bg-amber-50/60 border border-amber-200 rounded-sm">
                                            <p className="text-[11px] font-mono font-bold text-amber-900 mb-2 uppercase">
                                                Row Rejection Details ({uploadResult.errors.length}):
                                            </p>
                                            <div className="max-h-28 overflow-y-auto space-y-1 font-mono text-[10px] text-amber-800">
                                                {uploadResult.errors.map((err, idx) => (
                                                    <div key={idx} className="flex gap-2">
                                                        <span className="font-bold shrink-0">Row {err.row}:</span>
                                                        <span className="truncate">{err.error}</span>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                </div>
                            )}

                            {uploadState === "error" && (
                                <div className="space-y-3">
                                    <div className="flex items-start gap-2.5 p-3.5 bg-red-50 border border-red-200 text-red-900 rounded-sm">
                                        <AlertCircle size={18} className="shrink-0 mt-0.5" />
                                        <div className="text-xs">
                                            <p className="font-bold">Ingestion failed</p>
                                            <p className="mt-1 font-mono text-[11px] text-red-700">{uploadError}</p>
                                            {uploadResult?.persisted && (
                                                <p className="mt-2 text-[11px] text-slate-700">
                                                    The source file and raw rows were saved to the backend, but no recall could be normalized.
                                                </p>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>

                        {/* Modal Footer */}
                        <div className="p-4 border-t border-slate-200 bg-slate-50 flex items-center justify-end gap-3">
                            {uploadState === "idle" && (
                                <>
                                    <button
                                        type="button"
                                        onClick={handleCloseModal}
                                        className="px-3 py-2 text-xs font-mono text-slate-600 hover:text-slate-950 border border-slate-200 bg-white rounded-sm"
                                    >
                                        CANCEL
                                    </button>
                                    <button
                                        type="button"
                                        data-testid="start-upload-btn"
                                        onClick={handleStartUpload}
                                        disabled={!uploadFile || !uploadValidation?.valid}
                                        className="px-4 py-2 text-xs font-mono uppercase tracking-wider bg-slate-950 text-white hover:bg-slate-800 disabled:opacity-40 rounded-sm transition font-medium"
                                    >
                                        START INGESTION
                                    </button>
                                </>
                            )}

                            {uploadState === "uploading" && (
                                <button
                                    type="button"
                                    disabled
                                    className="px-4 py-2 text-xs font-mono bg-slate-400 text-white rounded-sm cursor-not-allowed flex items-center gap-2"
                                >
                                    <Loader2 size={13} className="animate-spin" />
                                    <span>INGESTING...</span>
                                </button>
                            )}

                            {(uploadState === "success" || uploadState === "partial_success") && (
                                <>
                                    <button
                                        type="button"
                                        onClick={handleResetUpload}
                                        className="px-3 py-2 text-xs font-mono text-slate-600 hover:text-slate-950 border border-slate-200 bg-white rounded-sm"
                                    >
                                        UPLOAD ANOTHER
                                    </button>
                                    <button
                                        type="button"
                                        onClick={handleCloseModal}
                                        className="px-4 py-2 text-xs font-mono uppercase bg-slate-950 text-white hover:bg-slate-800 rounded-sm font-medium"
                                    >
                                        DONE
                                    </button>
                                </>
                            )}

                            {uploadState === "error" && (
                                <>
                                    <button
                                        type="button"
                                        onClick={handleResetUpload}
                                        className="px-3 py-2 text-xs font-mono text-slate-600 hover:text-slate-950 border border-slate-200 bg-white rounded-sm"
                                    >
                                        TRY DIFFERENT FILE
                                    </button>
                                    <button
                                        type="button"
                                        onClick={handleStartUpload}
                                        className="px-4 py-2 text-xs font-mono uppercase bg-slate-950 text-white hover:bg-slate-800 rounded-sm font-medium"
                                    >
                                        RETRY
                                    </button>
                                </>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </Layout>
    );
}

function Select({ label, value, setValue, options, testid }) {
    return (
        <div className="flex items-center gap-2">
            <span className="font-mono text-[10px] uppercase tracking-widest text-slate-500">{label}</span>
            <select
                data-testid={testid}
                value={value}
                onChange={(e) => setValue(e.target.value)}
                className="px-2 py-1.5 text-xs font-mono bg-white border border-slate-200 hover:border-slate-950 outline-none rounded-sm transition"
            >
                {options.map((o) => (
                    <option key={o} value={o}>
                        {o || "all"}
                    </option>
                ))}
            </select>
        </div>
    );
}
