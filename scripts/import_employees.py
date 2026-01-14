#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""员工数据导入脚本

从 Excel 文件导入员工数据到数据库。

用法：
    python scripts/import_employees.py "分表-扬大基因.xlsx" --company-no ydjyhb
    python scripts/import_employees.py "分表-联博药业.xlsx" --company-no lbyyhb --sheet "联博药业"
    python scripts/import_employees.py --list-sheets "分表-扬大基因.xlsx"
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

# Add project root to path
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pandas as pd

from common.persistence import session_scope
from common.persistence.models import EmployeeORM

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


# Excel 列名到数据库字段的映射
# 不同子公司的 Excel 可能有细微差异，这里提供常见的列名映射
COLUMN_MAPPING = {
    # 公司名称
    "所属公司": "company_name",
    "公司": "company_name",
    "公司名称": "company_name",

    # 合同制
    "是/否劳动合同工": "is_contract",
    "劳动合同工": "is_contract",
    "合同制": "is_contract",

    # 部门
    "部门": "department",
    "所属部门": "department",

    # 姓名
    "姓名": "name",
    "员工姓名": "name",

    # 性别
    "性别": "gender",

    # 身份证号（敏感）
    "出生日期": "id_number",  # 某些 Excel 中这列实际是身份证号
    "身份证号": "id_number",
    "身份证": "id_number",
    "身份证号码": "id_number",

    # 电话（敏感）
    "电话号码": "phone",
    "电话": "phone",
    "手机号": "phone",
    "联系电话": "phone",

    # 职务
    "职务": "position",
    "岗位": "position",

    # 员工级别
    "一般员工/中层/管理层": "employee_level",
    "员工级别": "employee_level",
    "级别": "employee_level",

    # 学历
    "最高学历": "highest_education",
    "学历": "highest_education",

    # 毕业院校
    "毕业院校": "graduate_school",
    "毕业学校": "graduate_school",

    # 专业
    "专业": "major",
    "所学专业": "major",

    # 政治面貌
    "政治面貌": "political_status",

    # 职称
    "职称": "professional_title",

    # 技能等级
    "技能等级": "skill_level",

    # 入职时间
    "入职时间": "hire_date",
    "入职日期": "hire_date",
}


def generate_employee_id(company_no: str, name: str, id_number: Optional[str] = None) -> str:
    """生成员工唯一 ID。

    使用公司编号 + 姓名 + 身份证号（如有）生成 hash。
    """
    key = f"{company_no}:{name}:{id_number or ''}"
    return f"emp-{hashlib.sha256(key.encode()).hexdigest()[:12]}"


def parse_date(value: Any) -> Optional[datetime]:
    """解析日期字段。"""
    if pd.isna(value) or value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%Y年%m月%d日", "%Y.%m.%d"]:
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
    return None


def clean_string(value: Any) -> Optional[str]:
    """清理字符串字段。"""
    if pd.isna(value) or value is None:
        return None
    s = str(value).strip()
    return s if s else None


def parse_is_contract(value: Any) -> Optional[bool]:
    """解析合同制字段（是/否劳动合同工）。

    Excel 中的值可能是：
    - "是", "劳动合同工", "是劳动合同工" -> True
    - "否", "非劳动合同工", "非合同制" -> False
    """
    if pd.isna(value) or value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    # 匹配"是"或包含"劳动合同工"的值为 True
    if s in ("是", "劳动合同工", "是劳动合同工") or "劳动合同" in s:
        return True
    # 匹配"否"或包含"非"的值为 False
    if s in ("否", "非劳动合同工", "非合同制") or s.startswith("非"):
        return False
    return None


def make_json_serializable(obj: Any) -> Any:
    """将对象转换为 JSON 可序列化格式。"""
    if pd.isna(obj) or obj is None:
        return None
    if isinstance(obj, datetime):
        return obj.isoformat()
    if hasattr(obj, 'isoformat'):  # date 对象
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: make_json_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [make_json_serializable(v) for v in obj]
    return obj


