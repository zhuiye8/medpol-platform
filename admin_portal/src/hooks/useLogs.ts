import { useCallback, useEffect, useState } from "react";
import { fetchLogs } from "@/services/api";
import type { LogLine } from "@/types/api";

interface UseLogsOptions {
  limit?: number;
  autoRefreshMs?: number;
}

interface LogState {
  lines: LogLine[];
  total: number;
  truncated: boolean;
  loading: boolean;
  error: string | null;
  lastUpdated?: Date;
}

const defaultState: LogState = {
  lines: [],
  total: 0,
  truncated: false,
  loading: true,
  error: null,
};

export function useLogs(options: UseLogsOptions = {}) {
  const { limit = 200, autoRefreshMs = 15000 } = options;
  const [state, setState] = useState<LogState>(defaultState);

  const loadLogs = useCallback(
    async (silent = false) => {
      if (!silent) {
        setState((prev) => ({ ...prev, loading: true, error: null }));
      }
      try {
        const response = await fetchLogs(limit);
        setState({
          lines: response.data.lines,
          total: response.data.total,
          truncated: response.data.truncated,
          loading: false,
          error: null,
          lastUpdated: new Date(),
        });
      } catch (error) {
        setState((prev) => ({
          ...prev,
          loading: false,
          error: error instanceof Error ? error.message : "未知错误",
        }));
      }
    },
    [limit],
  );

  useEffect(() => {
    loadLogs();
    const timer = setInterval(() => loadLogs(true), autoRefreshMs);
    return () => clearInterval(timer);
  }, [loadLogs, autoRefreshMs]);

  return {
    ...state,
    refresh: () => loadLogs(false),
  };
}
