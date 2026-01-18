#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""员工数据导入脚本

从 Excel 文件导入员工数据到数据库。

用法：
    # 列出所有Sheet
    python scripts/import_employees.py --list-sheets "联环集团花名册.xlsx"

    # 单Sheet导入（独立文件）
    python scripts/import_employees.py "分表-扬大基因.xlsx" --company-name "扬州扬大联环药业基因工程有限公司"

    # 批量导入完整花名册
    python scripts/import_employees.py "联环集团花名册.xlsx" --batch
    python scripts/import_employees.py "联环集团花名册.xlsx" --batch --start-sheet 1 --end-sheet 5

    # 清空数据并重新导入
    python scripts/import_employees.py "联环集团花名册.xlsx" --clear-data --batch
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


def generate_employee_id(company_name: str, name: str, id_number: Optional[str] = None) -> str:
    """生成员工唯一 ID。

    使用公司名称 + 姓名 + 身份证号生成 hash。
    """
    key = f"{company_name}:{name}:{id_number or ''}"
    return f"emp-{hashlib.sha256(key.encode()).hexdigest()[:12]}"


def extract_sheet_title(excel_path: str, sheet_name: Optional[str] = None) -> str:
    """提取Sheet第一行标题（完整公司名称）。

    对于完整花名册：第一行是公司标题
    对于独立文件：可能没有标题行，返回空
    """
    try:
        df_title = pd.read_excel(excel_path, sheet_name=sheet_name or 0, nrows=1, header=None)
        if len(df_title) > 0:
            title = str(df_title.iloc[0, 0]).strip()
            # 判断是否为公司名称（包含"公司"或"有限"）
            if "公司" in title or "有限" in title:
                return title
    except Exception as e:
        logger.warning(f"提取标题失败: {e}")
    return ""


def auto_generate_aliases(company_name: str) -> List[str]:
    """自动生成公司别名。

    示例：
    - "扬州扬大联环药业基因工程有限公司" -> ["扬大基因", "基因", "扬大", ...]
    """
    import re

    if not company_name:
        return []

    aliases = [company_name]  # 包含完整名称

    # 1. 去除法人后缀
    suffixes = ["有限公司", "有限责任公司", "股份有限公司", "集团", "公司", "有限"]
    base_name = company_name
    for suffix in suffixes:
        if base_name.endswith(suffix):
            base_name = base_name[:-len(suffix)]
            if base_name not in aliases:
                aliases.append(base_name)

    # 2. 提取关键词（2-4个汉字的连续子串）
    keywords = re.findall(r'[\u4e00-\u9fff]{2,4}', company_name)
    for kw in keywords:
        if kw not in aliases and len(kw) >= 2:
            aliases.append(kw)

    return aliases[:10]  # 最多保留10个别名


def detect_excel_format(excel_path: str, sheet_name: Optional[str] = None) -> Dict[str, Any]:
    """检测Excel格式类型。

    返回: {
        "type": "full_roster" | "independent" | "unknown",
        "has_title_row": bool,
        "has_company_column": bool,
        "title": str,
        "skip_rows": int
    }
    """
    try:
        # 读取前3行
        df_header = pd.read_excel(excel_path, sheet_name=sheet_name or 0, nrows=3, header=None)

        # 检测第一行是否为公司标题
        first_cell = str(df_header.iloc[0, 0]).strip() if len(df_header) > 0 else ""
        has_title = "公司" in first_cell or "有限" in first_cell

        # 检测第二行是否为标准列名
        if has_title and len(df_header) > 1:
            second_row = df_header.iloc[1].tolist()
            standard_cols = ["姓名", "部门", "性别", "职务"]
            has_standard_cols = any(col in str(second_row) for col in standard_cols)

            if has_standard_cols:
                return {
                    "type": "full_roster",
                    "has_title_row": True,
                    "has_company_column": False,
                    "title": first_cell,
                    "skip_rows": 1  # 跳过第一行标题
                }

        # 检测是否有"所属公司"列
        df_check = pd.read_excel(excel_path, sheet_name=sheet_name or 0, nrows=1)
        has_company_col = "所属公司" in df_check.columns or "公司名称" in df_check.columns

        if has_company_col:
            return {
                "type": "independent",
                "has_title_row": False,
                "has_company_column": True,
                "title": "",
                "skip_rows": 0
            }

        return {
            "type": "unknown",
            "has_title_row": False,
            "has_company_column": False,
            "title": "",
            "skip_rows": 0
        }

    except Exception as e:
        logger.error(f"检测Excel格式失败: {e}")
        return {"type": "unknown", "has_title_row": False, "has_company_column": False, "title": "", "skip_rows": 0}


