import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { fetchArticles } from "@/services/api";
import type { Article, ArticleCategory } from "@/types/api";

interface UseArticlesOptions {
  category?: ArticleCategory;
  pageSize?: number;
  autoRefreshMs?: number;
}

interface ArticleState {
  items: Article[];
  total: number;
  loading: boolean;
  refreshing: boolean;
  error: string | null;
  lastUpdated?: Date;
}

const defaultState: ArticleState = {
  items: [],
  total: 0,
  loading: true,
  refreshing: false,
  error: null,
};

export function useArticles(options: UseArticlesOptions = {}) {
  const { category, pageSize = 20, autoRefreshMs = 0 } = options;
  const [state, setState] = useState<ArticleState>(defaultState);
  const abortRef = useRef<AbortController | null>(null);

  const fetchData = useCallback(
    async (isBackground = false) => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      setState((prev) => ({
        ...prev,
        loading: isBackground ? prev.loading : true,
        refreshing: isBackground,
        error: null,
      }));
      try {
        const response = await fetchArticles({
          page: 1,
          pageSize,
          category,
        });
        setState({
          items: response.data.items,
          total: response.data.total,
          loading: false,
          refreshing: false,
          error: null,
          lastUpdated: new Date(),
        });
      } catch (error) {
        if (controller.signal.aborted) {
          return;
        }
        setState((prev) => ({
          ...prev,
          loading: false,
          refreshing: false,
          error: error instanceof Error ? error.message : "未知错误",
        }));
      }
    },
    [category, pageSize],
  );

  useEffect(() => {
    fetchData();
    if (!autoRefreshMs) {
      return;
    }
    const timer = setInterval(() => fetchData(true), autoRefreshMs);
    return () => clearInterval(timer);
  }, [fetchData, autoRefreshMs]);

  const stats = useMemo(() => {
    const byCategory = state.items.reduce<Record<ArticleCategory, number>>((acc, article) => {
      acc[article.category] = (acc[article.category] || 0) + 1;
      return acc;
    }, {} as Record<ArticleCategory, number>);
    return {
      categories: byCategory,
      latest: state.items.at(0),
    };
  }, [state.items]);

  return {
    ...state,
    stats,
    refresh: () => fetchData(false),
  };
}