def parse_excel_row(row: Dict[str, Any], company_no: str) -> Dict[str, Any]:
    """解析 Excel 行数据为员工记录。"""
    record = {"company_no": company_no, "raw_data": make_json_serializable(dict(row))}

    for excel_col, db_field in COLUMN_MAPPING.items():
        if excel_col in row:
            value = row[excel_col]
            if db_field == "hire_date":
                record[db_field] = parse_date(value)
            elif db_field == "is_contract":
                record[db_field] = parse_is_contract(value)
            else:
                record[db_field] = clean_string(value)

    # 生成 ID
    record["id"] = generate_employee_id(
        company_no,
        record.get("name", ""),
        record.get("id_number"),
    )

    return record


def list_sheets(excel_path: str) -> List[str]:
    """列出 Excel 文件中的所有 sheet。"""
    xl = pd.ExcelFile(excel_path)
    return xl.sheet_names


def import_employees(
    excel_path: str,
    company_no: str,
    sheet_name: Optional[str] = None,
    dry_run: bool = False,
) -> Dict[str, int]:
    """导入员工数据。

    Args:
        excel_path: Excel 文件路径
        company_no: 公司编号（如 ydjyhb）
        sheet_name: Sheet 名称（可选，默认读取第一个）
        dry_run: 是否仅预览不写入数据库

    Returns:
        统计信息 {total, inserted, updated, skipped}
    """
    logger.info(f"读取 Excel 文件: {excel_path}")

    # 读取 Excel
    if sheet_name:
        df = pd.read_excel(excel_path, sheet_name=sheet_name)
    else:
        df = pd.read_excel(excel_path, sheet_name=0)

    logger.info(f"读取到 {len(df)} 行数据，列: {list(df.columns)}")

    # 解析数据
    records = []
    for idx, row in df.iterrows():
        try:
            record = parse_excel_row(row.to_dict(), company_no)
            if record.get("name"):  # 跳过没有姓名的行
                records.append(record)
            else:
                logger.warning(f"第 {idx + 2} 行缺少姓名，跳过")
        except Exception as e:
            logger.error(f"解析第 {idx + 2} 行出错: {e}")

    logger.info(f"解析有效记录: {len(records)} 条")

    if dry_run:
        logger.info("Dry run 模式，预览数据:")
        for rec in records[:5]:
            logger.info(f"  {rec.get('name')} - {rec.get('department')} - {rec.get('position')}")
        if len(records) > 5:
            logger.info(f"  ... 共 {len(records)} 条")
        return {"total": len(records), "inserted": 0, "updated": 0, "skipped": 0}

    # 写入数据库
    stats = {"total": len(records), "inserted": 0, "updated": 0, "skipped": 0}

    with session_scope() as session:
        for rec in records:
            existing = session.query(EmployeeORM).filter(EmployeeORM.id == rec["id"]).first()
            if existing:
                # 更新现有记录
                for key, value in rec.items():
                    if key != "id":
                        setattr(existing, key, value)
                stats["updated"] += 1
            else:
                # 插入新记录
                employee = EmployeeORM(**rec)
                session.add(employee)
                stats["inserted"] += 1

        logger.info(f"写入数据库: inserted={stats['inserted']}, updated={stats['updated']}")

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="导入员工数据到数据库")
    parser.add_argument("excel_path", help="Excel 文件路径")
    parser.add_argument("--company-no", help="公司编号（如 ydjyhb, lbyyhb）", required=False)
    parser.add_argument("--sheet", help="Sheet 名称（默认读取第一个）", default=None)
    parser.add_argument("--dry-run", action="store_true", help="仅预览不写入数据库")
    parser.add_argument("--list-sheets", action="store_true", help="列出 Excel 中的所有 sheet")

    args = parser.parse_args()

    if args.list_sheets:
        sheets = list_sheets(args.excel_path)
        print("可用的 Sheet 列表:")
        for i, sheet in enumerate(sheets):
            print(f"  {i + 1}. {sheet}")
        return

    if not args.company_no:
        parser.error("需要指定 --company-no 参数")

    stats = import_employees(
        excel_path=args.excel_path,
        company_no=args.company_no,
        sheet_name=args.sheet,
        dry_run=args.dry_run,
    )

    print(f"\n导入完成: total={stats['total']}, inserted={stats['inserted']}, updated={stats['updated']}")


if __name__ == "__main__":
    main()
