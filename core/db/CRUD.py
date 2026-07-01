# core/db/crud.py
import sqlite3
from typing import List, Dict, Any, Optional, Set, Iterable
from pathlib import Path

# ========== 安全校验 ==========

# 允许操作的表名白名单（防止 SQL 注入）
ALLOWED_TABLES: Set[str] = {"user"}


def _validate_table(table: str) -> None:
    """
    校验表名是否在白名单内，防止 SQL 注入
    抛出 ValueError 而非静默失败，确保开发期能及时发现未注册的表
    """
    if table not in ALLOWED_TABLES:
        raise ValueError(
            f"表名 '{table}' 不在白名单 {ALLOWED_TABLES} 中，"
            f"请先将表名注册到 ALLOWED_TABLES"
        )


def _quote_columns(columns: Iterable[str]) -> str:
    """
    用双引号包裹列名，防止列名含特殊字符或被注入
    SQLite 支持用双引号作为标识符引用
    """
    return ", ".join(f'"{col}"' for col in columns)


# ========== 辅助函数 ==========


def get_connection(db_path: str | Path) -> sqlite3.Connection:
    """获取数据库连接，确保目录存在"""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(db_path)


def dict_factory(cursor, row):
    """将查询结果转换为字典格式"""
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


def _enable_dict_factory(conn: sqlite3.Connection):
    """为连接启用字典返回格式"""
    conn.row_factory = dict_factory


# ========== 基础增删改查 ==========


def create_record(db_path: str | Path, table: str, data: Dict[str, Any]) -> int | None:
    """
    插入单条记录
    返回：新插入记录的 ID
    """
    _validate_table(table)
    columns = _quote_columns(data.keys())
    placeholders = ", ".join(["?"] * len(data))
    sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"

    with get_connection(db_path) as conn:
        cursor = conn.execute(sql, list(data.values()))
        return cursor.lastrowid


def read_records(
    db_path: str | Path, table: str, conditions: Optional[Dict[str, Any]] = None
) -> List[Dict]:
    """
    查询记录
    conditions: 可选，例如 {"name": "张三", "age": 20}
    """
    _validate_table(table)
    with get_connection(db_path) as conn:
        _enable_dict_factory(conn)
        if conditions:
            where_clause = " AND ".join([f"{k}=?" for k in conditions.keys()])
            sql = f"SELECT * FROM {table} WHERE {where_clause}"
            cursor = conn.execute(sql, list(conditions.values()))
        else:
            sql = f"SELECT * FROM {table}"
            cursor = conn.execute(sql)
        return cursor.fetchall()


def update_record(
    db_path: str | Path, table: str, record_id: int, data: Dict[str, Any]
) -> int:
    """
    更新单条记录（按 id 更新）
    返回：受影响的行数
    """
    _validate_table(table)
    set_clause = ", ".join([f'"{k}"=?' for k in data.keys()])
    sql = f"UPDATE {table} SET {set_clause} WHERE id=?"

    with get_connection(db_path) as conn:
        cursor = conn.execute(sql, list(data.values()) + [record_id])
        return cursor.rowcount


def delete_record(db_path: str | Path, table: str, record_id: int) -> int:
    """
    删除单条记录（按 id 删除）
    返回：受影响的行数
    """
    _validate_table(table)
    sql = f"DELETE FROM {table} WHERE id=?"

    with get_connection(db_path) as conn:
        cursor = conn.execute(sql, (record_id,))
        return cursor.rowcount


# ========== 批量操作 ==========


def batch_create_records(
    db_path: str | Path, table: str, records: List[Dict[str, Any]]
) -> List[int]:
    """
    批量插入多条记录
    返回：新插入记录的 ID 列表
    注意: executemany 的 lastrowid 在 SQLite 中可能不可靠，
    高并发场景建议改用循环调用 create_record。
    """
    _validate_table(table)
    if not records:
        return []

    columns = _quote_columns(records[0].keys())
    placeholders = ", ".join(["?"] * len(records[0]))
    sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"

    values = [[record[col] for col in records[0].keys()] for record in records]

    with get_connection(db_path) as conn:
        cursor = conn.executemany(sql, values)
        # 获取最后插入的 ID 范围
        last_id = cursor.lastrowid
        return list(range(last_id - len(records) + 1, last_id + 1))


def batch_update_records(db_path: str | Path, table: str, updates: List[Dict]) -> int:
    """
    批量更新多条记录
    updates 格式: [{"id": 1, "field1": "new_value", ...}, ...]
    返回：总受影响行数
    """
    _validate_table(table)
    if not updates:
        return 0

    # 取第一个记录确定要更新的字段（排除 id）
    sample = updates[0]
    update_fields = [k for k in sample.keys() if k != "id"]
    set_clause = ", ".join([f'"{k}"=?' for k in update_fields])
    sql = f"UPDATE {table} SET {set_clause} WHERE id=?"

    values = []
    for record in updates:
        row = [record[field] for field in update_fields] + [record["id"]]
        values.append(row)

    with get_connection(db_path) as conn:
        cursor = conn.executemany(sql, values)
        return cursor.rowcount


def batch_delete_records(db_path: str | Path, table: str, record_ids: List[int]) -> int:
    """
    批量删除多条记录（按 id 列表删除）
    返回：受影响的行数
    """
    _validate_table(table)
    if not record_ids:
        return 0

    placeholders = ", ".join(["?"] * len(record_ids))
    sql = f"DELETE FROM {table} WHERE id IN ({placeholders})"

    with get_connection(db_path) as conn:
        cursor = conn.execute(sql, record_ids)
        return cursor.rowcount


# ========== 条件批量操作 ==========


def batch_update_by_condition(
    db_path: str | Path, table: str, conditions: Dict[str, Any], updates: Dict[str, Any]
) -> int:
    """
    按条件批量更新
    conditions: 筛选条件，例如 {"class": "高三一班"}
    updates: 更新的数据，例如 {"score": 100}
    返回：受影响的行数
    """
    _validate_table(table)
    set_clause = ", ".join([f'"{k}"=?' for k in updates.keys()])
    where_clause = " AND ".join([f'"{k}"=?' for k in conditions.keys()])
    sql = f"UPDATE {table} SET {set_clause} WHERE {where_clause}"

    params = list(updates.values()) + list(conditions.values())

    with get_connection(db_path) as conn:
        cursor = conn.execute(sql, params)
        return cursor.rowcount


def batch_delete_by_condition(
    db_path: str | Path, table: str, conditions: Dict[str, Any]
) -> int:
    """
    按条件批量删除
    conditions: 筛选条件，例如 {"class": "高三一班", "score": "<60"}（注意：复杂条件建议直接用 sql）
    返回：受影响的行数
    """
    _validate_table(table)
    where_clause = " AND ".join([f'"{k}"=?' for k in conditions.keys()])
    sql = f"DELETE FROM {table} WHERE {where_clause}"

    with get_connection(db_path) as conn:
        cursor = conn.execute(sql, list(conditions.values()))
        return cursor.rowcount


# ========== 安全查询（防 SQL 注入）==========


def safe_query(db_path: str | Path, sql: str, params: tuple = ()) -> List[Dict]:
    """
    执行自定义查询（仅供需要复杂查询时使用）
    注意：sql 参数必须使用 ? 占位符，params 传入实际值
    """
    with get_connection(db_path) as conn:
        _enable_dict_factory(conn)
        cursor = conn.execute(sql, params)
        return cursor.fetchall()
