import { useCallback, useEffect, useMemo, useState } from "react";
import { useScheduler } from "@/hooks/useScheduler";
import type { LogLine } from "@/types/api";
import type { CrawlerJobItem, CrawlerJobRun, PipelineRunDetail, PipelineRunItem, SourceProxyItem, ProxyMode } from "@/types/scheduler";
import { fetchSourceProxyList, updateSourceProxyConfig } from "@/services/scheduler";

type JobType = "scheduled" | "one_off";

interface JobFormState {
  name: string;
  crawler_name: string;
  job_type: JobType;
  interval_minutes?: number;
  schedule_cron?: string;
  max_pages?: number;
  max_items?: number;
  timeout?: number;
  max_attempts?: number;
  request_max_retries?: number;
  enabled: boolean;
}

interface LogModalState {
  visible: boolean;
  title: string;
  path?: string | null;
  lines: string[];
  truncated: boolean;
  loading: boolean;
  error?: string | null;
}

const defaultForm: JobFormState = {
  name: "",
  crawler_name: "",
  job_type: "scheduled",
  interval_minutes: 60,
  max_pages: 1,
  max_items: 20,
  timeout: 20,
  max_attempts: 3,
  request_max_retries: 3,
  enabled: true,
};

function StatusBadge({ status }: { status?: string | null }) {
  const normalized = status || "-";
  const map: Record<string, { label: string; className: string }> = {
    success: { label: "成功", className: "pill pill--ok" },
    failed: { label: "失败", className: "pill pill--warn" },
    running: { label: "进行中", className: "pill pill--info" },
  };
  const payload = map[normalized] || { label: normalized, className: "pill" };
  return <span className={payload.className}>{payload.label}</span>;
}

