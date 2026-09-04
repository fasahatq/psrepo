import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  BarChart3, Bell, Bot, CheckCircle2, ChevronDown, ChevronRight,
  Download, FileBarChart2, FileText, Globe2, LayoutDashboard, Loader2, MessageSquareText,
  Package, Play, RefreshCw, Search, Send, ShieldCheck, Sparkles, Store, UploadCloud, X, Zap,
} from "lucide-react";

/* ── brand ──────────────────────────────────────────────────────────────── */
const C = {
  navy: "#02355A", blue: "#3680CE", darkBlue: "#155798", lightBlue: "#A6CBF0",
  offWhite: "#F7F5F3", yellow: "#EB9F0A", green: "#5D910D",
};

const navItems = [
  ["workspace", "Market Workspace", Globe2],
  ["outputs", "Output Studio", FileBarChart2],
  ["agents", "Agent Hub", Sparkles],
];

const MARKETS = ["India", "Mexico", "Brazil"];

/* 7 pipeline steps — labels mirror gui/steps.py STEP_META */
const STEPS = [
  [1, "Load"],
  [2, "Data quality"],
  [3, "Prioritization"],
  [4, "Segmentation"],
  [5, "MSL"],
  [6, "Outputs"],
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
  const [state, setState] = useState({ status: "idle", steps: {}, logs: [], detail: {}, meta: null, outputDir: null });
  useEffect(() => {
    if (streamKey === 0) return;
    setState({ status: "connecting", steps: {}, logs: [], detail: {}, meta: null, outputDir: null });
    const es = new EventSource("/api/runs/stream");
    es.onmessage = (e) => {
      let ev;
      try { ev = JSON.parse(e.data); } catch { return; }
      setState((s) => {
        if (ev.kind === "idle") { es.close(); return { ...s, status: "idle" }; }
        if (ev.kind === "init") return { ...s, status: "running", meta: ev.meta };
        if (ev.kind === "step") {
          const steps = { ...s.steps };
          const detail = { ...s.detail };
          if (ev.status === "running") {
            for (const [n] of STEPS) if (n < ev.step && steps[n] !== "done") steps[n] = "done";
          }
          steps[ev.step] = ev.status;
          if (ev.detail) detail[ev.step] = ev.detail;
          return { ...s, status: "running", steps, detail };
        }
        if (ev.kind === "log") {
          const line = `${ev.ts}  ${(ev.level || "").padEnd(5)} ${ev.msg}`;
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

/* ── ui atoms ───────────────────────────────────────────────────────────── */
const Btn = ({ children, className = "", ...p }) => (
  <button className={`rounded-xl px-3 py-2 text-xs font-semibold disabled:opacity-50 ${className}`} {...p}>
    {children}
  </button>
);
const Card = ({ children, className = "" }) => (
  <div className={`rounded-2xl bg-white shadow-sm ${className}`}>{children}</div>
);
const Chip = ({ children, tone = "blue" }) => {
  const map = {
    blue: "bg-[#A6CBF0]/40 text-[#155798]",
    green: "bg-[#BFDE7D]/50 text-[#3f6108]",
    amber: "bg-[#FFE8AD]/70 text-[#8a5a00]",
    slate: "bg-slate-100 text-slate-500",
  };
  return <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${map[tone]}`}>{children}</span>;
};

/* ── horizontal pipeline ────────────────────────────────────────────────── */
function HorizontalPipeline({ steps, detail, status }) {
  return (
    <div className="w-full">
      <div className="flex items-start">
        {STEPS.map(([n, label], i) => {
          const st = steps[n];
          const bg = st === "done" ? C.green : st === "running" ? C.yellow : st === "failed" ? "#d33" : "#e2e8f0";
          const done = st === "done";
          return (
            <React.Fragment key={n}>
              <div className="flex w-0 flex-1 flex-col items-center">
                <motion.div
                  animate={st === "running" ? { scale: [1, 1.12, 1] } : { scale: 1 }}
                  transition={{ repeat: st === "running" ? Infinity : 0, duration: 1.1 }}
                  className="grid h-9 w-9 place-items-center rounded-full text-[11px] font-bold text-white shadow-sm"
                  style={{ background: bg }}
                >
                  {st === "running" ? <Loader2 size={14} className="animate-spin" /> : done ? <CheckCircle2 size={16} /> : n}
                </motion.div>
                <p className={`mt-2 text-center text-[10px] font-semibold ${st ? "text-[#02355A]" : "text-slate-400"}`}>{label}</p>
                {detail?.[n] && <p className="mt-0.5 line-clamp-2 text-center text-[9px] text-slate-400">{detail[n]}</p>}
              </div>
              {i < STEPS.length - 1 && (
                <div className="mt-4 h-0.5 flex-1 rounded-full" style={{ background: steps[STEPS[i + 1][0]] || done ? C.green : "#e2e8f0" }} />
              )}
            </React.Fragment>
          );
        })}
      </div>
      <p className="mt-3 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
        {status === "running" || status === "connecting" ? "Executing…"
          : status === "done" ? "Run complete"
          : status === "failed" ? "Run failed — see log"
          : "Idle"}
      </p>
    </div>
  );
}

/* ── deck viewer (rendered slide images, scrollable) ────────────────────── */
function DeckViewer({ runId, height = "h-[460px]" }) {
  const [deck, setDeck] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => {
    if (!runId) { setDeck(null); return; }
    let live = true;
    setDeck(null); setErr(null);
    api.get(`/api/runs/${runId}/deck`)
      .then((d) => { if (live) setDeck(d); })
      .catch((e) => { if (live) setErr(e.message); });
    return () => { live = false; };
  }, [runId]);

  if (!runId) return <p className="text-xs text-slate-400">Select a run to preview its deck.</p>;
  if (err) return <p className="rounded-lg bg-amber-50 p-3 text-[11px] text-amber-700">Deck preview unavailable ({err}).</p>;
  if (!deck) return (
    <div className={`grid ${height} place-items-center rounded-xl bg-[#F7F5F3] text-xs text-slate-400`}>
      <span className="flex items-center gap-2"><Loader2 size={14} className="animate-spin" />rendering slides…</span>
    </div>
  );
  if (!deck.count) return <p className="text-xs text-slate-400">No deck was produced for this run.</p>;

  return (
    <div>
      <div className={`ps-scroll ${height} space-y-3 overflow-y-auto rounded-xl bg-[#F7F5F3] p-3`}>
        {deck.slides.map((s, i) => (
          <div key={s} className="overflow-hidden rounded-lg ring-1 ring-slate-200">
            <img src={`/api/runs/${runId}/deck/${s}`} alt={`Slide ${i + 1}`} className="block w-full" loading="lazy" />
            <p className="bg-white px-2 py-1 text-[9px] text-slate-400">Slide {i + 1} / {deck.count}</p>
          </div>
        ))}
      </div>
      <a href={`/api/runs/${runId}/file/${encodeURIComponent(deck.deck_name)}`}
        className="mt-2 flex items-center gap-1 text-[11px] font-bold text-[#3680CE]">
        <Download size={13} /> Download {deck.deck_name}
      </a>
    </div>
  );
}

/* ── recent outputs — two rows, then scroll ────────────────────────────── */
function RecentOutputs({ runs, selectedId, onPick, onRefresh, market }) {
  return (
    <Card>
      <div className="p-5">
        <div className="flex items-center justify-between">
          <h3 className="font-bold">Recent outputs</h3>
          <button onClick={onRefresh} className="text-slate-400 hover:text-[#3680CE]"><RefreshCw size={14} /></button>
        </div>
        {runs == null ? (
          <p className="mt-3 text-xs text-slate-400">Loading…</p>
        ) : runs.length === 0 ? (
          <p className="mt-3 rounded-xl bg-[#F7F5F3] p-4 text-xs text-slate-500">
            No runs {market ? `for ${market}` : "yet"}. Execute the pipeline above.
          </p>
        ) : (
          <div className="ps-scroll mt-3 max-h-[136px] space-y-2 overflow-y-auto pr-1">
            {runs.map((o) => (
              <button key={o.id} onClick={() => onPick(o.id)}
                className={`flex w-full items-center justify-between rounded-xl border p-3 text-left ${selectedId === o.id ? "border-[#3680CE] bg-[#A6CBF0]/20" : "border-slate-100"}`}>
                <div className="flex items-center gap-3">
                  <div className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-[#02355A] text-white">
                    {o.counts.deck ? <FileText size={15} /> : <BarChart3 size={15} />}
                  </div>
                  <div className="min-w-0">
                    <p className="truncate text-xs font-bold">{o.label}</p>
                    <p className="truncate text-[10px] text-slate-400">
                      {o.deck_slides ? `${o.deck_slides} slides · ` : ""}
                      {o.segment_count != null ? `${o.segment_count} segments · ` : ""}{fmtInt(o.outlets)} outlets
                    </p>
                  </div>
                </div>
                <Chip tone="green">{o.status}</Chip>
              </button>
            ))}
          </div>
        )}
      </div>
    </Card>
  );
}

/* ── main app ──────────────────────────────────────────────────────────── */
export default function App() {
  const health = useHealth();
  const { runs, err: runsErr, refresh: refreshRuns } = useRuns();

  const [section, setSection] = useState("workspace");
  const [market, setMarket] = useState("India");
  const [selectedRunId, setSelectedRunId] = useState(null);
  const [copilot, setCopilot] = useState(true);
  const [prompt, setPrompt] = useState("");
  const [streamKey, setStreamKey] = useState(0);
  const [messages, setMessages] = useState([
    { role: "ai", text: "I'm ready to help with this workspace. Pick a run, then ask me to explain the segments, rank the opportunity, or draft a leadership story." },
  ]);
  const [sending, setSending] = useState(false);

  // execute-pipeline controls (inline in Market Workspace)
  const [inbox, setInbox] = useState(null);
  const [execFile, setExecFile] = useState("");
  const [execSample, setExecSample] = useState(5000);
  const [execUseSample, setExecUseSample] = useState(true);
  const [execBusy, setExecBusy] = useState(false);
  const [execErr, setExecErr] = useState(null);
  const addFileRef = useRef(null);

  const stream = useRunStream(streamKey);
  const runActive = stream.status === "running" || stream.status === "connecting";

  useEffect(() => {
    api.get("/api/inbox").then((e) => {
      setInbox(e);
      const first = e.find((x) => x.kind === "dataset") || e[0];
      if (first) setExecFile(first.name);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (runs && runs.length && !selectedRunId) setSelectedRunId(runs[0].id);
  }, [runs, selectedRunId]);

  useEffect(() => {
    if (stream.status === "done" && stream.outputDir) {
      refreshRuns();
      setSelectedRunId(stream.outputDir);
    }
  }, [stream.status, stream.outputDir, refreshRuns]);

  useEffect(() => {
    api.get("/api/runs/active").then((s) => { if (s.status === "running") setStreamKey((k) => k + 1); }).catch(() => {});
  }, []);

  const detail = useRunDetail(selectedRunId);
  const selectedRun = runs?.find((r) => r.id === selectedRunId) || null;
  const latest = runs && runs[0];

  const marketRuns = useMemo(
    () => (runs || []).filter((r) => (r.market || "India") === market),
    [runs, market]
  );

  const execute = async () => {
    setExecBusy(true); setExecErr(null);
    try {
      await api.post("/api/runs", { file: execFile, sample_size: execUseSample ? Number(execSample) : null });
      setStreamKey((k) => k + 1);
    } catch (e) { setExecErr(e.message); }
    setExecBusy(false);
  };

  const addDataFile = async (f) => {
    if (!f) return;
    try {
      await api.upload("/api/inbox", f);
      const e = await api.get("/api/inbox");
      setInbox(e); setExecFile(f.name);
    } catch (e) { alert(e.message); }
  };

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

  const selectedInbox = inbox?.find((x) => x.name === execFile);

  const sectionTitle = { workspace: `${market} Workspace`, outputs: "Output Studio", agents: "Agent Hub" }[section];
  const sectionHeading = {
    workspace: `${market} Perfect Store`, outputs: "Segmentation & MSL — refined outputs", agents: "Specialist agents",
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
                {id === "workspace" && runActive && <span className="ml-auto h-2 w-2 animate-pulse rounded-full bg-[#EB9F0A]" />}
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
            <p className="mt-2 text-[10px] text-[#A6CBF0]">All agent actions are logged. Runs execute on the local pipeline.</p>
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
                  <p className="mt-1 text-sm text-slate-500">
                    {section === "workspace" ? "Execute the pipeline and preview the leadership deck as it is generated."
                      : section === "outputs" ? "A crisp view of what the Segmentation and MSL agents recommend."
                      : "Status of each specialist agent in the run."}
                  </p>
                </div>
                <div className="flex gap-2">
                  <Btn className="border border-[#155798]" onClick={() => addFileRef.current?.click()}>
                    <UploadCloud size={15} className="mr-2 inline" />Add data
                  </Btn>
                  <input ref={addFileRef} type="file" accept=".csv,.xlsx,.xls" className="hidden"
                    onChange={(e) => addDataFile(e.target.files?.[0])} />
                </div>
              </div>

              {runsErr && (
                <div className="mb-4 rounded-xl bg-red-50 p-3 text-xs text-red-600">
                  Can't reach the workbench API ({runsErr}). Start it with <code>./workbench/run_workbench.sh</code>.
                </div>
              )}

              {/* ══ Market Workspace ══ */}
              {section === "workspace" && (
                <div className="space-y-5">
                  {/* execute + horizontal pipeline */}
                  <Card>
                    <div className="p-5">
                      <div className="flex flex-wrap items-end gap-3">
                        <div>
                          <label className="text-[11px] font-bold uppercase text-slate-400">Source file</label>
                          <select value={execFile} onChange={(e) => setExecFile(e.target.value)} disabled={runActive}
                            className="mt-1 block w-64 rounded-xl border border-slate-200 p-2 text-sm">
                            {(inbox || []).map((e) => (
                              <option key={e.name} value={e.name}>
                                {e.name} ({e.size_h}){e.kind === "reference" ? " — reference" : ""}
                              </option>
                            ))}
                          </select>
                        </div>
                        <label className="flex items-center gap-2 pb-2 text-xs font-semibold">
                          <input type="checkbox" checked={execUseSample} disabled={runActive}
                            onChange={(e) => setExecUseSample(e.target.checked)} />
                          Sample
                        </label>
                        {execUseSample && (
                          <input type="number" min={500} step={500} value={execSample} disabled={runActive}
                            onChange={(e) => setExecSample(e.target.value)}
                            className="w-24 rounded-xl border border-slate-200 p-2 text-sm" />
                        )}
                        <Btn className="bg-[#3680CE] text-white" disabled={runActive || execBusy || !execFile} onClick={execute}>
                          {runActive ? <><Loader2 size={14} className="mr-2 inline animate-spin" />Running…</>
                            : execBusy ? "Starting…"
                            : <><Play size={14} className="mr-2 inline" />Execute pipeline</>}
                        </Btn>
                      </div>
                      {selectedInbox?.kind === "reference" && (
                        <p className="mt-2 text-[11px] font-semibold text-[#EB9F0A]">
                          This file has no outlet/SKU columns — the run will fail at prioritization.
                        </p>
                      )}
                      {execErr && <p className="mt-2 rounded-lg bg-red-50 p-2 text-[11px] text-red-600">{execErr}</p>}

                      <div className="mt-6 border-t border-slate-100 pt-6">
                        <HorizontalPipeline steps={stream.steps} detail={stream.detail} status={stream.status} />
                      </div>

                      {stream.logs.length > 0 && (
                        <pre className="ps-scroll mt-4 h-28 overflow-auto rounded-xl bg-[#02355A] p-3 text-[10px] leading-relaxed text-[#A6CBF0]">
                          {stream.logs.slice(-40).join("\n")}
                        </pre>
                      )}
                    </div>
                  </Card>

                  <div className="grid gap-5 lg:grid-cols-[1fr_1.1fr]">
                    <RecentOutputs runs={marketRuns} selectedId={selectedRunId} market={market}
                      onPick={(id) => setSelectedRunId(id)} onRefresh={refreshRuns} />

                    <Card>
                      <div className="p-5">
                        <div className="mb-3 flex items-center justify-between">
                          <div>
                            <h3 className="font-bold">Output preview — leadership deck</h3>
                            <p className="text-xs text-slate-400">{selectedRun ? selectedRun.label : "no run selected"}</p>
                          </div>
                          <button onClick={() => setCopilot(true)}
                            className="flex items-center gap-1 text-[11px] font-bold text-[#3680CE]">
                            <MessageSquareText size={13} />Chat
                          </button>
                        </div>
                        <DeckViewer runId={selectedRunId} />
                      </div>
                    </Card>
                  </div>
                </div>
              )}

              {/* ══ Output Studio ══ */}
              {section === "outputs" && (
                <OutputStudio runs={runs} selectedId={selectedRunId} setSelectedId={setSelectedRunId}
                  detail={detail} onRefresh={refreshRuns} />
              )}

              {/* ══ Agent Hub ══ */}
              {section === "agents" && (
                <div className="grid grid-cols-2 gap-4">
                  {AGENTS.map(([name, mod, steps, Icon, color]) => {
                    const st = steps.map((n) => stream.steps[n]).filter(Boolean);
                    const live = runActive && st.length;
                    const label = live
                      ? (st.includes("running") ? "Running now" : st.every((s) => s === "done") ? "Completed this run" : "Queued")
                      : latest ? `Ready · last run ${latest.label}` : "No runs yet";
                    const detailLine = steps.map((n) => stream.detail[n]).filter(Boolean).join(" · ");
                    return (
                      <Card key={name}>
                        <div className="p-5">
                          <div className="grid h-11 w-11 place-items-center rounded-xl text-white" style={{ background: color }}>
                            <Icon size={20} />
                          </div>
                          <h3 className="mt-4 font-bold">{name}</h3>
                          <p className="text-xs text-slate-500">{label}</p>
                          {detailLine && <p className="mt-1 text-[10px] text-slate-400">{detailLine}</p>}
                          <p className="mt-1 text-[10px] text-slate-300">agents/{mod}.py</p>
                        </div>
                      </Card>
                    );
                  })}
                </div>
              )}
            </motion.div>
          </AnimatePresence>
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
                  <button onClick={() => sendCopilot()} className="self-end rounded-lg bg-[#3680CE] p-2 text-white">
                    <Send size={15} />
                  </button>
                </div>
              </div>
            </motion.aside>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

/* ── Output Studio ────────────────────────────────────────────────────── */
function OutputStudio({ runs, selectedId, setSelectedId, detail, onRefresh }) {
  const cards = detail?.segment_cards || [];
  const topSkus = detail?.top_skus || [];
  const assets = cards.flatMap((c) => c.assets.map((a) => ({ ...a, segment: c.label })));
  const summ = detail?.summary || {};

  return (
    <div className="space-y-5">
      {/* run picker + headline metrics */}
      <div className="grid gap-5 lg:grid-cols-[1fr_1.4fr]">
        <RecentOutputs runs={runs} selectedId={selectedId} onPick={setSelectedId} onRefresh={onRefresh} />
        <Card>
          <div className="grid grid-cols-2 gap-px overflow-hidden rounded-2xl bg-slate-100 sm:grid-cols-4">
            {[
              ["Outlets", fmtInt(summ.outlets)],
              ["Segments", summ.segment_count ?? "—"],
              ["Priority tiers", summ.priority_tiers ?? "—"],
              ["Total VPO", fmtRupee(summ.total_vpo)],
            ].map(([k, v]) => (
              <div key={k} className="bg-white p-4">
                <p className="text-[10px] uppercase text-slate-400">{k}</p>
                <p className="mt-1 text-lg font-black">{v}</p>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {!detail && <p className="text-xs text-slate-400">Loading run…</p>}

      {detail && (
        <>
          {/* Segmentation agent — refined segments */}
          <Card>
            <div className="p-5">
              <div className="flex items-center gap-2">
                <div className="grid h-7 w-7 place-items-center rounded-lg text-white" style={{ background: C.darkBlue }}>
                  <Store size={14} />
                </div>
                <h3 className="font-bold">Segmentation agent — refined segments</h3>
              </div>
              {cards.length === 0 ? (
                <p className="mt-3 text-xs text-slate-400">No segment cards in this run.</p>
              ) : (
                <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                  {cards.map((c) => (
                    <div key={c.cluster} className="rounded-xl border border-slate-100 p-4">
                      <div className="flex items-start justify-between gap-2">
                        <p className="text-xs font-black leading-snug">{c.label}</p>
                        <Chip tone={c.growth === "High" ? "green" : c.growth === "Medium" ? "amber" : "slate"}>{c.growth || "—"}</Chip>
                      </div>
                      <p className="mt-1 text-[10px] font-semibold uppercase tracking-wide text-[#3680CE]">
                        {c.channel} · {c.occasion}
                      </p>
                      <p className="mt-2 text-[11px] text-slate-500">{c.headline}</p>
                      {c.hero_skus.length > 0 && (
                        <div className="mt-3">
                          <p className="text-[9px] font-bold uppercase text-slate-400">Hero SKUs</p>
                          <div className="mt-1 flex flex-wrap gap-1">
                            {c.hero_skus.map((s) => <Chip key={s} tone="blue">{s}</Chip>)}
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </Card>

          <div className="grid gap-5 lg:grid-cols-2">
            {/* MSL agent — top SKUs across segments */}
            <Card>
              <div className="p-5">
                <div className="flex items-center gap-2">
                  <div className="grid h-7 w-7 place-items-center rounded-lg text-white" style={{ background: C.yellow }}>
                    <Zap size={14} />
                  </div>
                  <h3 className="font-bold">MSL agent — top SKUs across segments</h3>
                </div>
                {topSkus.length === 0 ? (
                  <p className="mt-3 text-xs text-slate-400">No hero-SKU data in this run.</p>
                ) : (
                  <ol className="mt-4 space-y-2">
                    {topSkus.map((t, i) => (
                      <li key={t.sku} className="flex items-center gap-3 rounded-xl bg-[#F7F5F3] p-3">
                        <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-[#02355A] text-[10px] font-bold text-white">
                          {i + 1}
                        </span>
                        <div className="min-w-0 flex-1">
                          <p className="text-xs font-bold">{t.sku}</p>
                          <p className="truncate text-[10px] text-slate-400">{t.segments.join(" · ")}</p>
                        </div>
                        <Chip tone={t.count > 1 ? "green" : "slate"}>{t.count} seg{t.count > 1 ? "s" : ""}</Chip>
                      </li>
                    ))}
                  </ol>
                )}
              </div>
            </Card>

            {/* Recommended assets (merch & space) */}
            <Card>
              <div className="p-5">
                <div className="flex items-center gap-2">
                  <div className="grid h-7 w-7 place-items-center rounded-lg text-white" style={{ background: C.green }}>
                    <Package size={14} />
                  </div>
                  <h3 className="font-bold">Recommended assets — merch &amp; space</h3>
                </div>
                {assets.length === 0 ? (
                  <p className="mt-3 text-xs text-slate-400">No merch/space actions called out.</p>
                ) : (
                  <ul className="mt-4 space-y-2">
                    {assets.map((a, i) => (
                      <li key={i} className="rounded-xl border border-slate-100 p-3">
                        <p className="text-xs font-semibold">{a.text}</p>
                        <div className="mt-1 flex flex-wrap items-center gap-2">
                          <Chip tone="blue">{a.segment}</Chip>
                          {a.kpi && <span className="text-[10px] text-slate-400">KPI: {a.kpi}</span>}
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </Card>
          </div>

          {/* Charts from segmentation + MSL */}
          {detail.charts?.length > 0 && (
            <Card>
              <div className="p-5">
                <h3 className="font-bold">Charts</h3>
                <div className="ps-scroll mt-3 flex gap-3 overflow-x-auto pb-2">
                  {detail.charts.map((c) => (
                    <img key={c} src={`/api/runs/${selectedId}/chart/${encodeURIComponent(c)}`} alt={c}
                      className="h-52 shrink-0 rounded-lg ring-1 ring-slate-200" loading="lazy" />
                  ))}
                </div>
              </div>
            </Card>
          )}

          {/* Deliverables */}
          <Card>
            <div className="p-5">
              <h3 className="font-bold">Deliverables</h3>
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                {(detail.files || []).map((f) => (
                  <a key={f.name} href={`/api/runs/${selectedId}/file/${encodeURIComponent(f.name)}`}
                    className="flex items-center justify-between rounded-xl border border-slate-100 p-3 hover:border-[#3680CE]">
                    <span className="truncate text-xs font-semibold">{f.name}</span>
                    <span className="ml-3 shrink-0 text-[10px] text-slate-400">
                      {f.slides ? `${f.slides} sl · ` : ""}{f.size_h}
                    </span>
                  </a>
                ))}
              </div>
            </div>
          </Card>
        </>
      )}
    </div>
  );
}
