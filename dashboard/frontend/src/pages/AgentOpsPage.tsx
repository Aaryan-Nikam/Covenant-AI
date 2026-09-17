import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Clipboard,
  Database,
  FileText,
  Play,
  RefreshCcw,
  UploadCloud,
} from "lucide-react";

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

type JobStatus = "queued" | "running" | "completed" | "failed" | "cancelled";

interface UploadJob {
  id: string;
  status: JobStatus;
  created_at: string;
  updated_at: string;
  campaign_name: string | null;
  campaign_url: string | null;
  source: string | null;
  source_project_id: string | null;
  source_project_name: string | null;
  row_count: number;
  columns: string[];
  csv_path: string;
  error: string | null;
  run_log_path: string | null;
}

interface UploadJobList {
  jobs: UploadJob[];
  total: number;
}

function statusClass(status: JobStatus) {
  switch (status) {
    case "completed":
      return "bg-emerald-50 text-emerald-700 border-emerald-200";
    case "running":
      return "bg-blue-50 text-blue-700 border-blue-200";
    case "failed":
      return "bg-red-50 text-red-700 border-red-200";
    case "cancelled":
      return "bg-zinc-100 text-zinc-700 border-zinc-200";
    default:
      return "bg-amber-50 text-amber-700 border-amber-200";
  }
}