function DetailTable({
  details,
  onRetry,
  onViewLog,
  retryingDetails,
}: {
  details: PipelineRunDetail[];
  onRetry: (id: string, crawlerName: string) => void;
  onViewLog: (detail: PipelineRunDetail) => void;
  retryingDetails?: Set<string>;
}) {
  if (!details.length) return <div className="empty-state">暂无明细</div>;
  return (
    <table className="list-table sub">
      <thead>
        <tr>
          <th>爬虫</th>
          <th>来源</th>
          <th>状态</th>
          <th>条数</th>
          <th>耗时(ms)</th>
          <th>重试</th>
          <th>错误类型</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        {details.map((d) => {
          const isRetrying = retryingDetails?.has(d.id || "");
          return (
            <tr key={`${d.id || d.crawler_name}-${d.attempt_number ?? ""}`}>
              <td>{d.crawler_name}</td>
              <td>{d.source_id || "-"}</td>
              <td>
                {isRetrying ? (
                  <span className="pill pill--info">重试中...</span>
                ) : (
                  <StatusBadge status={d.status} />
                )}
              </td>
              <td>{d.result_count}</td>
              <td>{d.duration_ms ?? "-"}</td>
              <td>
                {d.attempt_number ?? "-"} / {d.max_attempts ?? "-"}
              </td>
              <td>{d.error_type || "-"}</td>
              <td className="table-actions">
                <button
                  className="link-btn"
                  disabled={!d.id || !d.log_path}
                  onClick={() => onViewLog(d)}
                  title={!d.log_path ? "暂无日志" : "查看日志"}
                >
                  查看日志
                </button>
                {d.status === "failed" && d.id && !isRetrying ? (
                  <button onClick={() => onRetry(d.id!, d.crawler_name)} className="link-btn danger">
                    异步重试
                  </button>
                ) : isRetrying ? (
                  <span className="muted small">重试中</span>
                ) : (
                  <span className="muted small">-</span>
                )}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function LogModal({ state, onClose }: { state: LogModalState; onClose: () => void }) {
  if (!state.visible) return null;
  return (
    <div className="modal-backdrop">
      <div className="modal">
        <div className="modal__header">
          <div>
            <h3>{state.title}</h3>
            {state.path ? (
              <p className="muted small">
                日志路径：<code>{state.path}</code>
              </p>
            ) : null}
            {state.truncated ? <p className="muted small">已截断，仅展示末尾内容</p> : null}
          </div>
          <button className="ghost" onClick={onClose}>
            关闭
          </button>
        </div>
        <div className="log-box">
          {state.loading ? (
            <div>正在加载日志...</div>
          ) : state.error ? (
            <div className="error">{state.error}</div>
          ) : state.lines.length ? (
            <pre>{state.lines.join("\n")}</pre>
          ) : (
            <div className="empty-state">暂无日志内容</div>
          )}
        </div>
      </div>
    </div>
  );
}

function ProxyStatusBadge({ needed, lastUsed }: { needed?: boolean | null; lastUsed?: boolean | null }) {
  if (needed === true) {
    return <span className="pill pill--warn">需要代理</span>;
  }
  if (needed === false) {
    return <span className="pill pill--ok">无需代理</span>;
  }
  if (lastUsed === true) {
    return <span className="pill pill--info">已用代理</span>;
  }
  return <span className="pill">未知</span>;
}

function ProxyModeSelect({
  value,
  onChange,
  disabled,
}: {
  value: ProxyMode;
  onChange: (mode: ProxyMode) => void;
  disabled?: boolean;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value as ProxyMode)}
      disabled={disabled}
      className="proxy-mode-select"
    >
      <option value="auto">自动</option>
      <option value="always">始终使用</option>
      <option value="never">从不使用</option>
    </select>
  );
}

export default function CrawlerManagementPage() {
  const {
    metas,
    jobs,
    loading,
    error,
    refresh,
    fetchRuns,
    runPipeline,
    runPipelineQuick,
    createJob,
    deleteJob,
    loadPipelineRuns,
    retryDetail,
    celeryStatus,
    celeryError,
    refreshCelery,
    loadPipelineDetailLog,
    loadJobRunLog,
  } = useScheduler();

  const [form, setForm] = useState<JobFormState>(defaultForm);
  const [selectedJob, setSelectedJob] = useState<string | null>(null);
  const [runs, setRuns] = useState<CrawlerJobRun[]>([]);
  const [pipelines, setPipelines] = useState<PipelineRunItem[]>([]);
  const [expandedRuns, setExpandedRuns] = useState<Set<string>>(new Set());
  const [submitting, setSubmitting] = useState(false);
  const [pipeLoading, setPipeLoading] = useState(false);
  const [quickLoading, setQuickLoading] = useState(false);
  const [lastPipelineDetails, setLastPipelineDetails] = useState<PipelineRunDetail[]>([]);
  const [pipelineError, setPipelineError] = useState<string | null>(null);
  const [logModal, setLogModal] = useState<LogModalState>({
    visible: false,
    title: "",
    path: "",
    lines: [],
    truncated: false,
    loading: false,
    error: null,
  });

  // 代理配置状态
  const [proxyConfigs, setProxyConfigs] = useState<SourceProxyItem[]>([]);
  const [proxyLoading, setProxyLoading] = useState(false);
  const [proxyUpdating, setProxyUpdating] = useState<string | null>(null);

  // 重试状态追踪
  const [retryingDetails, setRetryingDetails] = useState<Set<string>>(new Set());

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    loadPipelineRuns({ limit: 20 }).then((data) => setPipelines(data.items));
  }, [loadPipelineRuns]);

  // 加载代理配置
  const loadProxyConfigs = useCallback(async () => {
    setProxyLoading(true);
    try {
      const items = await fetchSourceProxyList();
      setProxyConfigs(items);
    } catch (err) {
      console.error("加载代理配置失败:", err);
    } finally {
      setProxyLoading(false);
    }
  }, []);

  useEffect(() => {
    loadProxyConfigs();
  }, [loadProxyConfigs]);

  // 更新代理模式
  const handleProxyModeChange = async (sourceId: string, mode: ProxyMode) => {
    setProxyUpdating(sourceId);
    try {
      const updated = await updateSourceProxyConfig(sourceId, { proxy_mode: mode });
      setProxyConfigs((prev) =>
        prev.map((item) => (item.source_id === sourceId ? updated : item))
      );
    } catch (err) {
      // eslint-disable-next-line no-alert
      alert(err instanceof Error ? err.message : "更新代理配置失败");
    } finally {
      setProxyUpdating(null);
    }
  };

  useEffect(() => {
    if (!selectedJob) {
      setRuns([]);
      return;
    }
    fetchRuns(selectedJob)
      .then(setRuns)
      .catch(() => setRuns([]));
  }, [selectedJob, fetchRuns]);

  const crawlerOptions = useMemo(
    () => metas.map((m) => ({ value: m.name, label: `${m.label || m.name}${m.category ? `（${m.category}）` : ""}` })),
    [metas]
  );

  const handleField = (key: keyof JobFormState, value: string | number | boolean | undefined) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const handleCreateJob = async () => {
    setSubmitting(true);
    try {
      const payload = {
        meta: {
          max_pages: form.max_pages,
          max_items: form.max_items,
          timeout: form.timeout,
        },
      };
      const retry_config: Record<string, unknown> = {
        max_attempts: form.max_attempts,
        attempt_backoff: 1.5,
        request: { max_retries: form.request_max_retries, timeout: form.timeout },
      };
      await createJob({
        name: form.name,
        crawler_name: form.crawler_name,
        job_type: form.job_type,
        schedule_cron: form.job_type === "scheduled" ? form.schedule_cron : null,
        interval_minutes: form.job_type === "scheduled" ? form.interval_minutes : null,
        payload,
        retry_config,
        enabled: form.enabled,
      } as unknown as Record<string, unknown>);
      await refresh();
      setForm(defaultForm);
    } catch (err) {
      // eslint-disable-next-line no-alert
      alert(err instanceof Error ? err.message : "创建任务失败");
    } finally {
      setSubmitting(false);
    }
  };

  const handleRunPipeline = async (quick?: boolean) => {
    setPipelineError(null);
    quick ? setQuickLoading(true) : setPipeLoading(true);
    try {
      const res = quick ? await runPipelineQuick() : await runPipeline();
      setLastPipelineDetails(res.details || []);
      await loadPipelineRuns({ limit: 20 }).then((data) => setPipelines(data.items));
    } catch (err) {
      setPipelineError(err instanceof Error ? err.message : "执行失败");
    } finally {
      quick ? setQuickLoading(false) : setPipeLoading(false);
    }
  };

  const toggleExpand = (id: string) => {
    setExpandedRuns((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleRetryDetail = async (detailId: string, crawlerName: string) => {
    // 添加到重试中状态
    setRetryingDetails((prev) => new Set(prev).add(detailId));

    await retryDetail(detailId);

    // 开始轮询检查重试结果
    const pollRetryStatus = async () => {
      const maxPolls = 60; // 最多轮询60次（约5分钟）
      for (let i = 0; i < maxPolls; i++) {
        await new Promise((r) => setTimeout(r, 5000)); // 5秒一次
        try {
          const runs = await loadPipelineRuns({ run_type: "manual_retry", limit: 5 });
          // 查找最新的与该爬虫相关的完成的重试
          const latestRetry = runs.items.find(
            (r) => r.finished_at && r.details?.some((d) => d.crawler_name === crawlerName)
          );
          if (latestRetry) {
            // 找到完成的重试，移除轮询状态
            setRetryingDetails((prev) => {
              const next = new Set(prev);
              next.delete(detailId);
              return next;
            });
            // 刷新列表
            await loadPipelineRuns({ limit: 20 }).then((data) => setPipelines(data.items));
            return;
          }
        } catch {
          // 轮询出错，继续
        }
      }
      // 超时，移除状态
      setRetryingDetails((prev) => {
        const next = new Set(prev);
        next.delete(detailId);
        return next;
      });
      await loadPipelineRuns({ limit: 20 }).then((data) => setPipelines(data.items));
    };

    // 后台轮询，不阻塞UI
    pollRetryStatus();
  };

  const showLog = async (
    title: string,
    path: string | null | undefined,
    loader: () => Promise<{ lines: LogLine[]; truncated: boolean }>
  ) => {
    setLogModal({
      visible: true,
      title,
      path,
      lines: [],
      truncated: false,
      loading: true,
      error: null,
    });
    try {
      const data = await loader();
      const formatted = data.lines.map((line) => `${String(line.idx).padStart(5, " ")} | ${line.content}`);
      setLogModal((prev) => ({
        ...prev,
        lines: formatted,
        truncated: data.truncated,
        loading: false,
      }));
    } catch (err) {
      setLogModal((prev) => ({
        ...prev,
        loading: false,
        error: err instanceof Error ? err.message : "加载日志失败",
      }));
    }
  };

  const handleViewPipelineLog = (detail: PipelineRunDetail) => {
    if (!detail.id) {
      setLogModal({
        visible: true,
        title: `${detail.crawler_name} 日志`,
        path: detail.log_path,
        lines: [],
        truncated: false,
        loading: false,
        error: "该记录尚未落库，无法查看日志",
      });
      return;
    }
    showLog(`${detail.crawler_name} 日志`, detail.log_path, () => loadPipelineDetailLog(detail.id!));
  };

  const handleViewJobLog = (run: CrawlerJobRun) => {
    if (!run.log_path) {
      setLogModal({
        visible: true,
        title: `${run.executed_crawler} 日志`,
        path: null,
        lines: [],
        truncated: false,
        loading: false,
        error: "暂无日志文件",
      });
      return;
    }
    showLog(`${run.executed_crawler} 日志`, run.log_path, () => loadJobRunLog(run.id));
  };

  const closeLogModal = () => {
    setLogModal((prev) => ({ ...prev, visible: false }));
  };

  const selectedJobName = useMemo(
    () => jobs.find((j) => j.id === selectedJob)?.name || "未选择",
    [jobs, selectedJob]
  );

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>爬虫管理</h1>
          <p className="muted">统一查看运行状态、任务配置、日志与重试</p>
        </div>
        <div className="toolbar">
          <button className="ghost" onClick={refresh}>
            刷新数据
          </button>
          <button className="ghost" onClick={refreshCelery}>
            检测 Celery
          </button>
        </div>
      </div>

      {error && <div className="error">{error}</div>}

      <section className="panel">
        <div className="panel__header">
          <h3>运行状态</h3>
        </div>
        <div className="card-grid">
          <div className="stat-card">
            <div className="stat-card__label">Celery Worker</div>
            <div className="stat-card__value">
              <StatusBadge status={celeryStatus?.running ? "success" : "failed"} />
            </div>
            <p className="muted small">{celeryError || celeryStatus?.detail || "正在检测..."}</p>
          </div>
          <div className="stat-card">
            <div className="stat-card__label">已配置任务</div>
            <div className="stat-card__value">{jobs.length}</div>
            <p className="muted small">来源自动匹配，无需手填来源 ID</p>
          </div>
          <div className="stat-card">
            <div className="stat-card__label">可用爬虫</div>
            <div className="stat-card__value">{metas.length}</div>
            <p className="muted small">下拉选择，默认兜底重试策略已带上</p>
          </div>
        </div>
      </section>

      <section className="panel panel--accent">
        <div className="panel__header">
          <div>
            <h3>一键执行采集 + 格式化 + AI</h3>
            <p className="muted small">支持全量与快速检测（每个爬虫 1 条），执行结果落库可追踪。</p>
          </div>
          <div className="panel__actions">
            <button onClick={() => handleRunPipeline(false)} className="primary" disabled={pipeLoading}>
              {pipeLoading ? "执行中..." : "执行全量流水线"}
            </button>
            <button onClick={() => handleRunPipeline(true)} className="ghost" disabled={quickLoading}>
              {quickLoading ? "执行中..." : "快速检测"}
            </button>
          </div>
        </div>
        {pipelineError && <div className="error">{pipelineError}</div>}
        <div>
          <h4 className="section-title">最近一次运行明细</h4>
          <DetailTable details={lastPipelineDetails} onRetry={handleRetryDetail} onViewLog={handleViewPipelineLog} retryingDetails={retryingDetails} />
        </div>
      </section>

      <section className="panel">
        <div className="panel__header">
          <div>
            <h3>新建任务</h3>
            <p className="muted small">来源自动创建/匹配，无需手填来源 ID。</p>
          </div>
        </div>
        <div className="form-grid">
          <label>
            任务名称
            <input value={form.name} onChange={(e) => handleField("name", e.target.value)} placeholder="如：每小时-国家药监局" />
          </label>
          <label>
            爬虫
            <select value={form.crawler_name} onChange={(e) => handleField("crawler_name", e.target.value)}>
              <option value="">请选择爬虫</option>
              {crawlerOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            任务类型
            <select value={form.job_type} onChange={(e) => handleField("job_type", e.target.value as JobType)}>
              <option value="scheduled">定时</option>
              <option value="one_off">临时</option>
            </select>
          </label>
          {form.job_type === "scheduled" && (
            <>
              <label>
                间隔分钟
                <input
                  type="number"
                  value={form.interval_minutes}
                  onChange={(e) => handleField("interval_minutes", Number(e.target.value))}
                  min={1}
                />
              </label>
              <label>
                Cron（可选）
                <input
                  value={form.schedule_cron || ""}
                  onChange={(e) => handleField("schedule_cron", e.target.value)}
                  placeholder="*/30 * * * *"
                />
              </label>
            </>
          )}
          <label>
            最大采集列表页
            <input
              type="number"
              value={form.max_pages}
              onChange={(e) => handleField("max_pages", Number(e.target.value))}
              min={1}
            />
          </label>
          <label>
            每页最大条数
            <input
              type="number"
              value={form.max_items}
              onChange={(e) => handleField("max_items", Number(e.target.value))}
              min={1}
            />
          </label>
          <label>
            请求超时(秒)
            <input
              type="number"
              value={form.timeout}
              onChange={(e) => handleField("timeout", Number(e.target.value))}
              min={1}
            />
          </label>
          <label>
            爬虫级重试次数
            <input
              type="number"
              value={form.max_attempts}
              onChange={(e) => handleField("max_attempts", Number(e.target.value))}
              min={1}
            />
          </label>
          <label>
            单次请求重试
            <input
              type="number"
              value={form.request_max_retries}
              onChange={(e) => handleField("request_max_retries", Number(e.target.value))}
              min={0}
            />
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={form.enabled}
              onChange={(e) => handleField("enabled", e.target.checked)}
            />
            启用
          </label>
        </div>
        <div className="panel__actions">
          <button onClick={handleCreateJob} disabled={submitting || !form.name || !form.crawler_name} className="primary">
            {submitting ? "创建中..." : "创建任务"}
          </button>
        </div>
      </section>

      <section className="panel">
        <div className="panel__header">
          <div>
            <h3>任务列表</h3>
            <p className="muted small">点击查看运行记录与日志，来源自动绑定。</p>
          </div>
          <button className="ghost" onClick={refresh} disabled={loading}>
            刷新
          </button>
        </div>
        {loading ? (
          <div>加载中...</div>
        ) : (
          <table className="list-table">
            <thead>
              <tr>
                <th>名称</th>
                <th>爬虫</th>
                <th>来源</th>
                <th>类型</th>
                <th>下次时间</th>
                <th>最近状态</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((job: CrawlerJobItem) => (
                <tr key={job.id}>
                  <td>{job.name}</td>
                  <td>{job.crawler_name}</td>
                  <td>{job.source_id}</td>
                  <td>{job.job_type}</td>
                  <td>{job.next_run_at ? new Date(job.next_run_at).toLocaleString() : "-"}</td>
                  <td>
                    <StatusBadge status={job.last_status || undefined} />
                  </td>
                  <td className="table-actions">
                    <button className="link-btn" onClick={() => setSelectedJob(job.id)}>
                      查看运行
                    </button>
                    <button className="link-btn danger" onClick={() => deleteJob(job.id)}>
                      删除
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {selectedJob && (
          <div style={{ marginTop: 12 }}>
            <h4 className="section-title">运行历史 · {selectedJobName}</h4>
            <table className="list-table sub">
              <thead>
                <tr>
                  <th>开始时间</th>
                  <th>状态</th>
                  <th>结果数</th>
                  <th>耗时(ms)</th>
                  <th>错误类型</th>
                  <th>日志</th>
                  <th>错误信息</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((r: CrawlerJobRun) => (
                  <tr key={r.id}>
                    <td>{new Date(r.started_at).toLocaleString()}</td>
                    <td>
                      <StatusBadge status={r.status} />
                    </td>
                    <td>{r.result_count}</td>
                    <td>{r.duration_ms ?? "-"}</td>
                    <td>{r.error_type || "-"}</td>
                    <td>
                      <button className="link-btn" disabled={!r.log_path} onClick={() => handleViewJobLog(r)}>
                        {r.log_path ? "查看" : "暂无"}
                      </button>
                    </td>
                    <td>{r.error_message || "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="panel">
        <div className="panel__header">
          <div>
            <h3>流水线运行记录</h3>
            <p className="muted small">包括快速检测与全量执行，支持展开明细与异步重试。</p>
          </div>
          <button className="ghost" onClick={() => loadPipelineRuns({ limit: 20 }).then((d) => setPipelines(d.items))}>
            刷新
          </button>
        </div>
        <table className="list-table">
          <thead>
            <tr>
              <th>开始时间</th>
              <th>类型</th>
              <th>状态</th>
              <th>爬虫数</th>
              <th>采集数</th>
              <th>错误</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {pipelines.map((p) => (
              <tr key={p.id}>
                <td>{new Date(p.started_at).toLocaleString()}</td>
                <td>{p.run_type}</td>
                <td>
                  <StatusBadge status={p.status} />
                </td>
                <td>
                  {p.successful_crawlers}/{p.total_crawlers}
                </td>
                <td>{p.total_articles}</td>
                <td>{p.error_message || "-"}</td>
                <td>
                  <button className="link-btn" onClick={() => toggleExpand(p.id)}>
                    {expandedRuns.has(p.id) ? "收起" : "查看明细"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {pipelines.map(
          (p) =>
            expandedRuns.has(p.id) && (
              <div key={`${p.id}-details`} style={{ marginTop: 8 }}>
                <DetailTable details={p.details} onRetry={handleRetryDetail} onViewLog={handleViewPipelineLog} retryingDetails={retryingDetails} />
              </div>
            )
        )}
      </section>

      <section className="panel">
        <div className="panel__header">
          <div>
            <h3>代理配置</h3>
            <p className="muted small">
              管理爬虫的代理模式。auto=超时自动切换，always=始终使用代理，never=从不使用代理。
            </p>
          </div>
          <button className="ghost" onClick={loadProxyConfigs} disabled={proxyLoading}>
            {proxyLoading ? "加载中..." : "刷新"}
          </button>
        </div>
        {proxyLoading ? (
          <div>加载中...</div>
        ) : proxyConfigs.length === 0 ? (
          <div className="empty-state">暂无来源配置</div>
        ) : (
          <table className="list-table">
            <thead>
              <tr>
                <th>来源名称</th>
                <th>爬虫</th>
                <th>代理模式</th>
                <th>代理状态</th>
                <th>自定义代理</th>
              </tr>
            </thead>
            <tbody>
              {proxyConfigs.map((item) => (
                <tr key={item.source_id}>
                  <td>{item.source_name}</td>
                  <td>{item.crawler_name || "-"}</td>
                  <td>
                    <ProxyModeSelect
                      value={item.proxy_mode}
                      onChange={(mode) => handleProxyModeChange(item.source_id, mode)}
                      disabled={proxyUpdating === item.source_id}
                    />
                  </td>
                  <td>
                    <ProxyStatusBadge needed={item.proxy_needed} lastUsed={item.proxy_last_used} />
                  </td>
                  <td>{item.proxy_url || <span className="muted">默认</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <LogModal state={logModal} onClose={closeLogModal} />
    </div>
  );
}
