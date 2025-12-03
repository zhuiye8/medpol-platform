import { useCallback, useEffect, useState } from "react";
import type {
  CrawlerJobItem,
  CrawlerMeta,
  CrawlerJobRun,
  PipelineRunList,
  PipelineRunItem,
} from "@/types/scheduler";
import {
  fetchJobs,
  fetchCrawlerMeta,
  fetchJobRuns,
  triggerJob,
  createJob,
  deleteJob,
  runPipeline,
  runPipelineQuick,
  fetchCeleryHealth,
  resetPipelineData,
  fetchPipelineRuns,
  fetchPipelineRun,
  retryPipelineDetail,
  fetchPipelineDetailLog,
  fetchJobRunLog,
} from "@/services/scheduler";
import type { CeleryHealth, ResetResult } from "@/types/scheduler";

export function useScheduler() {
  const [jobs, setJobs] = useState<CrawlerJobItem[]>([]);
  const [metas, setMetas] = useState<CrawlerMeta[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [celeryStatus, setCeleryStatus] = useState<CeleryHealth | null>(null);
  const [celeryError, setCeleryError] = useState<string | null>(null);
  const [lastReset, setLastReset] = useState<ResetResult | null>(null);
  const [pipelineRuns, setPipelineRuns] = useState<PipelineRunList | null>(null);
  const [runDetail, setRunDetail] = useState<PipelineRunItem | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [jobList, metaList] = await Promise.all([fetchJobs(), fetchCrawlerMeta()]);
      setJobs(jobList);
      setMetas(metaList);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  const loadCelery = useCallback(async () => {
    setCeleryError(null);
    try {
      const status = await fetchCeleryHealth();
      setCeleryStatus(status);
    } catch (err) {
      setCeleryStatus(null);
      setCeleryError(err instanceof Error ? err.message : "检测失败");
    }
  }, []);

  useEffect(() => {
    load();
    loadCelery();
  }, [load, loadCelery]);

  const fetchRuns = useCallback(async (jobId: string) => fetchJobRuns(jobId), []);

  const resetData = useCallback(async () => {
    const result = await resetPipelineData();
    setLastReset(result);
    return result;
  }, []);

  const loadPipelineRuns = useCallback(
    async (params?: { limit?: number; offset?: number; run_type?: string; status?: string }) => {
      const data = await fetchPipelineRuns(params);
      setPipelineRuns(data);
      return data;
    },
    []
  );

  const loadPipelineRun = useCallback(async (runId: string) => {
    const data = await fetchPipelineRun(runId);
    setRunDetail(data);
    return data;
  }, []);

  const retryDetail = useCallback(async (detailId: string) => retryPipelineDetail(detailId), []);

  const loadPipelineDetailLog = useCallback(
    async (detailId: string, limit?: number) => fetchPipelineDetailLog(detailId, limit),
    []
  );

  const loadJobRunLog = useCallback(async (runId: string, limit?: number) => fetchJobRunLog(runId, limit), []);

  return {
    jobs,
    metas,
    loading,
    error,
    refresh: load,
    fetchRuns,
    triggerJob,
    createJob,
    deleteJob,
    runPipeline,
    celeryStatus,
    celeryError,
    refreshCelery: loadCelery,
    resetData,
    lastReset,
    runPipelineQuick,
    pipelineRuns,
    runDetail,
    loadPipelineRuns,
    loadPipelineRun,
    retryDetail,
    loadPipelineDetailLog,
    loadJobRunLog,
  };
}
