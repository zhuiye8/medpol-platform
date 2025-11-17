import { useCallback, useEffect, useState } from "react";
import type { CrawlerJobItem, CrawlerMeta, CrawlerJobRun } from "@/types/scheduler";
import {
  fetchJobs,
  fetchCrawlerMeta,
  fetchJobRuns,
  triggerJob,
  createJob,
  deleteJob,
  runPipeline,
  fetchCeleryHealth,
  resetPipelineData,
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
  };
}
