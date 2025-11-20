import type { ArticleCategory } from "@/types/api";

export const CATEGORY_OPTIONS: { value: ArticleCategory; label: string }[] = [
  { value: "frontier", label: "前沿动态" },
  { value: "fda_policy", label: "FDA 政策" },
  { value: "ema_policy", label: "EMA 政策" },
  { value: "pmda_policy", label: "PMDA 政策" },
  { value: "bidding", label: "医保招标" },
  { value: "laws", label: "法律法规" },
  { value: "institution", label: "中心制度" },
  { value: "project_apply", label: "项目申报" },
  { value: "cde_trend", label: "CDE 动态" },
  { value: "industry_trend", label: "行业动态" },
];

export const STATUS_OPTIONS: Record<
  ArticleCategory,
  { value: string; label: string }[]
> = {
  project_apply: [
    { value: "pending", label: "未申报" },
    { value: "submitted", label: "已申报" },
  ],
  bidding: [
    { value: "policy_updates", label: "政策与动态" },
    { value: "national_tenders", label: "国家集采" },
    { value: "provincial_tenders", label: "省级集采" },
  ],
  cde_trend: [
    { value: "operations", label: "工作动态" },
    { value: "accepted_products", label: "受理品种信息" },
  ],
  industry_trend: [
    { value: "operations", label: "工作动态" },
    { value: "accepted_products", label: "受理品种信息" },
  ],
  frontier: [],
  fda_policy: [],
  ema_policy: [],
  pmda_policy: [],
  laws: [],
  institution: [],
};

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

export const getStatusOptions = (category?: ArticleCategory) => {
  if (!category) return [];
  return STATUS_OPTIONS[category] || [];
};
