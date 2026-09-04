import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  Activity, ArrowUpRight, BarChart3, Bell, Bot, CheckCircle2, ChevronDown, ChevronRight,
  Download, Eye, FileBarChart2, FileText, Globe2, LayoutDashboard, Loader2, MessageSquareText,
  MoreHorizontal, Play, RefreshCw, Search, Send, ShieldCheck, Sparkles, Store, UploadCloud,
  X, Zap,
} from "lucide-react";

/* ── brand ──────────────────────────────────────────────────────────────── */
const C = {
  navy: "#02355A", blue: "#3680CE", darkBlue: "#155798", lightBlue: "#A6CBF0",
  offWhite: "#F7F5F3", yellow: "#EB9F0A", green: "#5D910D",
};

const navItems = [
  ["home", "Command Center", LayoutDashboard],
  ["workspace", "Market Workspace", Globe2],
  ["outputs", "Output Studio", FileBarChart2],
  ["agents", "Agent Hub", Sparkles],
  ["approvals", "Approval Center", ShieldCheck],
  ["monitor", "Monitoring Hub", Activity],
];

const MARKETS = ["India", "Mexico", "Brazil"];

/* 7 pipeline steps — labels mirror gui/steps.py STEP_META */
const STEPS = [
  [1, "Load data"],
  [2, "Data quality checks"],
  [3, "Prioritization"],
  [4, "Segmentation"],
  [5, "MSL generation"],
  [6, "Generate outputs"],
  [7, "Space allocation"],
];

/* Agent Hub — one card per pipeline agent (agents/*.py) */
const AGENTS = [
  ["Data Quality Agent", "dq_agent", [2], CheckCircle2, C.green],
  ["Prioritization Agent", "prioritization_agent", [3], BarChart3, C.blue],
  ["Segmentation Agent", "segmentation_agent", [4], Store, C.darkBlue],
  ["MSL Agent", "msl_generator", [5], Zap, C.yellow],
  ["Output Agent", "output_agent", [6], FileText, C.blue],
  ["Space Allocation Agent", "space_allocation_agent", [7], LayoutDashboard, C.darkBlue],
];

/* ── api helpers ────────────────────────────────────────────────────────── */
const api = {
  async get(path) {
    const r = await fetch(path);
    if (!r.ok) throw new Error(`${r.status} ${path}`);
    return r.json();
  },
  async post(path, body) {
    const r = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(data.detail || `${r.status} ${path}`);
    return data;
  },
  async upload(path, file) {
    const fd = new FormData();
    fd.append("file", file);
    const r = await fetch(path, { method: "POST", body: fd });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(data.detail || `${r.status} ${path}`);
    return data;
  },
};

const fmtInt = (n) => (n == null ? "—" : Number(n).toLocaleString("en-IN"));
const fmtRupee = (n) => (n == null ? "—" : "₹" + Math.round(Number(n)).toLocaleString("en-IN"));
const monthKey = (iso) => (iso || "").slice(0, 7);

/* ── data hooks ─────────────────────────────────────────────────────────── */
function useHealth() {
  const [h, setH] = useState(null);
  useEffect(() => { api.get("/api/health").then(setH).catch(() => setH({ status: "down" })); }, []);
  return h;
}

function useRuns() {
  const [runs, setRuns] = useState(null);
  const [err, setErr] = useState(null);
  const refresh = useCallback(() => {
    api.get("/api/runs").then((r) => { setRuns(r); setErr(null); }).catch((e) => setErr(e.message));
  }, []);
  useEffect(() => { refresh(); }, [refresh]);
  return { runs, err, refresh };
}

function useRunDetail(id) {
  const [detail, setDetail] = useState(null);
  useEffect(() => {
    if (!id) { setDetail(null); return; }
    let live = true;
    setDetail(null);
    api.get(`/api/runs/${id}`).then((d) => { if (live) setDetail(d); }).catch(() => {});
    return () => { live = false; };
  }, [id]);
  return detail;
}

/* Live SSE stream of the current pipeline run. Bump `streamKey` to (re)connect. */
function useRunStream(streamKey) {
  const [state, setState] = useState({ status: "idle", steps: {}, logs: [], meta: null, outputDir: null });
  useEffect(() => {
    if (streamKey === 0) return;
    setState({ status: "connecting", steps: {}, logs: [], meta: null, outputDir: null });
    const es = new EventSource("/api/runs/stream");
    es.onmessage = (e) => {
      let ev;
      try { ev = JSON.parse(e.data); } catch { return; }
      setState((s) => {
        if (ev.kind === "idle") { es.close(); return { ...s, status: "idle" }; }
        if (ev.kind === "init") return { ...s, status: "running", meta: ev.meta };
        if (ev.kind === "step") {
          const steps = { ...s.steps };
          if (ev.status === "running") {
            for (const [n] of STEPS) if (n < ev.step && steps[n] !== "done") steps[n] = "done";
          }
          steps[ev.step] = ev.status;
          return { ...s, status: "running", steps };
        }
        if (ev.kind === "log") {
          const line = `${ev.ts}  ${(ev.level || "").padEnd(5)} ${(ev.name || "").padEnd(20)} ${ev.msg}`;
          return { ...s, logs: [...s.logs, line].slice(-400) };
        }
        if (ev.kind === "end") {
          es.close();
          const steps = { ...s.steps };
          if (!ev.error) for (const [n] of STEPS) steps[n] = "done";
          return { ...s, status: ev.error ? "failed" : "done", steps, outputDir: ev.output_dir };
        }
        return s;
      });
    };
    es.onerror = () => { es.close(); setState((s) => (s.status === "running" ? s : { ...s, status: "idle" })); };
    return () => es.close();
  }, [streamKey]);
  return state;
}

