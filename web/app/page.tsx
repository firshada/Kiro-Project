"use client";

import { useRef, useState } from "react";
import { ReportCard } from "@/components/ReportCard";
import { analyze, ApiError, downloadHtml, isError, type FileResult } from "@/lib/scrubby";

const MAX_FILES = 10;

type Status = "idle" | "analyzing" | "done" | "error";

export default function Home() {
  const [files, setFiles] = useState<File[]>([]);
  const [rules, setRules] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [status, setStatus] = useState<Status>("idle");
  const [message, setMessage] = useState("");
  const [results, setResults] = useState<FileResult[]>([]);
  const [active, setActive] = useState(0);
  const [downloading, setDownloading] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  function addFiles(list: FileList | null) {
    if (!list) return;
    const csvs = Array.from(list).filter((f) => f.name.toLowerCase().endsWith(".csv"));
    const skipped = list.length - csvs.length;
    setFiles((prev) => [...prev, ...csvs].slice(0, MAX_FILES));
    setMessage(skipped ? `Skipped ${skipped} non-CSV file(s). Scrubby reads CSV only.` : "");
    setStatus("idle");
  }

  async function run() {
    setStatus("analyzing");
    setMessage("");
    try {
      // Keep the scanning animation visible briefly so fast results still feel like a reveal.
      const [reports] = await Promise.all([analyze(files, rules), new Promise((r) => setTimeout(r, 900))]);
      setResults(reports);
      setActive(0);
      setStatus("done");
    } catch (err) {
      setStatus("error");
      setMessage(
        err instanceof ApiError
          ? `${err.code}: ${err.message}`
          : "Couldn't reach the Scrubby API. Is it running on port 8000?",
      );
    }
  }

  async function download() {
    setDownloading(true);
    try {
      await downloadHtml(files, rules);
    } catch {
      setMessage("Download failed. Try again.");
    } finally {
      setDownloading(false);
    }
  }

  function reset() {
    setFiles([]);
    setRules(null);
    setResults([]);
    setStatus("idle");
    setMessage("");
  }

  const current = results[active];

  return (
    <main className="shell">
      <div className="glow" aria-hidden="true" />
      <header className="brand">
        <span className="logo" aria-hidden="true">◆</span>
        <h1>Scrubby</h1>
        <p>Drop a dataset. Get a quality score in seconds.</p>
      </header>

      <section className="card upload" aria-labelledby="upload-title">
        <h2 id="upload-title">Upload dataset</h2>
        <label
          className={`drop ${dragging ? "dragging" : ""} ${status === "analyzing" ? "scanning" : ""}`}
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            addFiles(e.dataTransfer.files);
          }}
        >
          <input
            ref={input}
            type="file"
            accept=".csv,text/csv"
            multiple
            className="sr-only"
            onChange={(e) => {
              addFiles(e.target.files);
              e.target.value = "";
            }}
          />
          <span className="drop-icon" aria-hidden="true">⇪</span>
          <span className="drop-title">
            {status === "analyzing" ? "Scanning your data…" : "Drop CSV files here or click to browse"}
          </span>
          <span className="muted">Up to {MAX_FILES} files, 100 MB each</span>
          {status === "analyzing" && <span className="scanline" aria-hidden="true" />}
        </label>

        {files.length > 0 && (
          <ul className="chips" aria-label="Selected files">
            {files.map((f, i) => (
              <li key={`${f.name}-${i}`} className="chip">
                {f.name}
                <button
                  type="button"
                  aria-label={`Remove ${f.name}`}
                  onClick={() => setFiles((prev) => prev.filter((_, j) => j !== i))}
                >
                  ×
                </button>
              </li>
            ))}
          </ul>
        )}

        <details className="advanced">
          <summary>Advanced: validation rules (optional)</summary>
          <label className="rules-picker">
            Rule_Set JSON file
            <input type="file" accept=".json,application/json" onChange={(e) => setRules(e.target.files?.[0] ?? null)} />
          </label>
          <p className="muted">Without rules, Scrubby suggests them from the profile.</p>
        </details>

        <div className="actions">
          <button
            type="button"
            className="primary"
            disabled={files.length === 0 || status === "analyzing"}
            onClick={run}
          >
            {status === "analyzing" ? <span className="spinner" aria-hidden="true" /> : null}
            {status === "analyzing" ? "Analyzing" : "Analyze"}
          </button>
          {files.length > 0 && status !== "analyzing" && (
            <button type="button" className="ghost" onClick={reset}>
              Clear
            </button>
          )}
        </div>
        <p className="message" role="status" aria-live="polite">
          {message}
        </p>
      </section>

      {status === "done" && current && (
        <section aria-live="polite" className="results">
          {results.length > 1 && (
            <div className="tabs" role="tablist" aria-label="Datasets">
              {results.map((r, i) => (
                <button
                  key={`${r.dataset}-${i}`}
                  role="tab"
                  aria-selected={i === active}
                  className={`tab ${i === active ? "active" : ""}`}
                  onClick={() => setActive(i)}
                >
                  {isError(r) ? "✕ " : ""}
                  {r.dataset}
                </button>
              ))}
            </div>
          )}

          {isError(current) ? (
            <article className="card error-card" key={`err-${active}`}>
              <h2>{current.dataset}</h2>
              <p>
                <strong>{current.error.code}</strong>: {current.error.message}
                {current.error.line ? ` (line ${current.error.line})` : ""}
                {current.error.row_number ? ` (row ${current.error.row_number})` : ""}
              </p>
            </article>
          ) : (
            <ReportCard key={`rep-${active}`} report={current} />
          )}

          <div className="actions">
            <button type="button" className="primary" disabled={downloading} onClick={download}>
              {downloading ? "Preparing…" : "Download report"}
            </button>
          </div>
        </section>
      )}

      <footer className="foot muted">Stateless: your files are analyzed and never stored.</footer>
    </main>
  );
}