def validate_sheet(
    excel_path: str,
    sheet_name: Optional[str] = None,
    min_rows: int = 1
) -> tuple[bool, str, Dict[str, Any]]:
    """验证Sheet数据有效性。

    返回: (is_valid, error_message, validation_details)
    """
    try:
        # 检测格式
        format_info = detect_excel_format(excel_path, sheet_name)

        # 读取数据（跳过标题行）
        df = pd.read_excel(
            excel_path,
            sheet_name=sheet_name or 0,
            skiprows=format_info["skip_rows"]
        )

        result = {
            "sheet_name": sheet_name or "Sheet1",
            "format_type": format_info["type"],
            "title": format_info["title"],
            "total_rows": len(df),
            "columns": list(df.columns),
            "mapped_fields": [],
            "missing_required": [],
        }

        # 1. 检查行数
        if len(df) < min_rows:
            return False, f"数据行数不足（最少{min_rows}行，实际{len(df)}行）", result

        # 2. 检查必需字段：姓名
        has_name = any(col in df.columns for col in ["姓名", "员工姓名", "名字"])
        if not has_name:
            return False, "缺少必需字段：姓名", result

        # 3. 检测字段映射
        detected_cols = set(df.columns)
        for excel_col in detected_cols:
            if excel_col in COLUMN_MAPPING:
                result["mapped_fields"].append({
                    "excel_col": excel_col,
                    "db_field": COLUMN_MAPPING[excel_col]
                })

        if len(result["mapped_fields"]) < 3:  # 至少映射3个字段
            return False, f"有效字段太少（仅{len(result['mapped_fields'])}个），可能是格式不正确", result

        # 4. 检查空值率
        name_col = None
        for col in ["姓名", "员工姓名", "名字"]:
            if col in df.columns:
                name_col = col
                break

        if name_col:
            null_count = df[name_col].isnull().sum()
            null_rate = null_count / len(df)
            if null_rate > 0.5:
                return False, f"姓名字段空值率过高（{null_rate:.1%}），数据可能不完整", result

        return True, "", result

    except Exception as e:
        return False, f"读取Excel失败: {e}", {}


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


def parse_excel_row(
    row: Dict[str, Any],
    company_name: str,
    excel_company_name: Optional[str] = None,
    sheet_name: Optional[str] = None
) -> Dict[str, Any]:
    """解析 Excel 行数据为员工记录。

    Args:
        row: Excel行数据
        company_name: 主公司名称（标准全称）
        excel_company_name: Excel中的"所属公司"列值（如果有）
        sheet_name: Sheet名称（如果有）
    """
    # 生成别名列表
    aliases = auto_generate_aliases(company_name)
    if excel_company_name and excel_company_name not in aliases:
        aliases.append(excel_company_name)

    record = {
        "company_name": company_name,
        "raw_data": {
            **make_json_serializable(dict(row)),
            "company_aliases": aliases,
            "sheet_name": sheet_name,
            "excel_company_name": excel_company_name,
        }
    }

    # 字段映射
    for excel_col, db_field in COLUMN_MAPPING.items():
        if excel_col in row:
            value = row[excel_col]
            if db_field == "hire_date":
                record[db_field] = parse_date(value)
            elif db_field == "is_contract":
                record[db_field] = parse_is_contract(value)
            elif db_field != "company_name":  # 跳过company_name，使用传入的参数
                record[db_field] = clean_string(value)

    # 生成ID（使用新规则）
    record["id"] = generate_employee_id(
        company_name,
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
    company_name: str,
    sheet_name: Optional[str] = None,
    dry_run: bool = False,
) -> Dict[str, int]:
    """导入员工数据。

    Args:
        excel_path: Excel 文件路径
        company_name: 公司标准全称（如 "扬州扬大联环药业基因工程有限公司"）
        sheet_name: Sheet 名称（可选，默认读取第一个）
        dry_run: 是否仅预览不写入数据库

    Returns:
        统计信息 {total, inserted, updated, skipped}
    """
    logger.info(f"读取 Excel 文件: {excel_path}")

    # 检测格式
    format_info = detect_excel_format(excel_path, sheet_name)
    logger.info(f"检测到格式类型: {format_info['type']}")

    # 读取 Excel（跳过标题行）
    if sheet_name:
        df = pd.read_excel(excel_path, sheet_name=sheet_name, skiprows=format_info["skip_rows"])
    else:
        df = pd.read_excel(excel_path, sheet_name=0, skiprows=format_info["skip_rows"])

    logger.info(f"读取到 {len(df)} 行数据，列: {list(df.columns)}")

    # 解析数据
    records = []
    for idx, row in df.iterrows():
        try:
            excel_company_name = None
            if "所属公司" in row:
                excel_company_name = clean_string(row["所属公司"])

            record = parse_excel_row(
                row.to_dict(),
                company_name=company_name,
                excel_company_name=excel_company_name,
                sheet_name=sheet_name
            )
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


