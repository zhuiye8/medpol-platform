import type { ArticleCategory } from "@/types/api";

export const CATEGORY_OPTIONS: { value: ArticleCategory; label: string }[] = [
  { value: "frontier", label: "前沿动态" },
  { value: "domestic_policy", label: "国内政策与动态" },
  { value: "project_apply", label: "项目申报" },
  { value: "fda_policy", label: "FDA 政策" },
  { value: "ema_policy", label: "EMA 政策" },
  { value: "pmda_policy", label: "PMDA 政策" },
];

export const CATEGORY_LABEL_MAP: Record<ArticleCategory, string> = CATEGORY_OPTIONS.reduce(
  (acc, item) => {
    acc[item.value] = item.label;
    return acc;
  },
  {} as Record<ArticleCategory, string>,
);

export const getCategoryLabel = (category: ArticleCategory | undefined): string => {
  if (!category) {
    return "全部分类";
  }
  return CATEGORY_LABEL_MAP[category] || category;
};