/* ── small ui atoms (from the mockup) ───────────────────────────────────── */
const Btn = ({ children, className = "", ...p }) => (
  <button className={`rounded-xl px-3 py-2 text-xs font-semibold disabled:opacity-50 ${className}`} {...p}>
    {children}
  </button>
);
const Card = ({ children, className = "" }) => (
  <div className={`rounded-2xl bg-white shadow-sm ${className}`}>{children}</div>
);
const Tag = ({ children }) => (
  <span className="rounded-full bg-[#A6CBF0]/40 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wide text-[#155798]">
    {children}
  </span>
);

function MiniDeck({ headline, bars, market, takeaway }) {
  const b = bars && bars.length ? bars : [36, 64, 45, 88, 58, 42];
  const max = Math.max(...b, 1);
  const top = b.indexOf(Math.max(...b));
  return (
    <div className="aspect-video rounded-xl bg-white p-5 shadow-lg ring-1 ring-slate-200">
      <p className="text-[9px] font-bold text-[#3680CE]">PERFECT STORE · {(market || "INDIA").toUpperCase()} GT</p>
      <h3 className="mt-1 text-lg font-black leading-tight">
        {headline || "MSL opportunity is concentrated in two priority clusters"}
      </h3>
      <p className="mt-1 text-[9px] text-slate-400">Store-level recommendation output · pipeline run</p>
      <div className="mt-4 grid h-[48%] grid-cols-[1.5fr_1fr] gap-4">
        <div className="flex items-end gap-2 border-b border-l border-slate-300 px-3">
          {b.map((h, i) => (
            <div key={i} className="flex flex-1 flex-col items-center justify-end">
              <div className="w-full rounded-t" style={{ height: `${(h / max) * 100}%`, background: i === top ? C.yellow : C.blue }} />
              <span className="mt-1 text-[7px] text-slate-400">C{i}</span>
            </div>
          ))}
        </div>
        <div className="rounded-lg bg-[#A6CBF0]/30 p-3">
          <p className="text-[8px] font-bold text-[#155798]">KEY TAKEAWAY</p>
          <p className="mt-2 text-[9px] font-semibold">
            {takeaway || "Cluster with the largest incremental distribution opportunity leads the plan."}
          </p>
        </div>
      </div>
      <p className="mt-3 text-[7px] text-slate-400">CONFIDENTIAL</p>
    </div>
  );
}

/* ── stepper (shared by Run progress + the bottom Run status card) ──────── */
function StepPill({ n, label, state }) {
  const dot = state === "done" ? C.green : state === "running" ? C.yellow : state === "failed" ? "#d33" : "#cbd5e1";
  return (
    <div className="flex items-center gap-3 rounded-xl border border-slate-100 px-3 py-2">
      <span className="grid h-6 w-6 place-items-center rounded-full text-[10px] font-bold text-white" style={{ background: dot }}>
        {state === "running" ? <Loader2 size={12} className="animate-spin" /> : n}
      </span>
      <span className="text-xs font-semibold">{label}</span>
      <span className="ml-auto text-[10px] uppercase tracking-wide text-slate-400">{state || "pending"}</span>
    </div>
  );
}

/* ── new-analysis modal ────────────────────────────────────────────────── */
function NewAnalysisModal({ onClose, onStarted }) {
  const [inbox, setInbox] = useState(null);
  const [file, setFile] = useState("");
  const [sample, setSample] = useState(5000);
  const [useSample, setUseSample] = useState(true);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const uploadRef = useRef(null);

  useEffect(() => {
    api.get("/api/inbox").then((e) => {
      setInbox(e);
      const first = e.find((x) => x.kind === "dataset") || e[0];
      if (first) setFile(first.name);
    }).catch((e) => setErr(e.message));
  }, []);

  const start = async () => {
    setBusy(true); setErr(null);
    try {
      const snap = await api.post("/api/runs", { file, sample_size: useSample ? Number(sample) : null });
      onStarted(snap);
    } catch (e) { setErr(e.message); setBusy(false); }
  };

  const doUpload = async (f) => {
    if (!f) return;
    setBusy(true); setErr(null);
    try {
      await api.upload("/api/inbox", f);
      const e = await api.get("/api/inbox");
      setInbox(e); setFile(f.name);
    } catch (er) { setErr(er.message); }
    setBusy(false);
  };

  const selected = inbox?.find((x) => x.name === file);

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4" onClick={onClose}>
      <motion.div
        initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }}
        className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl" onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-black">New analysis</h3>
          <button onClick={onClose}><X size={18} /></button>
        </div>
        <p className="mt-1 text-xs text-slate-500">Run the Perfect Store pipeline on a file from <code>inbox/</code>.</p>

        <label className="mt-4 block text-[11px] font-bold uppercase text-slate-400">Source file</label>
        {inbox == null ? (
          <p className="mt-2 text-xs text-slate-400">Loading inbox…</p>
        ) : (
          <select value={file} onChange={(e) => setFile(e.target.value)}
            className="mt-1 w-full rounded-xl border border-slate-200 p-2 text-sm">
            {inbox.map((e) => (
              <option key={e.name} value={e.name}>
                {e.name} ({e.size_h}){e.kind === "reference" ? " — reference, not a pipeline input" : ""}
              </option>
            ))}
          </select>
        )}
        {selected?.kind === "reference" && (
          <p className="mt-1 text-[11px] font-semibold text-[#EB9F0A]">
            This file has no outlet/SKU columns — the run will fail at prioritization.
          </p>
        )}

        <button onClick={() => uploadRef.current?.click()}
          className="mt-2 flex items-center gap-2 text-[11px] font-bold text-[#3680CE]">
          <UploadCloud size={13} /> Upload a new file to inbox/
        </button>
        <input ref={uploadRef} type="file" accept=".csv,.xlsx,.xls" className="hidden"
          onChange={(e) => doUpload(e.target.files?.[0])} />

        <label className="mt-4 flex items-center gap-2 text-xs font-semibold">
          <input type="checkbox" checked={useSample} onChange={(e) => setUseSample(e.target.checked)} />
          Sample rows (faster test run)
        </label>
        {useSample && (
          <input type="number" min={500} step={500} value={sample}
            onChange={(e) => setSample(e.target.value)}
            className="mt-2 w-full rounded-xl border border-slate-200 p-2 text-sm" />
        )}

        {err && <p className="mt-3 rounded-lg bg-red-50 p-2 text-[11px] text-red-600">{err}</p>}

        <div className="mt-5 flex justify-end gap-2">
          <Btn className="border border-slate-200" onClick={onClose}>Cancel</Btn>
          <Btn className="bg-[#3680CE] text-white" disabled={busy || !file} onClick={start}>
            {busy ? "Starting…" : "Run pipeline"}
          </Btn>
        </div>
      </motion.div>
    </div>
  );
}

