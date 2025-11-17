.PHONY: help install playwright-install infra-up infra-down crawl-sample process-outbox run-crawlers seed-sources ai-jobs distribute

PYTHON ?= python

help:
	@echo "可用命令："
	@echo "  make install          安装 Python 依赖"
	@echo "  make playwright-install  安装 Playwright 浏览器"
	@echo "  make infra-up         启动 Redis/PostgreSQL 等基础服务"
	@echo "  make infra-down       停止基础服务"
	@echo "  make crawl-sample     抓取药渡云示例数据"
	@echo "  make process-outbox   处理 outbox 中的原始数据"
	@echo "  make run-crawlers     读取数据库配置运行所有爬虫"
	@echo "  make seed-sources     写入示例来源配置"
	@echo "  make ai-jobs          执行 AI 摘要任务"
	@echo "  make distribute       模拟分发 normalized 数据"

install:
	$(PYTHON) -m pip install -r requirements.txt

infra-up:
	docker compose -f infra/docker-compose.yml up -d

infra-down:
	docker compose -f infra/docker-compose.yml down

crawl-sample:
	$(PYTHON) scripts/fetch_sample.py

process-outbox:
	$(PYTHON) scripts/process_outbox.py

run-crawlers:
	$(PYTHON) scripts/run_crawlers.py

seed-sources:
	$(PYTHON) scripts/seed_sources.py

ai-jobs:
	$(PYTHON) scripts/run_ai_jobs.py

playwright-install:
	$(PYTHON) -m playwright install chromium

distribute:
	$(PYTHON) scripts/run_distribution.py
