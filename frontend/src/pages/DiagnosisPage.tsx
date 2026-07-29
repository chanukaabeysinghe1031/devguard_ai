import { FormEvent, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { clearSession, loadSession, type AuthSession } from "../api/client";
import { login, register } from "../api/diagnosis";
import {
  getAnalysis,
  getAnalysisStatus,
  getEvidence,
  getRecommendations,
  getSources,
  runDiagnosisPipeline,
  type AnalysisDetail,
  type EvidenceItem,
  type RecommendationItem,
  type SourceItem,
} from "../api/pipeline";
import { BackendStatusBadge } from "../components/BackendStatusBadge";

type Phase = "auth" | "upload" | "running" | "done" | "error";

const SAMPLE_HINTS = [
  "AWS AccessDenied during deployment",
  "Terraform undeclared resource",
  "Docker COPY failed",
  "GitHub Actions runner offline",
  "npm dependency conflict",
];

export function DiagnosisPage() {
  const [session, setSession] = useState<AuthSession | null>(() => loadSession());
  const [phase, setPhase] = useState<Phase>(session ? "upload" : "auth");
  const [email, setEmail] = useState("owner@example.com");
  const [password, setPassword] = useState("SecurePassword123!");
  const [fullName, setFullName] = useState("DevGuard Engineer");
  const [mode, setMode] = useState<"login" | "register">("login");
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [stage, setStage] = useState<string | null>(null);
  const [detail, setDetail] = useState<AnalysisDetail | null>(null);
  const [evidence, setEvidence] = useState<EvidenceItem[]>([]);
  const [sources, setSources] = useState<SourceItem[]>([]);
  const [recommendations, setRecommendations] = useState<RecommendationItem[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [lastAnalysisId, setLastAnalysisId] = useState<string | null>(null);
  const [history, setHistory] = useState<Array<{ id: string; title: string; status: string }>>([]);

  useEffect(() => {
    if (session) setPhase((current) => (current === "auth" ? "upload" : current));
  }, [session]);

  const confidencePct = useMemo(() => {
    const value = detail?.root_cause?.confidence ?? detail?.classification?.confidence;
    return value == null ? null : Math.round(Number(value) * 100);
  }, [detail]);

  async function handleAuth(event: FormEvent) {
    event.preventDefault();
    setMessage(null);
    try {
      const next =
        mode === "login"
          ? await login(email, password)
          : await register(email, password, fullName);
      setSession(next);
      setPhase("upload");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Authentication failed");
      setPhase("error");
    }
  }

  async function pollUntilDone(analysisRunId: string) {
    for (let attempt = 0; attempt < 90; attempt += 1) {
      const status = await getAnalysisStatus(analysisRunId);
      setProgress(status.progress_percentage);
      setStage(status.current_stage);
      if (["completed", "failed", "cancelled"].includes(status.status)) {
        return status.status;
      }
      await new Promise((resolve) => setTimeout(resolve, 1000));
    }
    throw new Error("Analysis timed out while waiting for completion.");
  }

  async function handleUpload(event: FormEvent) {
    event.preventDefault();
    if (isSubmitting) return;
    if (!file) {
      setMessage("Choose a CI/CD log file to analyse.");
      return;
    }
    const allowed = [".txt", ".log", ".json", ".yml", ".yaml", ".tf", ".md"];
    const lowerName = file.name.toLowerCase();
    if (!allowed.some((ext) => lowerName.endsWith(ext))) {
      setMessage("Unsupported file type. Allowed: .txt, .log, .json, .yml, .yaml, .tf, .md");
      return;
    }
    if (file.size <= 0) {
      setMessage("Uploaded file is empty.");
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setMessage("Uploaded file exceeds the 10MB size limit.");
      return;
    }
    setMessage(null);
    setIsSubmitting(true);
    setPhase("running");
    setProgress(5);
    setStage("uploading");
    setDetail(null);
    setEvidence([]);
    setSources([]);
    setRecommendations([]);
    try {
      const started = await runDiagnosisPipeline(file, title || file.name);
      setLastAnalysisId(started.analysisRunId);
      setProgress(Math.max(10, started.progress));
      const finalStatus =
        started.status === "completed" || started.status === "failed"
          ? started.status
          : await pollUntilDone(started.analysisRunId);
      const analysis = await getAnalysis(started.analysisRunId);
      setDetail(analysis);
      if (finalStatus !== "completed") {
        setMessage(analysis.error_message || `Analysis ended with status ${finalStatus}`);
        setPhase("error");
        return;
      }
      const [evidenceRes, sourcesRes, recommendationsRes] = await Promise.all([
        getEvidence(started.analysisRunId),
        getSources(started.analysisRunId),
        getRecommendations(started.analysisRunId),
      ]);
      setEvidence(evidenceRes.items || []);
      setSources(sourcesRes.items || []);
      setRecommendations(recommendationsRes.items || []);
      setProgress(100);
      setPhase("done");
      setHistory((prev) => [
        { id: started.analysisRunId, title: title || file.name, status: finalStatus },
        ...prev,
      ].slice(0, 8));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Diagnosis failed");
      setPhase("error");
    } finally {
      setIsSubmitting(false);
    }
  }

  function logout() {
    clearSession();
    setSession(null);
    setPhase("auth");
    setDetail(null);
  }

  return (
    <main className="mx-auto min-h-screen max-w-5xl px-6 py-10">
      <div className="mb-8 flex flex-wrap items-center justify-between gap-4">
        <div>
          <Link to="/" className="text-sm text-slate-400 hover:text-white">
            ← Home
          </Link>
          <h1 className="mt-2 text-3xl font-bold tracking-tight text-white">
            End-to-end diagnosis
          </h1>
          <p className="mt-1 text-slate-400">
            Upload a CI/CD log, retrieve grounded evidence, and view recommendations.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <BackendStatusBadge />
          {session ? (
            <button
              type="button"
              onClick={logout}
              className="rounded-lg border border-surface-border px-3 py-1.5 text-sm text-slate-300"
            >
              Sign out ({session.email})
            </button>
          ) : null}
        </div>
      </div>

      {message ? (
        <div className="mb-6 rounded-lg border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm text-rose-100">
          {message}
        </div>
      ) : null}

      {phase === "auth" || (!session && phase !== "running") ? (
        <form
          onSubmit={handleAuth}
          className="rounded-2xl border border-surface-border bg-surface-elevated p-6"
        >
          <div className="mb-4 flex gap-2">
            <button
              type="button"
              className={`rounded-lg px-3 py-1.5 text-sm ${mode === "login" ? "bg-accent text-white" : "bg-surface text-slate-300"}`}
              onClick={() => setMode("login")}
            >
              Sign in
            </button>
            <button
              type="button"
              className={`rounded-lg px-3 py-1.5 text-sm ${mode === "register" ? "bg-accent text-white" : "bg-surface text-slate-300"}`}
              onClick={() => setMode("register")}
            >
              Register
            </button>
          </div>
          {mode === "register" ? (
            <label className="mb-3 block text-sm text-slate-300">
              Full name
              <input
                className="mt-1 w-full rounded-lg border border-surface-border bg-surface px-3 py-2"
                value={fullName}
                onChange={(event) => setFullName(event.target.value)}
                required
              />
            </label>
          ) : null}
          <label className="mb-3 block text-sm text-slate-300">
            Email
            <input
              className="mt-1 w-full rounded-lg border border-surface-border bg-surface px-3 py-2"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </label>
          <label className="mb-4 block text-sm text-slate-300">
            Password
            <input
              className="mt-1 w-full rounded-lg border border-surface-border bg-surface px-3 py-2"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </label>
          <button type="submit" className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white">
            {isSubmitting ? "Please wait..." : "Continue"}
          </button>
        </form>
      ) : null}

      {session && (phase === "upload" || phase === "error" || phase === "done") ? (
        <form
          onSubmit={handleUpload}
          className="mb-8 rounded-2xl border border-surface-border bg-surface-elevated p-6"
        >
          <label className="mb-3 block text-sm text-slate-300">
            Incident title
            <input
              className="mt-1 w-full rounded-lg border border-surface-border bg-surface px-3 py-2"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="Optional — defaults to filename"
            />
          </label>
          <label className="mb-4 block text-sm text-slate-300">
            CI/CD log (.txt, .log, .json, .yaml, …)
            <input
              className="mt-1 block w-full text-sm text-slate-300"
              type="file"
              accept=".txt,.log,.json,.yml,.yaml,.tf,.md"
              onChange={(event) => setFile(event.target.files?.[0] || null)}
              required
            />
          </label>
          <div className="mb-4 flex flex-wrap gap-2">
            {SAMPLE_HINTS.map((hint) => (
              <button
                key={hint}
                type="button"
                className="rounded-full border border-surface-border px-3 py-1 text-xs text-slate-400"
                onClick={() => setTitle(hint)}
              >
                {hint}
              </button>
            ))}
          </div>
          <button type="submit" className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white">
            {isSubmitting ? "Submitting..." : "Analyse with grounded RAG + LLM"}
          </button>
        </form>
      ) : null}

      {phase === "running" ? (
        <section className="mb-8 rounded-2xl border border-surface-border bg-surface-elevated p-6">
          <h2 className="text-lg font-semibold text-white">Analysing…</h2>
          <p className="mt-1 text-sm text-slate-400">Stage: {stage || "queued"}</p>
          <div className="mt-4 h-2 overflow-hidden rounded-full bg-surface">
            <div className="h-full bg-accent transition-all" style={{ width: `${progress}%` }} />
          </div>
          <p className="mt-2 text-sm text-slate-400">{progress}%</p>
        </section>
      ) : null}

      {phase === "error" && lastAnalysisId ? (
        <div className="mb-6 flex items-center gap-3">
          <button
            type="button"
            onClick={() => setPhase("upload")}
            className="rounded-lg border border-surface-border px-3 py-1.5 text-sm text-slate-300"
          >
            Retry upload
          </button>
          <button
            type="button"
            onClick={async () => {
              try {
                const latest = await getAnalysis(lastAnalysisId);
                setDetail(latest);
              } catch {
                // ignore refresh errors in retry UI
              }
            }}
            className="rounded-lg border border-surface-border px-3 py-1.5 text-sm text-slate-300"
          >
            Refresh analysis
          </button>
        </div>
      ) : null}

      {history.length > 0 ? (
        <section className="mb-8 rounded-2xl border border-surface-border bg-surface-elevated p-6">
          <h2 className="text-lg font-semibold text-white">Recent analyses</h2>
          <ul className="mt-3 space-y-2 text-sm text-slate-300">
            {history.map((item) => (
              <li key={item.id} className="flex items-center justify-between gap-3 rounded-md bg-surface px-3 py-2">
                <span className="truncate">{item.title}</span>
                <span className="text-xs uppercase tracking-wide text-slate-400">{item.status}</span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {detail && (phase === "done" || phase === "error") ? (
        <div className="space-y-6">
          <section className="rounded-2xl border border-surface-border bg-surface-elevated p-6">
            <h2 className="text-lg font-semibold text-white">Diagnosis</h2>
            <dl className="mt-4 grid gap-4 sm:grid-cols-2">
              <div>
                <dt className="text-xs uppercase tracking-wide text-slate-500">Category</dt>
                <dd className="mt-1 text-slate-100">{detail.classification?.category || "—"}</dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wide text-slate-500">Confidence</dt>
                <dd className="mt-1 text-slate-100">{confidencePct == null ? "—" : `${confidencePct}%`}</dd>
              </div>
              <div className="sm:col-span-2">
                <dt className="text-xs uppercase tracking-wide text-slate-500">Root cause</dt>
                <dd className="mt-1 text-slate-100">{detail.root_cause?.summary || "—"}</dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wide text-slate-500">Latency</dt>
                <dd className="mt-1 text-slate-100">
                  {detail.processing_time_ms ?? detail.duration_ms ?? "—"} ms
                </dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wide text-slate-500">Route</dt>
                <dd className="mt-1 text-slate-100">
                  {detail.orchestration?.selected_route || "—"}
                  {detail.orchestration?.fallback_used ? " (fallback)" : ""}
                </dd>
              </div>
            </dl>
            {detail.limitations?.length ? (
              <div className="mt-4 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-50">
                <p className="font-medium">Limitations</p>
                <ul className="mt-1 list-disc pl-5">
                  {detail.limitations.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            ) : null}
          </section>

          <section className="rounded-2xl border border-surface-border bg-surface-elevated p-6">
            <h2 className="text-lg font-semibold text-white">
              Supporting evidence ({evidence.length})
            </h2>
            <div className="mt-4 space-y-3">
              {evidence.length === 0 ? (
                <p className="text-sm text-slate-400">No evidence rows persisted.</p>
              ) : (
                evidence.map((item) => (
                  <article key={item.id} className="rounded-lg border border-surface-border bg-surface p-4">
                    <p className="text-xs uppercase tracking-wide text-slate-500">
                      {item.evidence_type}
                      {item.source_file?.name ? ` · ${item.source_file.name}` : ""}
                      {item.line_start != null ? ` · L${item.line_start}` : ""}
                    </p>
                    <pre className="mt-2 whitespace-pre-wrap text-sm text-slate-200">{item.excerpt}</pre>
                    {item.explanation ? (
                      <p className="mt-2 text-sm text-slate-400">{item.explanation}</p>
                    ) : null}
                  </article>
                ))
              )}
            </div>
          </section>

          <section className="rounded-2xl border border-surface-border bg-surface-elevated p-6">
            <h2 className="text-lg font-semibold text-white">
              Retrieved sources ({sources.length})
            </h2>
            <div className="mt-4 space-y-3">
              {sources.length === 0 ? (
                <p className="text-sm text-slate-400">
                  No knowledge citations. Ensure ENABLE_RAG=true and knowledge base is indexed.
                </p>
              ) : (
                sources.map((item) => (
                  <article key={item.id} className="rounded-lg border border-surface-border bg-surface p-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="font-medium text-slate-100">
                        #{item.rank} {item.document.title}
                      </p>
                      <p className="text-xs text-slate-400">
                        sim {item.similarity_score?.toFixed(3) ?? "—"} · {item.document.provider}
                      </p>
                    </div>
                    <p className="mt-1 text-xs text-slate-500">{item.chunk.heading || "Section"}</p>
                    <p className="mt-2 text-sm text-slate-300">{item.chunk.content_preview}</p>
                    {item.document.source_url ? (
                      <a
                        className="mt-2 inline-block text-sm text-accent hover:underline"
                        href={item.document.source_url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Open source
                      </a>
                    ) : null}
                  </article>
                ))
              )}
            </div>
          </section>

          <section className="rounded-2xl border border-surface-border bg-surface-elevated p-6">
            <h2 className="text-lg font-semibold text-white">
              Recommendations ({recommendations.length})
            </h2>
            <ol className="mt-4 space-y-3">
              {recommendations.length === 0 ? (
                <p className="text-sm text-slate-400">No recommendations generated.</p>
              ) : (
                recommendations.map((item) => (
                  <li key={`${item.id}-${item.step_number}`} className="rounded-lg border border-surface-border bg-surface p-4">
                    <p className="font-medium text-slate-100">
                      {item.step_number}. {item.title}
                    </p>
                    <p className="mt-1 text-sm text-slate-300">{item.action}</p>
                    {item.explanation ? (
                      <p className="mt-2 text-sm text-slate-400">{item.explanation}</p>
                    ) : null}
                  </li>
                ))
              )}
            </ol>
          </section>

          <section className="rounded-2xl border border-surface-border bg-surface-elevated p-6 text-sm text-slate-400">
            <h2 className="text-lg font-semibold text-white">Runtime metadata</h2>
            <pre className="mt-3 overflow-x-auto whitespace-pre-wrap rounded-lg bg-surface p-3 text-xs text-slate-300">
              {JSON.stringify(
                {
                  token_usage: detail.token_usage,
                  cost: detail.cost,
                  orchestration: detail.orchestration,
                },
                null,
                2,
              )}
            </pre>
          </section>
        </div>
      ) : null}
    </main>
  );
}