/* ── main app ──────────────────────────────────────────────────────────── */
export default function App() {
  const health = useHealth();
  const { runs, err: runsErr, refresh: refreshRuns } = useRuns();

  const [section, setSection] = useState("home");
  const [market, setMarket] = useState("India");
  const [selectedRunId, setSelectedRunId] = useState(null);
  const [copilot, setCopilot] = useState(true);
  const [prompt, setPrompt] = useState("");
  const [heroPrompt, setHeroPrompt] = useState("");
  const [modal, setModal] = useState(false);
  const [streamKey, setStreamKey] = useState(0);
  const [messages, setMessages] = useState([
    { role: "ai", text: "I'm ready to help with this workspace. Open a run in Output Studio, then ask me to explain the segments, compare priority tiers, or draft a leadership story." },
  ]);
  const [sending, setSending] = useState(false);
  const addFileRef = useRef(null);

  const stream = useRunStream(streamKey);
  const runActive = stream.status === "running" || stream.status === "connecting";

  // default selection = newest run
  useEffect(() => {
    if (runs && runs.length && !selectedRunId) setSelectedRunId(runs[0].id);
  }, [runs, selectedRunId]);

  // when a live run finishes, refresh the list and select it
  useEffect(() => {
    if (stream.status === "done" && stream.outputDir) {
      refreshRuns();
      setSelectedRunId(stream.outputDir);
    }
  }, [stream.status, stream.outputDir, refreshRuns]);

  // pick up a run that is already in progress on load
  useEffect(() => {
    api.get("/api/runs/active").then((s) => { if (s.status === "running") setStreamKey((k) => k + 1); }).catch(() => {});
  }, []);

  const detail = useRunDetail(selectedRunId);
  const selectedRun = runs?.find((r) => r.id === selectedRunId) || null;

  const thisMonth = monthKey(new Date().toISOString());
  const outputsThisMonth = (runs || []).filter((r) => monthKey(r.ts) === thisMonth).length;
  const latest = runs && runs[0];

  const metrics = [
    ["Completed runs", runs ? String(runs.length) : "—", "in outputs/", C.blue],
    ["Outputs this month", String(outputsThisMonth), thisMonth, C.green],
    ["Segments (latest run)", latest?.segment_count != null ? String(latest.segment_count) : "—", latest?.label || "", C.yellow],
    ["Outlets analysed (latest)", fmtInt(latest?.outlets), latest?.label || "", C.darkBlue],
  ];

  const marketRuns = useMemo(
    () => (runs || []).filter((r) => (r.market || "India") === market),
    [runs, market]
  );
  const visibleRuns = section === "workspace" ? marketRuns : (runs || []);

  const sendCopilot = async (text) => {
    const q = (text ?? prompt).trim();
    if (!q || sending) return;
    setPrompt("");
    setMessages((m) => [...m, { role: "user", text: q }]);
    setSending(true);
    try {
      const res = await api.post("/api/copilot", {
        messages: [...messages, { role: "user", text: q }].map((m) => ({ role: m.role, text: m.text })),
        run_id: selectedRunId,
      });
      setMessages((m) => [...m, { role: "ai", text: res.text }]);
    } catch (e) {
      setMessages((m) => [...m, { role: "ai", text: `Copilot error: ${e.message}` }]);
    }
    setSending(false);
  };

  const onRunStarted = (snap) => {
    setModal(false);
    setStreamKey((k) => k + 1);
    setSection("run");
  };

  const addDataFile = async (f) => {
    if (!f) return;
    try { await api.upload("/api/inbox", f); } catch (e) { alert(e.message); }
  };

  const sectionTitle = {
    home: "Command Center", workspace: `${market} Workspace`, outputs: "Output Studio",
    agents: "Agent Hub", approvals: "Approval Center", monitor: "Monitoring Hub", run: "Live Run",
  }[section];

  const sectionHeading = {
    home: "Good afternoon, Fasahat", workspace: `${market} Perfect Store`,
    outputs: "Explore generated outputs", agents: "Specialist agents",
    approvals: "Review and approve", monitor: "Track adoption and impact",
    run: "Pipeline execution",
  }[section];

  return (
    <div className="min-h-screen bg-[#F7F5F3] text-[#02355A]">
      {/* header */}
      <header className="flex h-16 items-center justify-between bg-[#02355A] px-5 text-white">
        <div className="flex items-center gap-3">
          <div className="grid h-9 w-9 place-items-center rounded-full bg-[#3680CE]"><Sparkles size={18} /></div>
          <div>
            <h1 className="font-bold">Perfect Store AI Workbench</h1>
            <p className="text-[10px] tracking-wide text-[#A6CBF0]">OUTPUTS · AGENTS · GOVERNANCE</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="relative hidden md:block">
            <Search className="absolute left-3 top-2.5 text-[#A6CBF0]" size={15} />
            <input className="h-9 w-64 rounded-xl border border-[#3680CE] bg-[#155798]/60 pl-9 text-xs outline-none"
              placeholder="Search outputs or markets" />
          </div>
          <span className="hidden rounded-full border border-[#3680CE] px-3 py-1 text-[10px] text-[#A6CBF0] lg:inline">
            {health ? `${health.llm_backend} · ${health.model}` : "connecting…"}
          </span>
          <Bell size={18} />
          <span className="rounded-full border border-[#3680CE] px-3 py-1 text-[10px] text-[#A6CBF0]">CONFIDENTIAL</span>
          <div className="grid h-9 w-9 place-items-center rounded-full bg-[#3680CE] text-xs font-bold">FQ</div>
        </div>
      </header>

      <div className="grid min-h-[calc(100vh-64px)] grid-cols-[220px_1fr]">
        {/* sidebar */}
        <aside className="border-r border-[#A6CBF0] bg-white p-3">
          <div className="mb-4 rounded-xl bg-[#F7F5F3] p-3">
            <p className="text-[10px] font-bold uppercase text-slate-400">Current workspace</p>
            <div className="mt-2 flex items-center justify-between">
              <div>
                <p className="text-sm font-bold">Global Perfect Store</p>
                <p className="text-[10px] text-slate-500">{MARKETS.length} markets · India live</p>
              </div>
              <ChevronDown size={15} />
            </div>
          </div>
          <nav className="space-y-1">
            {navItems.map(([id, label, Icon]) => (
              <button key={id} onClick={() => setSection(id)}
                className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold ${section === id ? "bg-[#A6CBF0]/45" : "text-slate-500"}`}>
                <Icon size={17} />{label}
                {id === "monitor" && runActive && <span className="ml-auto h-2 w-2 rounded-full bg-[#EB9F0A]" />}
              </button>
            ))}
          </nav>
          <p className="mb-2 mt-6 px-3 text-[10px] font-bold uppercase text-slate-400">Market workspaces</p>
          {MARKETS.map((m) => (
            <button key={m} onClick={() => { setMarket(m); setSection("workspace"); }}
              className={`flex w-full items-center justify-between rounded-xl px-3 py-2 text-sm ${market === m && section === "workspace" ? "bg-[#02355A] text-white" : "text-slate-500"}`}>
              <span>{m}</span><ChevronRight size={14} />
            </button>
          ))}
          <div className="mt-6 rounded-xl bg-[#02355A] p-3 text-white">
            <div className="flex items-center gap-2 text-xs font-bold"><ShieldCheck size={15} />Governed workspace</div>
            <p className="mt-2 text-[10px] text-[#A6CBF0]">All agent actions are logged. Approvals are recorded locally in this browser.</p>
          </div>
        </aside>

        {/* main */}
        <main className={`min-w-0 p-6 ${copilot ? "pr-[374px]" : ""}`}>
          <AnimatePresence mode="wait">
            <motion.div key={section} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
              <div className="mb-5 flex items-end justify-between">
                <div>
                  <p className="text-xs font-bold uppercase text-[#3680CE]">{sectionTitle}</p>
                  <h2 className="mt-1 text-2xl font-black">{sectionHeading}</h2>
                  <p className="mt-1 text-sm text-slate-500">Here is what needs your attention across Perfect Store.</p>
                </div>
                <div className="flex gap-2">
                  <Btn className="border border-[#155798]" onClick={() => addFileRef.current?.click()}>
                    <UploadCloud size={15} className="mr-2 inline" />Add data
                  </Btn>
                  <input ref={addFileRef} type="file" accept=".csv,.xlsx,.xls" className="hidden"
                    onChange={(e) => addDataFile(e.target.files?.[0])} />
                  <Btn className="bg-[#3680CE] text-white" onClick={() => setModal(true)}>
                    <Play size={15} className="mr-2 inline" />New analysis
                  </Btn>
                </div>
              </div>

              {runsErr && (
                <div className="mb-4 rounded-xl bg-red-50 p-3 text-xs text-red-600">
                  Can't reach the workbench API ({runsErr}). Start it with <code>./workbench/run_workbench.sh</code>.
                </div>
              )}

              {(section === "home" || section === "monitor") && (
                <div className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
                  {metrics.map((x) => (
                    <Card key={x[0]}>
                      <div className="p-5">
                        <div className="mb-3 h-1.5 w-10 rounded-full" style={{ background: x[3] }} />
                        <p className="text-xs text-slate-500">{x[0]}</p>
                        <p className="mt-1 text-2xl font-black">{x[1]}</p>
                        <p className="text-xs text-slate-400">{x[2]}</p>
                      </div>
                    </Card>
                  ))}
                </div>
              )}

              {(section === "home" || section === "workspace") && (
                <div className="mb-5 grid gap-5 lg:grid-cols-[1.3fr_1fr]">
                  <Card className="bg-[#02355A] text-white">
                    <div className="p-6">
                      <div className="flex justify-between">
                        <div>
                          <p className="text-xs font-bold text-[#A6CBF0]">PERFECT STORE COPILOT</p>
                          <h3 className="mt-2 text-xl font-bold">What would you like to do?</h3>
                          <p className="text-sm text-[#A6CBF0]">Ask across outputs, agents and approved run data.</p>
                        </div>
                        <Bot size={28} />
                      </div>
                      <div className="mt-5 flex rounded-xl bg-white p-2">
                        <input value={heroPrompt} onChange={(e) => setHeroPrompt(e.target.value)}
                          onFocus={() => setCopilot(true)}
                          onKeyDown={(e) => { if (e.key === "Enter" && heroPrompt.trim()) { sendCopilot(heroPrompt); setHeroPrompt(""); } }}
                          className="flex-1 px-2 text-sm text-[#02355A] outline-none"
                          placeholder="Which segment holds the biggest opportunity?" />
                        <button className="rounded-lg bg-[#3680CE] p-2"
                          onClick={() => { if (heroPrompt.trim()) { setCopilot(true); sendCopilot(heroPrompt); setHeroPrompt(""); } }}>
                          <Send size={16} />
                        </button>
                      </div>
                    </div>
                  </Card>
                  <Card>
                    <div className="p-5">
                      <h3 className="font-bold">Needs attention</h3>
                      <div className="mt-4 space-y-3">
                        {latest ? (
                          <button onClick={() => { setSelectedRunId(latest.id); setSection("approvals"); }}
                            className="w-full rounded-xl bg-[#FFE8AD]/50 p-3 text-left text-xs font-bold">
                            {latest.deck_name ? `${latest.label} deck ready for approval` : `${latest.label} run — no deck produced`}
                          </button>
                        ) : (
                          <div className="rounded-xl bg-[#A6CBF0]/30 p-3 text-xs font-bold">No runs yet — start a new analysis</div>
                        )}
                        {runActive && (
                          <button onClick={() => setSection("run")}
                            className="w-full rounded-xl bg-[#A6CBF0]/30 p-3 text-left text-xs font-bold">
                            Pipeline running — view live progress
                          </button>
                        )}
                      </div>
                    </div>
                  </Card>
                </div>
              )}

              {/* ── Output Studio / recent outputs ── */}
              {(section === "home" || section === "workspace" || section === "outputs") && (
                <div className="grid gap-5 lg:grid-cols-[1.05fr_1fr]">
                  <Card>
                    <div className="p-5">
                      <div className="flex items-center justify-between">
                        <h3 className="font-bold">{section === "outputs" ? "All runs" : "Recent outputs"}</h3>
                        <button onClick={refreshRuns} className="text-slate-400 hover:text-[#3680CE]"><RefreshCw size={14} /></button>
                      </div>
                      <div className="mt-4 space-y-2">
                        {visibleRuns == null && <p className="text-xs text-slate-400">Loading…</p>}
                        {visibleRuns && visibleRuns.length === 0 && (
                          <p className="rounded-xl bg-[#F7F5F3] p-4 text-xs text-slate-500">
                            No runs {section === "workspace" ? `for ${market}` : "yet"}. Use “New analysis”.
                          </p>
                        )}
                        {(visibleRuns || []).map((o) => (
                          <button key={o.id} onClick={() => { setSelectedRunId(o.id); setSection("outputs"); }}
                            className={`flex w-full items-center justify-between rounded-xl border p-3 text-left ${selectedRunId === o.id ? "border-[#3680CE] bg-[#A6CBF0]/20" : "border-slate-100"}`}>
                            <div className="flex items-center gap-3">
                              <div className="grid h-10 w-10 place-items-center rounded-xl bg-[#02355A] text-white">
                                {o.counts.deck ? <FileText size={17} /> : <BarChart3 size={17} />}
                              </div>
                              <div>
                                <p className="text-xs font-bold">{o.label}</p>
                                <p className="text-[10px] text-slate-400">
                                  {o.market} · {o.deck_slides ? `${o.deck_slides} slides · ` : ""}
                                  {o.segment_count != null ? `${o.segment_count} segments · ` : ""}
                                  {fmtInt(o.outlets)} outlets
                                </p>
                              </div>
                            </div>
                            <span className="rounded-full bg-[#BFDE7D]/60 px-2 py-1 text-[9px] font-bold">{o.status}</span>
                          </button>
                        ))}
                      </div>
                    </div>
                  </Card>

                  <Card>
                    <div className="p-5">
                      <div className="mb-4 flex justify-between">
                        <div>
                          <h3 className="font-bold">Output preview</h3>
                          <p className="text-xs text-slate-400">{selectedRun ? selectedRun.label : "Select a run"}</p>
                        </div>
                        <div className="flex gap-2 text-slate-400">
                          {detail?.files?.[0] && (
                            <a href={`/api/runs/${selectedRunId}/file/${encodeURIComponent(detail.files[0].name)}`}
                              className="hover:text-[#3680CE]"><Download size={15} /></a>
                          )}
                          <MoreHorizontal size={15} />
                        </div>
                      </div>
                      <MiniDeck
                        market={selectedRun?.market}
                        headline={detail?.deck_titles?.[0]?.replace(/^\d+\.\s*/, "")}
                        bars={detail?.summary?.segments?.map((s) => s.outlets)}
                        takeaway={
                          detail?.summary?.segments?.[0]
                            ? `${detail.summary.segments[0].label} is the largest segment (${detail.summary.segments[0].outlets} outlets, avg gap ${fmtRupee(detail.summary.segments[0].avg_gap)}).`
                            : undefined
                        }
                      />
                      <button onClick={() => { setCopilot(true); }}
                        className="mt-3 flex w-full items-center justify-center gap-2 rounded-xl bg-[#3680CE] py-2.5 text-xs font-bold text-white">
                        <MessageSquareText size={15} />Chat with this output
                      </button>
                    </div>
                  </Card>
                </div>
              )}

              {/* ── Output Studio detail ── */}
              {section === "outputs" && detail && (
                <div className="mt-5 grid gap-5 lg:grid-cols-2">
                  <Card>
                    <div className="p-5">
                      <h3 className="font-bold">Deliverables</h3>
                      <div className="mt-3 space-y-2">
                        {detail.files.map((f) => (
                          <a key={f.name} href={`/api/runs/${selectedRunId}/file/${encodeURIComponent(f.name)}`}
                            className="flex items-center justify-between rounded-xl border border-slate-100 p-3 hover:border-[#3680CE]">
                            <span className="truncate text-xs font-semibold">{f.name}</span>
                            <span className="ml-3 shrink-0 text-[10px] text-slate-400">
                              {f.slides ? `${f.slides} slides · ` : ""}{f.size_h}
                            </span>
                          </a>
                        ))}
                        {!detail.files.length && <p className="text-xs text-slate-400">No files in this run.</p>}
                      </div>
                      {detail.charts?.length > 0 && (
                        <>
                          <h4 className="mt-5 text-xs font-bold uppercase text-slate-400">Charts</h4>
                          <div className="mt-2 grid grid-cols-2 gap-2">
                            {detail.charts.map((c) => (
                              <img key={c} src={`/api/runs/${selectedRunId}/chart/${encodeURIComponent(c)}`}
                                alt={c} className="rounded-lg ring-1 ring-slate-200" />
                            ))}
                          </div>
                        </>
                      )}
                    </div>
                  </Card>

                  <Card>
                    <div className="p-5">
                      <h3 className="font-bold">Segment summary</h3>
                      {detail.summary?.segments?.length ? (
                        <table className="mt-3 w-full text-left text-xs">
                          <thead className="text-[10px] uppercase text-slate-400">
                            <tr><th className="py-1">Segment</th><th>Outlets</th><th>% univ</th><th>Avg VPO</th><th>Avg gap</th></tr>
                          </thead>
                          <tbody>
                            {detail.summary.segments.map((s) => (
                              <tr key={s.id} className="border-t border-slate-100">
                                <td className="py-1.5 pr-2 font-semibold">{s.label}</td>
                                <td>{fmtInt(s.outlets)}</td>
                                <td>{s.pct_universe}%</td>
                                <td>{fmtRupee(s.avg_vpo)}</td>
                                <td>{fmtRupee(s.avg_gap)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      ) : (
                        <p className="mt-3 text-xs text-slate-400">No all_segments summary in this run.</p>
                      )}

                      {detail.deck_titles?.length > 0 && (
                        <>
                          <h4 className="mt-5 text-xs font-bold uppercase text-slate-400">Deck slides</h4>
                          <ol className="mt-2 space-y-1 text-xs text-slate-600">
                            {detail.deck_titles.map((t) => <li key={t}>{t}</li>)}
                          </ol>
                        </>
                      )}
                    </div>
                  </Card>
                </div>
              )}

              {/* ── Agent Hub ── */}
              {section === "agents" && (
                <div className="grid grid-cols-2 gap-4">
                  {AGENTS.map(([name, mod, steps, Icon, color]) => {
                    const st = steps.map((n) => stream.steps[n]).filter(Boolean);
                    const live = runActive && st.length;
                    const label = live
                      ? (st.includes("running") ? "Running now" : st.every((s) => s === "done") ? "Completed this run" : "Queued")
                      : latest ? `Ready · last run ${latest.label}` : "No runs yet";
                    return (
                      <Card key={name}>
                        <div className="p-5">
                          <div className="grid h-11 w-11 place-items-center rounded-xl text-white" style={{ background: color }}>
                            <Icon size={20} />
                          </div>
                          <h3 className="mt-4 font-bold">{name}</h3>
                          <p className="text-xs text-slate-500">{label}</p>
                          <p className="mt-1 text-[10px] text-slate-400">agents/{mod}.py</p>
                        </div>
                      </Card>
                    );
                  })}
                </div>
              )}

              {/* ── Approval Center ── */}
              {section === "approvals" && (
                <ApprovalCenter runs={runs || []} onOpen={(id) => { setSelectedRunId(id); setSection("outputs"); }} />
              )}

              {/* ── Monitoring Hub ── */}
              {section === "monitor" && (
                <MonitoringHub runs={runs || []} live={runActive ? stream : null} />
              )}

              {/* ── Live Run ── */}
              {section === "run" && (
                <div className="grid gap-5 lg:grid-cols-[1fr_1fr]">
                  <Card>
                    <div className="p-5">
                      <div className="flex items-center justify-between">
                        <h3 className="font-bold">Steps</h3>
                        <span className="text-[10px] uppercase tracking-wide text-slate-400">
                          {stream.meta ? `${stream.meta.llm_backend} · ${stream.meta.model}` : stream.status}
                        </span>
                      </div>
                      <div className="mt-4 space-y-2">
                        {STEPS.map(([n, label]) => <StepPill key={n} n={n} label={label} state={stream.steps[n]} />)}
                      </div>
                      {stream.status === "done" && stream.outputDir && (
                        <button onClick={() => { setSelectedRunId(stream.outputDir); setSection("outputs"); }}
                          className="mt-4 flex w-full items-center justify-center gap-2 rounded-xl bg-[#5D910D] py-2.5 text-xs font-bold text-white">
                          View output <ArrowUpRight size={13} />
                        </button>
                      )}
                      {stream.status === "failed" && (
                        <p className="mt-4 rounded-lg bg-red-50 p-2 text-[11px] text-red-600">Run failed — see the log.</p>
                      )}
                      {stream.status === "idle" && (
                        <p className="mt-4 text-xs text-slate-400">No active run. Start one with “New analysis”.</p>
                      )}
                    </div>
                  </Card>
                  <Card>
                    <div className="p-5">
                      <h3 className="font-bold">Live log</h3>
                      <pre className="ps-scroll mt-3 h-[420px] overflow-auto rounded-xl bg-[#02355A] p-3 text-[10px] leading-relaxed text-[#A6CBF0]">
                        {stream.logs.join("\n") || "waiting for output…"}
                      </pre>
                    </div>
                  </Card>
                </div>
              )}
            </motion.div>
          </AnimatePresence>

          {/* bottom row — agent activity + run status */}
          {section !== "run" && (
            <div className="mt-5 grid gap-5 lg:grid-cols-[1.3fr_1fr]">
              <Card>
                <div className="p-5">
                  <h3 className="text-sm font-bold">Agent activity</h3>
                  <div className="mt-4 grid grid-cols-2 gap-2">
                    {(runActive
                      ? STEPS.filter(([n]) => stream.steps[n]).slice(-4).map(([n, l]) => [l, stream.steps[n]])
                      : [
                          ["Segmentation Agent", latest ? `${latest.segment_count} segments` : "idle"],
                          ["Output Agent", latest ? `${latest.counts.excel} workbooks · ${latest.counts.csv} CSVs` : "idle"],
                          ["PPT Agent", latest?.deck_slides ? `${latest.deck_slides}-slide deck` : "no deck"],
                          ["Space Agent", latest ? "planogram written" : "idle"],
                        ]
                    ).map((x) => (
                      <div key={x[0]} className="rounded-xl bg-[#F7F5F3] p-3">
                        <p className="text-[10px] font-bold text-[#3680CE]">{x[0]}</p>
                        <p className="text-xs">{x[1]}</p>
                      </div>
                    ))}
                  </div>
                </div>
              </Card>
              <Card>
                <div className="p-5">
                  <h3 className="text-sm font-bold">Run status</h3>
                  {(() => {
                    const done = STEPS.filter(([n]) => stream.steps[n] === "done").length;
                    const pct = runActive || stream.status === "done" ? Math.round((done / STEPS.length) * 100) : (latest ? 100 : 0);
                    const line = runActive ? "Live run in progress"
                      : stream.status === "failed" ? "Last run failed"
                      : latest ? `${latest.label} · complete` : "No runs yet";
                    return (
                      <>
                        <p className="mt-4 text-xs font-bold">{line}</p>
                        <p className="text-[10px] text-slate-400">
                          {runActive ? `${done} of ${STEPS.length} steps` : latest ? "7 of 7 steps" : "—"}
                        </p>
                        <div className="mt-4 h-2 rounded-full bg-slate-100">
                          <div className="h-full rounded-full" style={{ width: `${pct}%`, background: stream.status === "failed" ? "#d33" : C.green }} />
                        </div>
                        <button onClick={() => setSection("run")}
                          className="mt-4 flex items-center gap-1 text-xs font-bold text-[#3680CE]">
                          View execution timeline <ArrowUpRight size={13} />
                        </button>
                      </>
                    );
                  })()}
                </div>
              </Card>
            </div>
          )}
        </main>

        {/* copilot */}
        <AnimatePresence>
          {copilot && (
            <motion.aside initial={{ x: 360 }} animate={{ x: 0 }} exit={{ x: 360 }}
              className="fixed bottom-0 right-0 top-16 z-20 flex w-[350px] flex-col border-l border-[#A6CBF0] bg-white shadow-2xl">
              <div className="flex items-center justify-between bg-[#02355A] p-4 text-white">
                <div className="flex items-center gap-3">
                  <Bot size={20} />
                  <div>
                    <p className="text-sm font-bold">Perfect Store Copilot</p>
                    <p className="text-[10px] text-[#A6CBF0]">
                      {health ? `${health.llm_backend} · ${health.model}` : "grounded on run data"}
                    </p>
                  </div>
                </div>
                <button onClick={() => setCopilot(false)}><X size={18} /></button>
              </div>
              <div className="border-b bg-[#F7F5F3] p-3 text-xs font-bold">
                Context: {selectedRun ? selectedRun.label : "no run selected"}
              </div>
              <div className="ps-scroll flex-1 space-y-3 overflow-auto p-4">
                {messages.map((m, i) => (
                  <div key={i} className={`max-w-[88%] whitespace-pre-wrap rounded-2xl p-3 text-xs ${m.role === "user" ? "ml-auto bg-[#3680CE] text-white" : "bg-[#F7F5F3]"}`}>
                    {m.text}
                  </div>
                ))}
                {sending && (
                  <div className="flex items-center gap-2 text-xs text-slate-400"><Loader2 size={13} className="animate-spin" />thinking…</div>
                )}
              </div>
              <div className="border-t p-4">
                <div className="flex rounded-xl border border-[#3680CE] p-2">
                  <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendCopilot(); } }}
                    className="ps-scroll flex-1 resize-none px-2 text-xs outline-none" rows={2}
                    placeholder="Ask about this run…" />
                  <button onClick={() => sendCopilot()} className="rounded-lg bg-[#3680CE] p-2 text-white self-end">
                    <Send size={15} />
                  </button>
                </div>
              </div>
            </motion.aside>
          )}
        </AnimatePresence>
      </div>

      {modal && <NewAnalysisModal onClose={() => setModal(false)} onStarted={onRunStarted} />}
    </div>
  );
}

/* ── Approval Center (localStorage-backed) ─────────────────────────────── */
function ApprovalCenter({ runs, onOpen }) {
  const [decisions, setDecisions] = useState(() => {
    try { return JSON.parse(localStorage.getItem("ps_approvals") || "{}"); } catch { return {}; }
  });
  const set = (id, verdict) => {
    const next = { ...decisions, [id]: { verdict, at: new Date().toISOString() } };
    setDecisions(next);
    try { localStorage.setItem("ps_approvals", JSON.stringify(next)); } catch { /* private mode */ }
  };
  return (
    <Card>
      <div className="p-5">
        <h3 className="font-bold">Pending approvals</h3>
        <p className="text-xs text-slate-400">Deck sign-off per run. Recorded in this browser only.</p>
        <div className="mt-4 space-y-3">
          {runs.length === 0 && <p className="text-xs text-slate-400">No runs to review.</p>}
          {runs.map((r) => {
            const d = decisions[r.id];
            return (
              <div key={r.id} className="flex items-center justify-between rounded-xl border p-4">
                <div>
                  <button onClick={() => onOpen(r.id)} className="text-sm font-bold hover:text-[#3680CE]">{r.label}</button>
                  <p className="text-[10px] text-slate-400">
                    {r.deck_name || "no deck"} · {r.segment_count ?? "—"} segments
                    {d && ` · ${d.verdict} ${new Date(d.at).toLocaleDateString()}`}
                  </p>
                </div>
                {d ? (
                  <span className={`rounded-full px-3 py-1 text-[10px] font-bold ${d.verdict === "approved" ? "bg-[#BFDE7D]/60" : "bg-red-100 text-red-600"}`}>
                    {d.verdict}
                  </span>
                ) : (
                  <div className="flex gap-2">
                    <Btn className="border border-slate-200" onClick={() => set(r.id, "rejected")}>Reject</Btn>
                    <Btn className="bg-[#5D910D] text-white" onClick={() => set(r.id, "approved")}>Approve</Btn>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </Card>
  );
}

/* ── Monitoring Hub ───────────────────────────────────────────────────── */
function MonitoringHub({ runs, live }) {
  const byMonth = useMemo(() => {
    const m = {};
    for (const r of runs) { const k = monthKey(r.ts) || "—"; m[k] = (m[k] || 0) + 1; }
    return Object.entries(m).sort();
  }, [runs]);
  const maxRuns = Math.max(1, ...byMonth.map(([, v]) => v));

  return (
    <div className="grid gap-5 lg:grid-cols-[1.3fr_1fr]">
      <Card>
        <div className="p-5">
          <h3 className="font-bold">Runs over time</h3>
          <div className="mt-4 flex items-end gap-3">
            {byMonth.map(([k, v]) => (
              <div key={k} className="flex flex-1 flex-col items-center">
                <div className="w-full rounded-t bg-[#3680CE]" style={{ height: `${(v / maxRuns) * 140}px` }} />
                <span className="mt-1 text-[9px] text-slate-400">{k}</span>
                <span className="text-[10px] font-bold">{v}</span>
              </div>
            ))}
            {byMonth.length === 0 && <p className="text-xs text-slate-400">No runs recorded.</p>}
          </div>
        </div>
      </Card>
      <Card>
        <div className="p-5">
          <h3 className="font-bold">Latest run health</h3>
          {runs[0] ? (
            <div className="mt-4 space-y-2 text-xs">
              <Row label="Run" value={runs[0].label} />
              <Row label="Outlets" value={fmtInt(runs[0].outlets)} />
              <Row label="Segments" value={runs[0].segment_count ?? "—"} />
              <Row label="Deck" value={runs[0].deck_slides ? `${runs[0].deck_slides} slides` : "—"} />
              <Row label="Total VPO" value={fmtRupee(runs[0].total_vpo)} />
              <Row label="Live run" value={live ? live.status : "none"} />
            </div>
          ) : <p className="mt-4 text-xs text-slate-400">No runs yet.</p>}
          <p className="mt-4 text-[10px] text-slate-400">
            Adoption &amp; in-market impact tiles need a downstream feedback source — not wired in this build.
          </p>
        </div>
      </Card>
    </div>
  );
}

const Row = ({ label, value }) => (
  <div className="flex justify-between border-b border-slate-100 py-1.5">
    <span className="text-slate-400">{label}</span><span className="font-semibold">{value}</span>
  </div>
);
