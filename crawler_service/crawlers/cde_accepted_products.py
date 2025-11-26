"""CDE - 受理品种信息（cde_trend: accepted_products），使用 Playwright 渲染列表/详情。"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from common.domain import ArticleCategory
from ..base import BaseCrawler, CrawlResult
from ..registry import registry
from ..playwright_runner import fetch_html


class CDEAcceptedProductsCrawler(BaseCrawler):
    """采集 CDE 受理品种信息栏目。"""

    name = "cde_accepted_products"
    label = "CDE 受理品种信息"
    source_name = "药审中心(CDE)"
    category = ArticleCategory.CDE_TREND
    start_urls = ["https://www.cde.org.cn/main/xxgk/listpage/9f9c74c73e0f8f56a8bfbc646055026d"]

    def __init__(self, config: Dict | None = None) -> None:
        super().__init__(config)
        meta = self.config.meta
        self.list_url = meta.get("list_url") or self.start_urls[0]
        self.max_items = int(meta.get("max_items", 20))
        self._client.headers.setdefault(
            "User-Agent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0 Safari/537.36",
        )

    def crawl(self) -> List[CrawlResult]:
        entries = self._fetch_entries()
        results: List[CrawlResult] = []
        for entry in entries:
            try:
                results.append(self._build_result(entry))
            except Exception as exc:  # pylint: disable=broad-except
                self.logger.warning("解析受理品种失败 url=%s err=%s", entry["url"], exc)
        self.logger.info("受理品种采集 %s 条记录", len(results))
        return results

    def _fetch_entries(self) -> List[Dict[str, str]]:
        html = ""
        # 优先用 Playwright 渲染
        try:
            self.logger.info("使用 Playwright 渲染 CDE 受理品种列表: %s", self.list_url)
            # 正确的选择器：等待表格数据加载
            html = fetch_html(self.list_url, wait_selector="tbody#acceptVarietyInfoTbody tr", wait_time=8.0)
        except Exception as exc:
            self.logger.warning("Playwright 列表渲染失败: %s", exc)

        # 兜底：HTTP 请求
        if not html or len(html) < 500:
            fallback = os.getenv("CDE_ACCEPTED_HTML")
            if fallback and os.path.exists(fallback):
                self.logger.info("使用兜底文件: %s", fallback)
                html = Path(fallback).read_text(encoding="utf-8", errors="ignore")
            else:
                # 兜底再请求一次 HTTP
                resp = self.request("GET", self.list_url)
                html = resp.text

        entries: List[Dict[str, str]] = []
        soup = BeautifulSoup(html, "html.parser")

        # CDE的数据在表格中，不是新闻列表
        tbody = soup.select_one("tbody#acceptVarietyInfoTbody")
        if not tbody:
            self.logger.warning("未找到表格 tbody#acceptVarietyInfoTbody，尝试其他选择器")
            # 尝试其他可能的选择器
            tbody = soup.select_one("table tbody") or soup.select_one("tbody")

        if not tbody:
            self.logger.error("无法找到数据表格，HTML长度: %d", len(html))
            return entries

        rows = tbody.select("tr")
        self.logger.info("找到 %d 行数据", len(rows))

        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 8:
                self.logger.debug("跳过不完整的行（列数: %d）", len(cols))
                continue

            # 提取表格字段（索引从0开始）
            # 0:序号 1:受理号 2:药品名称 3:药品类型 4:申请类型 5:注册分类 6:企业名称 7:承办日期
            accept_id = cols[1].get_text(strip=True)  # 受理号
            drug_name = cols[2].get_text(strip=True)  # 药品名称
            drug_type = cols[3].get_text(strip=True)  # 药品类型
            apply_type = cols[4].get_text(strip=True)  # 申请类型
            register_class = cols[5].get_text(strip=True)  # 注册分类
            company = cols[6].get_text(strip=True)  # 企业名称
            accept_date = cols[7].get_text(strip=True)  # 承办日期

            if not drug_name or not accept_id:
                continue

            # 组合标题：药品名称（受理号）
            title = f"{drug_name}（{accept_id}）"

            # CDE的受理品种没有详情页，构造一个锚点URL
            url = f"{self.list_url}#{accept_id}"

            entries.append({
                "title": title,
                "url": url,
                "publish_date": accept_date,
                "accept_id": accept_id,
                "drug_name": drug_name,
                "drug_type": drug_type,
                "apply_type": apply_type,
                "register_class": register_class,
                "company": company,
            })

            if len(entries) >= self.max_items:
                break

        self.logger.info("成功提取 %d 条受理品种记录", len(entries))
        return entries

    def _build_result(self, entry: Dict[str, str]) -> CrawlResult:
        # CDE受理品种没有独立的详情页，直接使用列表数据构建内容
        accept_id = entry.get("accept_id", "")
        drug_name = entry.get("drug_name", "")
        drug_type = entry.get("drug_type", "")
        apply_type = entry.get("apply_type", "")
        register_class = entry.get("register_class", "")
        company = entry.get("company", "")
        accept_date = entry.get("publish_date", "")

        # 构建HTML内容表格
        content_html = f"""
<div class="cde-accepted-product">
    <h3>{drug_name}</h3>
    <table border="1" cellpadding="5" cellspacing="0" style="border-collapse: collapse; width: 100%;">
        <tr>
            <th style="background-color: #f0f0f0; width: 120px;">受理号</th>
            <td>{accept_id}</td>
        </tr>
        <tr>
            <th style="background-color: #f0f0f0;">药品类型</th>
            <td>{drug_type}</td>
        </tr>
        <tr>
            <th style="background-color: #f0f0f0;">申请类型</th>
            <td>{apply_type}</td>
        </tr>
        <tr>
            <th style="background-color: #f0f0f0;">注册分类</th>
            <td>{register_class}</td>
        </tr>
        <tr>
            <th style="background-color: #f0f0f0;">企业名称</th>
            <td>{company}</td>
        </tr>
        <tr>
            <th style="background-color: #f0f0f0;">承办日期</th>
            <td>{accept_date}</td>
        </tr>
    </table>
</div>
"""

        publish_time = self._parse_publish_time(accept_date)

        # 将所有字段作为metadata保存
        metadata = {
            "status": "accepted_products",
            "accept_id": accept_id,
            "drug_type": drug_type,
            "apply_type": apply_type,
            "register_class": register_class,
            "company": company,
        }

        return CrawlResult(
            title=entry["title"],
            source_url=entry["url"],
            content_html=content_html,
            publish_time=publish_time,
            metadata=metadata,
        )

    @staticmethod
    def _parse_publish_time(value: str | None) -> datetime:
        if not value:
            return datetime.utcnow()
        for fmt in ("%Y-%m-%d", "%Y.%m.%d", "%Y.%m %d"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        return datetime.utcnow()


registry.register(CDEAcceptedProductsCrawler)