function formatTime(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export function AgentOpsPage() {
  const [jobs, setJobs] = useState<UploadJob[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selected = jobs.find((job) => job.id === selectedId) ?? jobs[0] ?? null;
  const stats = useMemo(() => {
    const byStatus = jobs.reduce<Record<JobStatus, number>>(
      (acc, job) => ({ ...acc, [job.status]: acc[job.status] + 1 }),
      { queued: 0, running: 0, completed: 0, failed: 0, cancelled: 0 }
    );
    const totalRows = jobs.reduce((sum, job) => sum + job.row_count, 0);
    return { byStatus, totalRows };
  }, [jobs]);

  async function loadJobs() {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${BASE_URL}/agent-ops/upload-jobs`);
      if (!response.ok) throw new Error(await response.text());
      const data = (await response.json()) as UploadJobList;
      setJobs(data.jobs);
      setSelectedId((current) => current ?? data.jobs[0]?.id ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadJobs();
    const timer = window.setInterval(() => void loadJobs(), 5000);
    return () => window.clearInterval(timer);
  }, []);

  const webhookJson = `POST ${BASE_URL}/agent-ops/webhooks/processed-csv
Headers:
  Content-Type: application/json
  X-Agent-Webhook-Secret: <secret>

Body:
{
  "campaign_name": "Dripify campaign",
  "campaign_url": "https://app.dripify.io/...",
  "source": "n8n",
  "source_project_id": "linkedin-recruiter-project-id",
  "csv_content": "first_name,last_name,email,linkedin_url\\n..."
}`;

  const runnerCommand = selected
    ? `PYTHONPATH=agent_desktop python -m azmeth_agent.runner --config agent_desktop/config/client.example.yaml --job-id ${selected.id} --job-queue-dir /tmp/azmeth-agent/upload-jobs --campaign "${selected.campaign_name ?? "Dripify campaign"}" --mode local`
    : "";

  return (
    <main className="min-h-screen bg-zinc-50 text-zinc-950">
      <div className="border-b border-zinc-200 bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">Agent Ops</p>
            <h1 className="mt-1 text-2xl font-semibold tracking-tight">Dripify Upload Queue</h1>
          </div>
          <button
            onClick={() => void loadJobs()}
            className="inline-flex h-9 items-center gap-2 rounded-md border border-zinc-300 bg-white px-3 text-sm font-medium text-zinc-800 hover:bg-zinc-100"
          >
            <RefreshCcw className="h-4 w-4" />
            Refresh
          </button>
        </div>
      </div>

      <div className="mx-auto grid max-w-7xl gap-6 px-6 py-6">
        <section className="grid gap-3 md:grid-cols-4">
          <Metric label="Queued" value={stats.byStatus.queued} icon={<UploadCloud className="h-4 w-4" />} />
          <Metric label="Running" value={stats.byStatus.running} icon={<Play className="h-4 w-4" />} />
          <Metric label="Completed" value={stats.byStatus.completed} icon={<CheckCircle2 className="h-4 w-4" />} />
          <Metric label="Lead Rows" value={stats.totalRows} icon={<Database className="h-4 w-4" />} />
        </section>

        {error ? (
          <div className="flex items-start gap-2 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
            <AlertCircle className="mt-0.5 h-4 w-4" />
            <span>{error}</span>
          </div>
        ) : null}

        <section className="grid gap-6 lg:grid-cols-[1.4fr_0.9fr]">
          <div className="overflow-hidden rounded-lg border border-zinc-200 bg-white">
            <div className="flex items-center justify-between border-b border-zinc-200 px-4 py-3">
              <h2 className="text-sm font-semibold">Incoming CSV Jobs</h2>
              <span className="text-xs text-zinc-500">{loading ? "Refreshing" : `${jobs.length} jobs`}</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px] text-left text-sm">
                <thead className="bg-zinc-50 text-xs uppercase text-zinc-500">
                  <tr>
                    <th className="px-4 py-3 font-medium">Campaign</th>
                    <th className="px-4 py-3 font-medium">Source</th>
                    <th className="px-4 py-3 font-medium">Rows</th>
                    <th className="px-4 py-3 font-medium">Status</th>
                    <th className="px-4 py-3 font-medium">Created</th>
                  </tr>
                </thead>
                <tbody>
                  {jobs.map((job) => (
                    <tr
                      key={job.id}
                      onClick={() => setSelectedId(job.id)}
                      className={`cursor-pointer border-t border-zinc-100 hover:bg-zinc-50 ${selected?.id === job.id ? "bg-zinc-50" : ""}`}
                    >
                      <td className="px-4 py-3">
                        <div className="font-medium text-zinc-900">{job.campaign_name ?? "Unassigned"}</div>
                        <div className="mt-0.5 max-w-xs truncate text-xs text-zinc-500">{job.id}</div>
                      </td>
                      <td className="px-4 py-3 text-zinc-700">
                        {job.source_project_name ?? job.source_project_id ?? job.source ?? "Webhook"}
                      </td>
                      <td className="px-4 py-3 tabular-nums">{job.row_count}</td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex rounded-md border px-2 py-1 text-xs font-medium ${statusClass(job.status)}`}>
                          {job.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-zinc-600">{formatTime(job.created_at)}</td>
                    </tr>
                  ))}
                  {jobs.length === 0 ? (
                    <tr>
                      <td className="px-4 py-8 text-center text-sm text-zinc-500" colSpan={5}>
                        No processed CSV jobs received yet.
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          </div>

          <aside className="grid gap-4">
            <Panel title="Selected Job" icon={<FileText className="h-4 w-4" />}>
              {selected ? (
                <div className="grid gap-3 text-sm">
                  <Field label="CSV path" value={selected.csv_path} />
                  <Field label="Columns" value={selected.columns.join(", ")} />
                  <Field label="Campaign URL" value={selected.campaign_url ?? "Not provided"} />
                  <Field label="Run log" value={selected.run_log_path ?? "Not started"} />
                  {selected.error ? <Field label="Error" value={selected.error} /> : null}
                  <div className="rounded-md bg-zinc-950 p-3 font-mono text-xs text-zinc-100">
                    {runnerCommand}
                  </div>
                </div>
              ) : (
                <p className="text-sm text-zinc-500">Select a job to see upload details.</p>
              )}
            </Panel>

            <Panel title="n8n Webhook" icon={<Clipboard className="h-4 w-4" />}>
              <pre className="max-h-80 overflow-auto rounded-md bg-zinc-950 p-3 text-xs leading-5 text-zinc-100">
                {webhookJson}
              </pre>
            </Panel>
          </aside>
        </section>
      </div>
    </main>
  );
}

function Metric({ label, value, icon }: { label: string; value: number; icon: ReactNode }) {
  return (
    <div className="rounded-lg border border-zinc-200 bg-white px-4 py-3">
      <div className="flex items-center justify-between text-zinc-500">
        <span className="text-sm">{label}</span>
        {icon}
      </div>
      <div className="mt-2 text-2xl font-semibold tabular-nums">{value}</div>
    </div>
  );
}

function Panel({ title, icon, children }: { title: string; icon: ReactNode; children: ReactNode }) {
  return (
    <div className="rounded-lg border border-zinc-200 bg-white">
      <div className="flex items-center gap-2 border-b border-zinc-200 px-4 py-3 text-sm font-semibold">
        {icon}
        {title}
      </div>
      <div className="p-4">{children}</div>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs font-medium uppercase text-zinc-500">{label}</div>
      <div className="mt-1 break-all text-zinc-900">{value}</div>
    </div>
  );
}
