import { useEffect, useState } from "react";
import { useScheduler } from "@/hooks/useScheduler";
import type { CrawlerJobRun, PipelineRunResult, ResetResult } from "@/types/scheduler";
import type { ArticleCategory } from "@/types/api";
import { CATEGORY_OPTIONS } from "@/constants/categories";

interface JobFormState {
  name: string;
  crawler_name: string;
  source_id: string;
  job_type: "scheduled" | "one_off";
  interval_minutes: number;
  payload_meta: string;
  enabled: boolean;
}

const defaultForm: JobFormState = {
  name: "",
  crawler_name: "",
  source_id: "",
  job_type: "scheduled",
  interval_minutes: 60,
  payload_meta: '{"meta": {"max_pages": 1}}',
  enabled: true,
};

export default function SchedulerPage() {
  const {
    jobs,
    metas,
    loading,
    error,
    refresh,
    fetchRuns,
    triggerJob,
    createJob,
    deleteJob,
    runPipeline,
    celeryStatus,
    celeryError,
    refreshCelery,
    resetData,
    lastReset,
    runPipelineQuick,
  } = useScheduler();

  const [form, setForm] = useState<JobFormState>(defaultForm);
  const [selectedJob, setSelectedJob] = useState<string | null>(null);
  const [runs, setRuns] = useState<CrawlerJobRun[]>([]);
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [pipelineResult, setPipelineResult] = useState<PipelineRunResult | null>(null);
  const [pipelineError, setPipelineError] = useState<string | null>(null);
  const [pipelineRunning, setPipelineRunning] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [resetError, setResetError] = useState<string | null>(null);
  const [resetResult, setResetResult] = useState<ResetResult | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<ArticleCategory | "">("");
  const [quickRunning, setQuickRunning] = useState(false);
  const [quickError, setQuickError] = useState<string | null>(null);
  const recentReset = resetResult ?? lastReset;

  useEffect(() => {
    if (!selectedJob) {
      setRuns([]);
      return;
    }
    fetchRuns(selectedJob).then(setRuns).catch(() => setRuns([]));
  }, [selectedJob, fetchRuns]);

  useEffect(() => {
    if (lastReset) {
      setResetResult(lastReset);
    }
  }, [lastReset]);

  const handleField = (key: keyof JobFormState, value: string | boolean | number) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const handleCategoryChange = (value: ArticleCategory | "") => {
    setSelectedCategory(value);
    setForm((prev) => ({ ...prev, crawler_name: "" }));
  };

  const filteredMetas = selectedCategory
    ? metas.filter((meta) => (meta.category || "") === selectedCategory)
    : [];

  const handleSubmit = async () => {
    setFormError(null);
    setSubmitting(true);
    try {
      let payload;
      try {
        payload = JSON.parse(form.payload_meta || "{}");
      } catch {
        throw new Error("payload 元数据需要是合法的 JSON");
      }
      await createJob({
        name: form.name,
        crawler_name: form.crawler_name,
        source_id: form.source_id,
        job_type: form.job_type,
        interval_minutes: form.job_type === "scheduled" ? form.interval_minutes : undefined,
        payload,
        enabled: form.enabled,
      });
      setForm(defaultForm);
      setSelectedCategory("");
      refresh();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "提交失败");
    } finally {
      setSubmitting(false);
    }
  };

  const handleTrigger = async (jobId: string) => {
    await triggerJob(jobId, {});
    refresh();
    if (selectedJob === jobId) {
      const updatedRuns = await fetchRuns(jobId);
      setRuns(updatedRuns);
    }
  };

  const handleDelete = async (jobId: string) => {
    const confirmed = window.confirm("确认删除该任务？删除后不可恢复。");
    if (!confirmed) return;
    await deleteJob(jobId);
    if (selectedJob === jobId) {
      setSelectedJob(null);
      setRuns([]);
    }
    refresh();
  };

  const handlePipelineRun = async () => {
    setPipelineRunning(true);
    setPipelineError(null);
    setQuickError(null);
    try {
      const result = await runPipeline();
      setPipelineResult(result);
      refresh();
    } catch (err) {
      setPipelineError(err instanceof Error ? err.message : "执行失败");
    } finally {
      setPipelineRunning(false);
      refreshCelery();
    }
  };

  const handlePipelineQuickRun = async () => {
    setQuickRunning(true);
    setQuickError(null);
    setPipelineError(null);
    try {
      const result = await runPipelineQuick();
      setPipelineResult(result);
      refresh();
    } catch (err) {
      setQuickError(err instanceof Error ? err.message : "执行失败");
    } finally {
      setQuickRunning(false);
      refreshCelery();
    }
  };

  const handleReset = async () => {
    const confirmed = window.confirm("将清空数据库与缓存中的所有文章与任务，确认继续？");
    if (!confirmed) return;
    setResetting(true);
    setResetError(null);
    try {
      const result = await resetData();
      setResetResult(result);
      setPipelineResult(null);
      refresh();
    } catch (err) {
      setResetError(err instanceof Error ? err.message : "清理失败");
    } finally {
      setResetting(false);
      refreshCelery();
    }
  };

  return (
    <div>
      <div className="page-header">
        <h1>采集与调度</h1>
        <span style={{ color: "#64748b" }}>统一管理爬虫任务、流水线执行与数据清理。</span>
      </div>

      <div className="panel" style={{ marginBottom: 24 }}>
        <div className="toolbar" style={{ justifyContent: "space-between", marginBottom: 12 }}>
          <div>
            <h3 style={{ margin: 0 }}>一键执行采集 + 格式化 + AI</h3>
            <p style={{ margin: 0, color: "#64748b", fontSize: 13 }}>
              排查数据缺失前，先确认流水线运行是否正常。
            </p>
          </div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button className="ghost" onClick={refreshCelery}>
              检查 Celery
            </button>
            <button className="ghost" onClick={handlePipelineQuickRun} disabled={quickRunning}>
              {quickRunning ? "检测中..." : "快速检测（每爬虫 1 条）"}
            </button>
            <button className="primary" onClick={handlePipelineRun} disabled={pipelineRunning}>
              {pipelineRunning ? "执行中..." : "运行完整流程"}
            </button>
            <button className="ghost" style={{ color: "#f87171" }} onClick={handleReset} disabled={resetting}>
              {resetting ? "清理中..." : "清空所有数据"}
            </button>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
          <span>Celery 状态：</span>
          {celeryStatus ? (
            <span className={`status-pill ${celeryStatus.running ? "up" : "down"}`}>
              {celeryStatus.running ? "在线" : "未运行"}
            </span>
          ) : (
            <span className="status-pill down">未知</span>
          )}
          <span style={{ color: "#94a3b8", fontSize: 13 }}>{celeryStatus?.detail || celeryError || "--"}</span>
        </div>

        {pipelineError ? <div style={{ color: "#b91c1c" }}>{pipelineError}</div> : null}
        {quickError ? <div style={{ color: "#b91c1c" }}>{quickError}</div> : null}
        {resetError ? <div style={{ color: "#b91c1c" }}>{resetError}</div> : null}

        {recentReset ? (
          <div style={{ color: "#94a3b8", fontSize: 13, marginBottom: 8 }}>
            最近清理完成：Redis {recentReset.redis_cleared ? "已清理" : "未执行"}；
            表数 {recentReset.truncated_tables.length}；
            目录 {recentReset.cleared_dirs.length}
          </div>
        ) : null}

        {pipelineResult ? (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(160px,1fr))", gap: 12 }}>
            <div style={{ background: "#0f172a", borderRadius: 8, padding: 12 }}>
              <strong style={{ fontSize: 20 }}>{pipelineResult.crawled}</strong>
              <div style={{ color: "#94a3b8", fontSize: 12 }}>爬虫条数</div>
            </div>
            <div style={{ background: "#0f172a", borderRadius: 8, padding: 12 }}>
              <strong style={{ fontSize: 20 }}>
                {pipelineResult.outbox_processed}/{pipelineResult.outbox_files}
              </strong>
              <div style={{ color: "#94a3b8", fontSize: 12 }}>Outbox 入库（成功/总数）</div>
            </div>
            <div style={{ background: "#0f172a", borderRadius: 8, padding: 12 }}>
              <strong style={{ fontSize: 18 }}>
                {pipelineResult.ai_summary_enqueued}/{pipelineResult.ai_summary_pending}
              </strong>
              <div style={{ color: "#94a3b8", fontSize: 12 }}>摘要（已入队/待处理）</div>
            </div>
            <div style={{ background: "#0f172a", borderRadius: 8, padding: 12 }}>
              <strong style={{ fontSize: 18 }}>
                {pipelineResult.ai_translation_enqueued}/{pipelineResult.ai_translation_pending}
              </strong>
              <div style={{ color: "#94a3b8", fontSize: 12 }}>翻译（已入队/待处理）</div>
            </div>
            <div style={{ background: "#0f172a", borderRadius: 8, padding: 12 }}>
              <strong style={{ fontSize: 18 }}>
                {pipelineResult.ai_analysis_enqueued}/{pipelineResult.ai_analysis_pending}
              </strong>
              <div style={{ color: "#94a3b8", fontSize: 12 }}>分析（已入队/待处理）</div>
            </div>
          </div>
        ) : (
          <div style={{ color: "#94a3b8", fontSize: 13 }}>
            尚未执行，可点击“快速检测（每爬虫 1 条）”或“运行完整流程”验证一次。
          </div>
        )}
      </div>

      <div className="panel" style={{ marginBottom: 24 }}>
        <h3 style={{ marginTop: 0 }}>新建任务</h3>
        {formError ? <div style={{ color: "#b91c1c" }}>{formError}</div> : null}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(200px,1fr))", gap: 12 }}>
          <input value={form.name} placeholder="任务名称" onChange={(e) => handleField("name", e.target.value)} />
          <select
            value={selectedCategory}
            onChange={(e) => handleCategoryChange((e.target.value || "") as ArticleCategory | "")}
          >
            <option value="">选择分类</option>
            {CATEGORY_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <select
            value={form.crawler_name}
            onChange={(e) => handleField("crawler_name", e.target.value)}
            disabled={!selectedCategory || !filteredMetas.length}
          >
            <option value="">
              {!selectedCategory ? "请先选择分类" : filteredMetas.length ? "选择爬虫" : "该分类暂无爬虫"}
            </option>
            {filteredMetas.map((meta) => (
              <option key={meta.name} value={meta.name}>
                {meta.label || meta.name}
              </option>
            ))}
          </select>
          <input
            value={form.source_id}
            placeholder="来源 ID（sources.id）"
            onChange={(e) => handleField("source_id", e.target.value)}
          />
          <select value={form.job_type} onChange={(e) => handleField("job_type", e.target.value as JobFormState["job_type"])}>
            <option value="scheduled">定时任务</option>
            <option value="one_off">临时任务</option>
          </select>
          {form.job_type === "scheduled" ? (
            <input
              type="number"
              min={1}
              value={form.interval_minutes}
              placeholder="间隔（分钟）"
              onChange={(e) => handleField("interval_minutes", Number(e.target.value))}
            />
          ) : null}
          <textarea
            value={form.payload_meta}
            placeholder='{"meta":{"max_pages":1}}'
            rows={3}
            onChange={(e) => handleField("payload_meta", e.target.value)}
          />
          <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <input type="checkbox" checked={form.enabled} onChange={(e) => handleField("enabled", e.target.checked)} /> 启用
          </label>
        </div>
        <button className="primary" style={{ marginTop: 12 }} onClick={handleSubmit} disabled={submitting}>
          {submitting ? "提交中..." : "创建任务"}
        </button>
      </div>

      <div className="panel">
        <div className="toolbar">
          <button className="ghost" onClick={refresh}>
            刷新
          </button>
        </div>
        {loading ? (
          <div>加载中...</div>
        ) : error ? (
          <div style={{ color: "#b91c1c" }}>{error}</div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>名称</th>
                <th>爬虫</th>
                <th>类型</th>
                <th>计划</th>
                <th>状态</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((job) => (
                <tr key={job.id}>
                  <td>{job.name}</td>
                  <td>{job.crawler_name}</td>
                  <td>{job.job_type === "scheduled" ? "定时" : "单次"}</td>
                  <td>{job.schedule_cron || (job.interval_minutes ? `每 ${job.interval_minutes} 分钟` : "--")}</td>
                  <td>
                    <span className={`status-pill ${job.enabled ? "up" : "down"}`}>
                      {job.enabled ? job.last_status || "active" : "disabled"}
                    </span>
                  </td>
                  <td style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                    <button className="ghost" onClick={() => setSelectedJob(job.id)}>
                      历史
                    </button>
                    <button className="ghost" onClick={() => handleTrigger(job.id)}>
                      立即执行
                    </button>
                    <button className="ghost" style={{ color: "#f87171" }} onClick={() => handleDelete(job.id)}>
                      删除
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {selectedJob ? (
        <div className="panel" style={{ marginTop: 24 }}>
          <div className="toolbar" style={{ justifyContent: "space-between" }}>
            <strong>执行历史</strong>
            <button className="ghost" onClick={async () => setRuns(await fetchRuns(selectedJob))}>
              刷新
            </button>
          </div>
          {!runs.length ? (
            <div className="empty-state">暂无记录</div>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>时间</th>
                  <th>状态</th>
                  <th>结果数</th>
                  <th>耗时</th>
                  <th>错误</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => (
                  <tr key={run.id}>
                    <td>{new Date(run.started_at).toLocaleString()}</td>
                    <td>
                      <span className={`status-pill ${run.status === "success" ? "up" : "down"}`}>{run.status}</span>
                    </td>
                    <td>{run.result_count}</td>
                    <td>
                      {run.finished_at
                        ? `${Math.round((new Date(run.finished_at).getTime() - new Date(run.started_at).getTime()) / 1000)}s`
                        : "--"}
                    </td>
                    <td>{run.error_message || "--"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      ) : null}
    </div>
  );
}
