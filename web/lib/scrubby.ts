// Types mirror src/profiler/core/render_json.py.

export type Dimensions = {
  completeness: number;
  uniqueness: number;
  validity: number;
  consistency: number;
};

export type Rule = { name: string; [param: string]: unknown };

export type RuleResult = {
  column: string;
  rule: Rule;
  source: "user" | "suggested";
  status: "PASS" | "FAIL" | "SKIPPED";
  evaluated_count: number;
  failed_count: number;
  failed_rows: number[];
};

export type Report = {
  dataset: string;
  score: number;
  issues: number;
  dimensions: Dimensions;
  summary: {
    row_count: number;
    column_count: number;
    null_count: number;
    duplicate_count: number;
    potential_issues: number;
  };
  columns: { name: string; inferred_type: string; null_pct: number; unique_pct: number }[];
  rules: RuleResult[];
  duplicates: { key: string[] | null; duplicate_records: number };
};

export type FileError = {
  dataset: string;
  error: { code: string; message: string; line: number | null; row_number: number | null };
};

export type FileResult = Report | FileError;

export const isError = (r: FileResult): r is FileError => "error" in r;

export class ApiError extends Error {
  constructor(public code: string, message: string) {
    super(message);
  }
}

function form(files: File[], rules: File | null): FormData {
  const data = new FormData();
  files.forEach((f) => data.append("files", f, f.name));
  if (rules) data.append("rules", rules);
  return data;
}

async function post(files: File[], rules: File | null, format: "json" | "html"): Promise<Response> {
  const response = await fetch(`/api/v1/reports?format=${format}`, {
    method: "POST",
    body: form(files, rules),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new ApiError(body.code ?? "HTTP_" + response.status, body.message ?? "Request failed");
  }
  return response;
}

export async function analyze(files: File[], rules: File | null): Promise<FileResult[]> {
  const body = (await (await post(files, rules, "json")).json()) as { reports: FileResult[] };
  return body.reports;
}

export async function downloadHtml(files: File[], rules: File | null): Promise<void> {
  const blob = await (await post(files, rules, "html")).blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `quality-report-${new Date().toISOString().slice(0, 10)}.html`;
  link.click();
  URL.revokeObjectURL(url);
}

const plural = (n: number, one: string, many: string) => `${n.toLocaleString()} ${n === 1 ? one : many}`;

/** Turn failed rules and duplicates into short, human-readable issue lines. */
export function issueLines(report: Report): string[] {
  const lines = report.rules
    .filter((r) => r.status === "FAIL")
    .sort((a, b) => b.failed_count - a.failed_count)
    .map((r) => {
      const n = r.failed_count;
      const col = r.column;
      switch (r.rule.name) {
        case "not_null":
          return `${plural(n, "missing value", "missing values")} in ${col}`;
        case "unique":
          return `${plural(n, "repeated value", "repeated values")} in ${col}`;
        case "valid_email":
          return `${plural(n, "invalid email", "invalid emails")} in ${col}`;
        case "type_is":
          return `${plural(n, "value", "values")} in ${col} not of type ${String(r.rule.type)}`;
        case "in_range":
          return `${plural(n, "value", "values")} out of range in ${col}`;
        case "accepted_values":
          return `${plural(n, "unexpected value", "unexpected values")} in ${col}`;
        default:
          return `${plural(n, "value", "values")} in ${col} fail ${r.rule.name}`;
      }
    });
  const dup = report.duplicates;
  if (dup.duplicate_records > 0) {
    const by = dup.key ? `by ${dup.key.join(", ")}` : "(whole row)";
    lines.push(`${plural(dup.duplicate_records, "duplicate record", "duplicate records")} ${by}`);
  }
  if (report.summary.null_count > 0) {
    lines.push(`${plural(report.summary.null_count, "null value", "null values")} across the dataset`);
  }
  return lines;
}
