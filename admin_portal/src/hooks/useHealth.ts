import { useCallback, useEffect, useState } from "react";
import { fetchHealth } from "@/services/api";

type Status = "loading" | "up" | "down";

export function useHealth(autoRefreshMs = 20000) {
  const [status, setStatus] = useState<Status>("loading");
  const [lastChecked, setLastChecked] = useState<Date | undefined>(undefined);

  const probe = useCallback(async () => {
    try {
      const response = await fetchHealth();
      setStatus(response.data.status === "ok" ? "up" : "down");
      setLastChecked(new Date());
    } catch (error) {
      console.error("Health check failed", error);
      setStatus("down");
    }
  }, []);

  useEffect(() => {
    probe();
    const timer = setInterval(probe, autoRefreshMs);
    return () => clearInterval(timer);
  }, [probe, autoRefreshMs]);

  return {
    status,
    lastChecked,
    refresh: probe,
  };
}