def batch_import_from_roster(
    excel_path: str,
    start_sheet_index: int = 1,
    end_sheet_index: Optional[int] = None,
    dry_run: bool = False,
    skip_validation: bool = False
) -> Dict[str, Any]:
    """从完整花名册批量导入所有Sheet。

    Args:
        excel_path: Excel文件路径
        start_sheet_index: 起始Sheet索引（默认1，跳过目录Sheet）
        end_sheet_index: 结束Sheet索引（默认None，处理所有）
        dry_run: 仅预览不导入
        skip_validation: 跳过验证（不推荐）

    Returns:
        {
            "total_sheets": int,
            "success_sheets": int,
            "failed_sheets": int,
            "skipped_sheets": int,
            "results": {sheet_name: {...}},
            "errors": {sheet_name: error_msg}
        }
    """
    logger.info(f"开始批量导入: {excel_path}")

    # 读取所有Sheet
    xl = pd.ExcelFile(excel_path)
    sheets = xl.sheet_names[start_sheet_index:end_sheet_index]

    summary = {
        "total_sheets": len(sheets),
        "success_sheets": 0,
        "failed_sheets": 0,
        "skipped_sheets": 0,
        "results": {},
        "errors": {}
    }

    for idx, sheet_name in enumerate(sheets, start=start_sheet_index):
        logger.info(f"\n处理 Sheet [{idx + 1}/{len(xl.sheet_names)}]: {sheet_name}")

        try:
            # 1. 验证Sheet
            if not skip_validation:
                is_valid, error_msg, details = validate_sheet(excel_path, sheet_name)
                if not is_valid:
                    logger.warning(f"  ✗ 跳过: {error_msg}")
                    logger.warning(f"    详情: {details}")
                    summary["skipped_sheets"] += 1
                    summary["errors"][sheet_name] = error_msg
                    continue

            # 2. 检测格式并提取公司名称
            format_info = detect_excel_format(excel_path, sheet_name)

            if format_info["type"] == "full_roster" and format_info["title"]:
                company_name = format_info["title"]
            elif format_info["type"] == "independent":
                # 从"所属公司"列提取（需要读取第一行）
                df_first = pd.read_excel(excel_path, sheet_name=sheet_name, nrows=1)
                if "所属公司" in df_first.columns:
                    company_name = str(df_first["所属公司"].iloc[0]).strip()
                else:
                    raise ValueError("独立文件格式但缺少'所属公司'列")
            else:
                raise ValueError(f"无法识别格式类型: {format_info['type']}")

            logger.info(f"  公司名称: {company_name}")
            logger.info(f"  格式类型: {format_info['type']}")

            # 3. 读取并解析数据
            df = pd.read_excel(
                excel_path,
                sheet_name=sheet_name,
                skiprows=format_info["skip_rows"]
            )

            records = []
            for row_idx, row in df.iterrows():
                try:
                    excel_company_name = None
                    if "所属公司" in row:
                        excel_company_name = clean_string(row["所属公司"])

                    record = parse_excel_row(
                        row.to_dict(),
                        company_name=company_name,
                        excel_company_name=excel_company_name,
                        sheet_name=sheet_name
                    )

                    if record.get("name"):
                        records.append(record)
                    else:
                        logger.debug(f"    第 {row_idx + 2} 行缺少姓名，跳过")

                except Exception as e:
                    logger.warning(f"    第 {row_idx + 2} 行解析失败: {e}")

            logger.info(f"  有效记录: {len(records)} 条")

            # 4. 写入数据库
            if not dry_run and len(records) > 0:
                stats = {"inserted": 0, "updated": 0}

                with session_scope() as session:
                    for rec in records:
                        existing = session.query(EmployeeORM).filter(EmployeeORM.id == rec["id"]).first()
                        if existing:
                            for key, value in rec.items():
                                if key != "id":
                                    setattr(existing, key, value)
                            stats["updated"] += 1
                        else:
                            session.add(EmployeeORM(**rec))
                            stats["inserted"] += 1

                logger.info(f"  ✓ 导入成功: inserted={stats['inserted']}, updated={stats['updated']}")
                summary["success_sheets"] += 1
                summary["results"][sheet_name] = {
                    "company_name": company_name,
                    "total": len(records),
                    **stats
                }
            elif dry_run:
                logger.info(f"  [Dry Run] 跳过写入")
                summary["success_sheets"] += 1
                summary["results"][sheet_name] = {
                    "company_name": company_name,
                    "total": len(records),
                    "dry_run": True
                }
            else:
                logger.warning(f"  ✗ 无有效记录")
                summary["skipped_sheets"] += 1

        except Exception as e:
            logger.error(f"  ✗ 处理失败: {e}")
            summary["failed_sheets"] += 1
            summary["errors"][sheet_name] = str(e)

    # 5. 打印总结
    logger.info(f"\n{'='*60}")
    logger.info(f"批量导入完成:")
    logger.info(f"  总Sheet数: {summary['total_sheets']}")
    logger.info(f"  成功: {summary['success_sheets']}")
    logger.info(f"  失败: {summary['failed_sheets']}")
    logger.info(f"  跳过: {summary['skipped_sheets']}")

    if summary["errors"]:
        logger.info(f"\n错误详情:")
        for sheet, error in summary["errors"].items():
            logger.info(f"  - {sheet}: {error}")

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="导入员工数据到数据库")
    parser.add_argument("excel_path", help="Excel 文件路径")

    # 原有参数
    parser.add_argument("--company-name", help="公司标准全称（如：扬州扬大联环药业基因工程有限公司）", required=False)
    parser.add_argument("--sheet", help="Sheet 名称（默认读取第一个）", default=None)
    parser.add_argument("--dry-run", action="store_true", help="仅预览不写入数据库")
    parser.add_argument("--list-sheets", action="store_true", help="列出 Excel 中的所有 sheet")

    # 新增参数
    parser.add_argument("--batch", action="store_true", help="批量导入所有Sheet（完整花名册模式）")
    parser.add_argument("--start-sheet", type=int, default=1, help="批量导入起始Sheet索引（默认1，跳过目录）")
    parser.add_argument("--end-sheet", type=int, default=None, help="批量导入结束Sheet索引（默认None，处理所有）")
    parser.add_argument("--skip-validation", action="store_true", help="跳过验证（不推荐）")
    parser.add_argument("--clear-data", action="store_true", help="导入前清空现有员工数据")

    args = parser.parse_args()

    # 列出Sheet
    if args.list_sheets:
        sheets = list_sheets(args.excel_path)
        print("可用的 Sheet 列表:")
        for i, sheet in enumerate(sheets):
            print(f"  {i}. {sheet}")
        return

    # 清空数据
    if args.clear_data:
        confirm = input("WARNING: 确认清空所有员工数据？(yes/no): ")
        if confirm.lower() == "yes":
            with session_scope() as session:
                count = session.query(EmployeeORM).count()
                session.query(EmployeeORM).delete()
                print(f"OK: 已清空 {count} 条员工数据")
        else:
            print("取消清空")
            return

    # 批量导入
    if args.batch:
        summary = batch_import_from_roster(
            excel_path=args.excel_path,
            start_sheet_index=args.start_sheet,
            end_sheet_index=args.end_sheet,
            dry_run=args.dry_run,
            skip_validation=args.skip_validation
        )
        print(f"\n{'='*60}")
        print(f"批量导入完成: 成功{summary['success_sheets']}，失败{summary['failed_sheets']}，跳过{summary['skipped_sheets']}")
        return

    # 单Sheet导入（原有逻辑）
    if not args.company_name:
        parser.error("单Sheet模式需要指定 --company-name 参数")

    # 验证Sheet
    is_valid, error_msg, details = validate_sheet(args.excel_path, args.sheet)
    if not is_valid:
        print(f"✗ Sheet验证失败: {error_msg}")
        print(f"  详情: {details}")
        return

    # 导入
    stats = import_employees(
        excel_path=args.excel_path,
        company_name=args.company_name,
        sheet_name=args.sheet,
        dry_run=args.dry_run,
    )

    print(f"\n导入完成: total={stats['total']}, inserted={stats['inserted']}, updated={stats['updated']}")


if __name__ == "__main__":
    main()
