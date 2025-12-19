# -*- coding: utf-8 -*-
"""System prompt builder for chat."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from ai_chat.prompts.company_info import GROUP_INTRO, build_company_context


# 指标类型完整映射
TYPE_NO_MAPPING = {
    "01": "营业收入",
    "02": "利润总额",
    "03": "实现税金",
    "04": "入库税金",
    "05": "所得税",
    "06": "净利润",
    "07": "实现税金(扬州地区)",
    "08": "入库税金(扬州地区)",
}

# 公司编号映射（company_no -> company_name，与 API 返回一致）
COMPANY_MAPPING = {
    "lhjt": "集团(合)",
    "gykg": "国药控股",
    "htb": "华天宝",
    "ltyyhb": "联通医药",
    "plshb": "普林斯(合)",
    "yhtzy": "颐和堂",
    "lhjthb": "股份(合)",
    "lbyyhb": "联博(合)",
    "jkcyhb": "产业(合)",
    "sshx": "圣氏化学",
    "ydjyhb": "基因(合)",
    "khyy": "康和药业",
    "scly": "四川龙一",
}


def build_system_prompt(persona: str | None = None, mode: str = "rag") -> str:
    """生成带有模式提示的系统提示。"""

    persona_key = persona or "general"
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    weekday_cn = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"][now.weekday()]
    time_str = f"{now.year}年{now.month}月{now.day}日{now:%H:%M}（{weekday_cn}）"

    # 动态生成当前年份的日期示例
    current_year = now.year
    current_month = now.month
    # 生成最近两个月的示例日期
    if current_month >= 2:
        example_dates = f"'{current_year}-{current_month-1:02d}-01','{current_year}-{current_month:02d}-01'"
    else:
        example_dates = f"'{current_year-1}-12-01','{current_year}-01-01'"

    # 指标类型映射字符串
    type_mapping_str = ", ".join([f"{k}={v}" for k, v in TYPE_NO_MAPPING.items()])

    # 公司映射字符串（所有公司）
    company_mapping_str = ", ".join([f"{v}={k}" for k, v in COMPANY_MAPPING.items()])

    # 财务查询的核心业务知识（SQL 和 Hybrid 共用）
    sql_knowledge = (
        f"【财务查询规范】\n"
        f"表名：finance_records\n"
        f"字段：keep_date（月份日期，格式如 {current_year}-09-01）、company_no（公司编号）、"
        f"company_name（公司名称）、type_no（指标类型编号）、type_name（指标类型名称）、"
        f"current_amount（本期金额，单位：万元）、last_year_amount（去年同期金额）、"
        f"add_rate（同比增长率，单位：%）、this_year_total_amount（本年累计）、year_add_rate（年同比%）。\n"
        f"【指标类型】{type_mapping_str}\n"
        f"【公司编号】{company_mapping_str}\n"
        f'【重要】当前是{current_year}年，用户问"今年/当年/本年"的数据时，必须查询{current_year}年的数据！\n'
        f"日期过滤示例：keep_date IN ({example_dates}) 或 keep_date >= '{current_year}-01-01'\n"
        f"SQL示例：SELECT keep_date, type_name, current_amount FROM finance_records "
        f"WHERE company_no='lhjt' AND type_no='01' AND keep_date >= '{current_year}-01-01' ORDER BY keep_date;\n"
        f"禁止使用 company/year/month/period/revenue 等不存在的字段。"
    )

    # 输出规范
    output_rules = (
        "【输出规范】\n"
        "1. 财务数据必须标注单位（万元），例如：营业收入 62,468.63 万元\n"
        '2. 指标类型使用中文名称（如"营业收入"而非"01"或"类型01"）\n'
        '3. 数据来源表述为"联环集团财务数据"而非"finance_records"或"数据表"\n'
        '4. 同比增长使用百分比格式，如"+23.72%"或"-5.3%"\n'
        '5. 日期显示为"2025年9月"而非"2025-09-01"\n'
        "6. 禁止暴露技术细节：\n"
        "   - 禁止输出SQL语句、表名、字段名\n"
        "   - 禁止显示JSON结构、文件路径、CSV文件名\n"
        '   - 禁止说"根据查询结果"、"Results saved to file"等内部提示\n'
        "   - 直接用自然语言陈述数据，如：联环集团2024年9月营业收入为xxx万元\n"
        "7. 禁止生成 markdown 图片语法（如 ![xxx](url)），图表会由系统自动展示\n"
    )

    # 图表生成引导
    chart_guidance = (
        "【图表生成】\n"
        "查询财务数据后，主动调用 generate_finance_chart 生成可视化图表：\n"
        "- 多公司数据对比：使用 bar（柱状图）\n"
        "- 月度趋势分析：使用 line（折线图）\n"
        "- 占比/分布分析：使用 pie（饼图）\n"
        "注意：\n"
        "1. 必须先调用 query_finance_sql 获取数据，再调用 generate_finance_chart\n"
        "2. 默认只生成一个图表，不要同时生成多种图表类型，除非用户明确要求\n"
        "3. 选择最适合数据特点的图表类型即可\n"
    )

    mode_hint = {
        "rag": "仅可调用 search_policy_articles 进行向量检索；回答时引用片段信息并用中文总结，不泄露字段/向量细节。",
        "sql": f"可调用 query_finance_sql 执行只读 SQL，以及 generate_finance_chart 生成图表。\n{sql_knowledge}\n{output_rules}\n{chart_guidance}",
        "hybrid": (
            f"可调用 query_finance_sql 获取财务数据，search_policy_articles 检索政策信息，generate_finance_chart 生成图表。\n"
            f"{sql_knowledge}\n{output_rules}\n{chart_guidance}"
        ),
    }.get(mode, "")

    # 构建公司信息上下文（所有模式通用）
    company_context = build_company_context()

    return (
        f"【当前时间】北京时间：{time_str}（{current_year}年）。\n"
        f"【身份】你是联环集团的专属AI助手，负责医药政策与财务分析。回答需准确、简洁、中文输出，避免无依据的编造。\n"
        f'【重要】用户说"我们"、"我们集团"、"我们公司"、"集团"时，指的就是联环集团。\n'
        f'用户说"今年/当年/本年"指的是{current_year}年，"去年"指{current_year-1}年。\n'
        f"【联环集团简介】\n{GROUP_INTRO}\n"
        f"{company_context}\n"
        f"{mode_hint}\n"
        f"Persona={persona_key}。"
    )


# 字段显示名映射（用于图表、前端展示）
FIELD_DISPLAY_MAPPING = {
    "current_amount": "当期金额",
    "last_year_amount": "去年同期",
    "this_year_total_amount": "本年累计",
    "add_rate": "同比增长率(%)",
    "year_add_rate": "年同比(%)",
    "keep_date": "月份",
    "company_name": "公司",
    "company_no": "公司编号",
    "type_name": "指标类型",
    "type_no": "指标编号",
}


__all__ = ["build_system_prompt", "TYPE_NO_MAPPING", "COMPANY_MAPPING", "FIELD_DISPLAY_MAPPING"]
