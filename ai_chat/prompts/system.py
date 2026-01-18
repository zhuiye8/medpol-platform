# -*- coding: utf-8 -*-
"""System prompt builder for chat."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from ai_chat.prompts.company_info import GROUP_INTRO, build_company_context


# 员工数据权限角色
EMPLOYEE_FULL_ACCESS_ROLES = {"admin"}  # 只有 admin 可访问完整数据
EMPLOYEE_BASIC_ACCESS_ROLES = {"admin", "viewer"}  # admin 和 viewer 可访问员工数据

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


def build_employee_knowledge(user_role: str) -> str:
    """根据用户角色生成员工查询知识。

    Args:
        user_role: 用户角色

    Returns:
        员工查询提示词（如果无权限则返回空字符串）
    """
    if user_role not in EMPLOYEE_BASIC_ACCESS_ROLES:
        return ""

    # 基础字段（所有有权限的角色可见）
    base_fields = (
        "id, company_no(公司编号), company_name(公司名称), name(姓名), gender(性别), "
        "department(部门), position(职务), employee_level(员工级别：一般员工/中层/管理层), "
        "highest_education(最高学历), graduate_school(毕业院校), major(专业), "
        "political_status(政治面貌), professional_title(职称), skill_level(技能等级), "
        "hire_date(入职时间)"
    )

    if user_role in EMPLOYEE_FULL_ACCESS_ROLES:
        # 管理员可见敏感字段
        fields_desc = f"{base_fields}, id_number(身份证号), phone(电话号码)"
        access_note = "可查看全部员工信息（含身份证号、电话）"
        table_instruction = "表名: employees（完整数据表，包含敏感字段）"
    else:
        # 普通查看者只能看基础字段
        fields_desc = base_fields
        access_note = "仅可查看基础信息（不含身份证号、电话等敏感信息）"
        table_instruction = "表名: employees_basic（基础视图，不含敏感字段）"

    return (
        f"【员工查询规范】\n"
        f"{table_instruction}\n"
        f"可用字段：{fields_desc}\n"
        f"权限说明：{access_note}\n"
        f"\n"
        f"【⭐ 重要】集团公司架构说明：\n"
        f"数据库中的所有公司都属于联环集团体系（目前约22家公司，共1315名员工）。\n"
        f"包括但不限于：\n"
        f"  - 联环系公司（公司名含\"联环\"）：江苏联环健康大药房、联环药业（安庆）、扬州联环医药营销等\n"
        f"  - 其他成员企业：四川龙一医药、江苏华天宝药业、扬州市普林斯医药科技等\n"
        f"\n"
        f"【集团查询策略】⭐ 关键\n"
        f"1. 用户问\"集团\"或\"联环集团\"时：\n"
        f"   - 理解：用户想了解集团整体情况（所有公司）\n"
        f"   - SQL：SELECT COUNT(*) FROM employees （不加WHERE，统计全部）\n"
        f"   - 结果：1315人（所有22家公司）\n"
        f"   - 回答示例：\"联环集团共有1315名员工，分布在22家成员企业中\"\n"
        f"\n"
        f"2. 用户问具体公司时：\n"
        f"   - 例如：\"四川龙一有多少员工？\"、\"华天宝的员工情况\"\n"
        f"   - SQL：WHERE company_name ILIKE '%四川龙一%' 或 '%华天宝%'\n"
        f"   - 使用ILIKE模糊匹配，因为用户通常不知道完整公司名\n"
        f"\n"
        f"3. 用户问\"联环\"的公司时（易混淆场景）：\n"
        f"   - 例如：\"联环有多少员工？\"、\"联环的药房\"\n"
        f"   - 需要判断：用户是问集团整体，还是仅问带\"联环\"字样的公司？\n"
        f"   - 优先理解为集团整体（1315人），除非用户明确限定\"名字带联环的公司\"\n"
        f"\n"
        f"【聚合查询规范（COUNT/SUM/AVG/MAX/MIN）】\n"
        f"  - 统计集团总人数：SELECT COUNT(*) as count FROM employees;\n"
        f"  - 按学历分组：SELECT highest_education, COUNT(*) as count FROM employees GROUP BY highest_education LIMIT 100;\n"
        f"  - 按公司分组：SELECT company_name, COUNT(*) as count FROM employees GROUP BY company_name ORDER BY count DESC LIMIT 10;\n"
        f"注意：聚合查询结果会以大数字卡片形式展示，LLM应根据统计数值直接回答。\n"
        f"\n"
        f"【统计分组（GROUP BY）】\n"
        f"  - 当用户询问\"按XXX统计\"、\"各公司...占比\"、\"分布情况\"时，使用 GROUP BY\n"
        f"  - 限制：最多返回100个分组\n"
        f"  - 示例：SELECT company_name, COUNT(*) as total FROM employees_basic GROUP BY company_name LIMIT 100;\n"
        f"\n"
        f"【图表生成】⭐ 重要\n"
        f"  - GROUP BY统计查询后，**主动调用 generate_employee_chart** 生成可视化图表\n"
        f"  - 图表类型选择：\n"
        f"    * 按公司/部门统计人数 → bar（柱状图）\n"
        f"    * 按学历/职称分布 → pie（饼图）\n"
        f"    * 多指标对比 → bar（分组柱状图）\n"
        f"  - 注意：\n"
        f"    1. 必须先调用 query_employees 获取 GROUP BY 数据\n"
        f"    2. 再调用 generate_employee_chart 生成图表\n"
        f"    3. 默认只生成一个图表，选择最适合的类型\n"
        f"\n"
        f"【明细查询规范】\n"
        f"  - 默认限制：最多返回20条记录（除非用户明确要求更多）\n"
        f"  - 示例：SELECT name, department, position FROM employees WHERE company_name ILIKE '%四川龙一%' LIMIT 20;\n"
        f"\n"
        f"SQL示例：\n"
        f"  - 查询集团总人数：SELECT COUNT(*) FROM employees;\n"
        f"  - 查询部门员工：SELECT name, department, position FROM employees WHERE department = '市场部';\n"
        f"  - 查询特定公司：SELECT * FROM employees WHERE company_name ILIKE '%四川龙一%';\n"
        f"\n"
        f"注意：\n"
        f"1. 员工数据回答时使用自然语言，如：四川龙一医药市场部共有5名员工\n"
        f"2. 禁止暴露SQL语句和技术细节\n"
        f"3. 敏感信息（身份证、电话）仅在用户明确请求且有权限时提供\n"
        f"4. 查询结果应明确说明统计范围，避免用户误解\n"
    )


def build_system_prompt(
    persona: str | None = None,
    mode: str = "rag",
    user_role: str = "viewer",
) -> str:
    """生成带有模式提示的系统提示。

    Args:
        persona: 人格设定
        mode: 模式 - "rag", "sql", "hybrid"
        user_role: 用户角色 - 决定员工数据访问权限
    """

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
        "8. 禁止生成 markdown 表格（如 |列1|列2|）。数据查询结果会自动以表格组件展示，你只需用自然语言总结数据要点，不要重复生成表格。\n"
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

    # 构建员工查询知识（根据角色权限）
    employee_knowledge = build_employee_knowledge(user_role)

    return (
        f"【当前时间】北京时间：{time_str}（{current_year}年）。\n"
        f"【身份】你是联环集团的专属AI助手，负责医药政策、财务分析与人事查询。回答需准确、简洁、中文输出，避免无依据的编造。\n"
        f'【重要】用户说"我们"、"我们集团"、"我们公司"、"集团"时，指的就是联环集团。\n'
        f'用户说"今年/当年/本年"指的是{current_year}年，"去年"指{current_year-1}年。\n'
        f"【联环集团简介】\n{GROUP_INTRO}\n"
        f"{company_context}\n"
        f"{employee_knowledge}\n"
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


__all__ = [
    "build_system_prompt",
    "build_employee_knowledge",
    "TYPE_NO_MAPPING",
    "COMPANY_MAPPING",
    "FIELD_DISPLAY_MAPPING",
    "EMPLOYEE_FULL_ACCESS_ROLES",
    "EMPLOYEE_BASIC_ACCESS_ROLES",
]
