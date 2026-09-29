"use client";

import { useCountUp } from "@/lib/useCountUp";
import { issueLines, type Report } from "@/lib/scrubby";

const DIMENSIONS = ["completeness", "validity", "uniqueness", "consistency"] as const;
const BAR_CELLS = 24;

function grade(score: number): { label: string; tone: string } {
  if (score >= 90) return { label: "EXCELLENT", tone: "good" };
  if (score >= 75) return { label: "GOOD", tone: "ok" };
  if (score >= 50) return { label: "NEEDS WORK", tone: "warn" };
  return { label: "POOR", tone: "bad" };
}

function Stat({ label, value }: { label: string; value: number }) {
  const shown = useCountUp(value, 900);
  return (
    <div className="stat">
      <span className="stat-label">{label}</span>
      <span className="stat-value">{Math.round(shown).toLocaleString()}</span>
    </div>
  );
}

/** A text bar like ██████░░░░ that fills up as the value counts up. */
function Bar({ name, value, delay }: { name: string; value: number; delay: number }) {
  const shown = useCountUp(value, 1200 + delay);
  const filled = Math.round((shown / 100) * BAR_CELLS);
  return (
    <li className={`bar tone-${grade(value).tone}`}>
      <span className="bar-label">{name.toUpperCase().padEnd(12, " ")}</span>
      <span className="bar-cells" aria-hidden="true">
        {"█".repeat(filled)}
        <span className="bar-empty">{"░".repeat(BAR_CELLS - filled)}</span>
      </span>
      <span className="bar-value">{shown.toFixed(1).padStart(5, " ")}%</span>
      <span className="sr-only">
        {name} {value} percent
      </span>
    </li>
  );
}

export function ReportCard({ report }: { report: Report }) {
  const issues = issueLines(report);
  const s = report.summary;
  const score = useCountUp(report.score);
  const { label, tone } = grade(report.score);

  return (
    <article className="panel report" aria-labelledby={`title-${report.dataset}`}>
      <h2 className="panel-title" id={`title-${report.dataset}`}>
        [ DATASET: {report.dataset} ]
      </h2>

      <div className="stats">
        <Stat label="ROWS" value={s.row_count} />
        <Stat label="COLUMNS" value={s.column_count} />
        <Stat label="DUPLICATES" value={s.duplicate_count} />
        <Stat label="ISSUES" value={report.issues} />
      </div>

      <div className={`score tone-${tone}`}>
        <span className="score-caption">QUALITY SCORE</span>
        <span className="score-value">{score.toFixed(1)}</span>
        <span className="score-rule">─────────</span>
        <span className="score-grade">
          /100 · {label}
        </span>
        <span className="sr-only">
          Quality score {report.score} out of 100, {label}
        </span>
      </div>

      <ul className="bars" aria-label="Quality dimensions">
        {DIMENSIONS.map((name, i) => (
          <Bar key={name} name={name} value={report.dimensions[name]} delay={i * 200} />
        ))}
      </ul>

      <section className="issues" aria-labelledby={`issues-${report.dataset}`}>
        <h3 id={`issues-${report.dataset}`}>&gt; ISSUES</h3>
        {issues.length === 0 ? (
          <p className="clean">[OK] NO ISSUES FOUND. DATASET IS SPOTLESS.</p>
        ) : (
          <ul>
            {issues.map((line, i) => (
              <li key={line} style={{ animationDelay: `${900 + i * 150}ms` }}>
                <span className="warn-tag">[!]</span> {line}
              </li>
            ))}
          </ul>
        )}
      </section>
    </article>
  );
}
