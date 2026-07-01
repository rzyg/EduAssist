"""
core/db/CRUD.py 单元测试

测试目标:
  - 所有 CRUD 函数在临时 SQLite 数据库上的行为
  - 批量操作
  - 表名白名单验证
"""
import pytest
from core.db.CRUD import (
    create_record, read_records, update_record, delete_record,
    batch_create_records, batch_update_records, batch_delete_records,
    batch_update_by_condition, batch_delete_by_condition,
)


# =============================================================================
# 辅助：在每个测试之前初始化 user 表
# =============================================================================

@pytest.fixture(autouse=True)
def setup_db(tmp_db_path: str):
    """在每个 CRUD 测试前创建 user 表"""
    # 直接在临时路径上执行建表语句
    import sqlite3
    with sqlite3.connect(tmp_db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                phone TEXT NOT NULL,
                identity TEXT NOT NULL
            )
        """)
    yield
    # 测试结束后删除临时 db 文件（tmp_path 自动清理）


# =============================================================================
# 基础 CRUD
# =============================================================================

class TestCreateRecord:
    """插入单条记录"""

    def test_insert(self, tmp_db_path):
        """插入后返回自增 ID"""
        user_id = create_record(tmp_db_path, "user", {
            "username": "张三", "phone": "13800138000", "identity": "教师"
        })
        assert user_id is not None and user_id > 0

    def test_insert_and_read_back(self, tmp_db_path):
        """插入后能查询到"""
        user_id = create_record(tmp_db_path, "user", {
            "username": "李四", "phone": "13900139000", "identity": "班主任"
        })
        records = read_records(tmp_db_path, "user", {"id": user_id})
        assert len(records) == 1
        assert records[0]["username"] == "李四"


class TestReadRecords:
    """查询记录"""

    def test_read_all_empty(self, tmp_db_path):
        """空表返回空列表"""
        records = read_records(tmp_db_path, "user")
        assert records == []

    def test_read_all(self, tmp_db_path):
        """查询所有记录"""
        create_record(tmp_db_path, "user", {"username": "a", "phone": "1", "identity": "x"})
        create_record(tmp_db_path, "user", {"username": "b", "phone": "2", "identity": "y"})
        records = read_records(tmp_db_path, "user")
        assert len(records) == 2

    def test_read_with_conditions(self, tmp_db_path):
        """带条件查询"""
        create_record(tmp_db_path, "user", {"username": "甲", "phone": "111", "identity": "T"})
        create_record(tmp_db_path, "user", {"username": "乙", "phone": "222", "identity": "S"})
        records = read_records(tmp_db_path, "user", {"identity": "S"})
        assert len(records) == 1
        assert records[0]["username"] == "乙"

    def test_read_returns_dicts(self, tmp_db_path):
        """查询结果返回字典格式"""
        create_record(tmp_db_path, "user", {"username": "丙", "phone": "333", "identity": "U"})
        records = read_records(tmp_db_path, "user")
        row = records[0]
        assert isinstance(row, dict)
        assert "username" in row
        assert "phone" in row


class TestUpdateRecord:
    """更新记录"""

    def test_update(self, tmp_db_path):
        """按 id 更新后数据变更"""
        uid = create_record(tmp_db_path, "user", {
            "username": "旧名", "phone": "000", "identity": "X"
        })
        affected = update_record(tmp_db_path, "user", uid, {"username": "新名"})
        assert affected == 1
        records = read_records(tmp_db_path, "user", {"id": uid})
        assert records[0]["username"] == "新名"

    def test_update_nonexistent(self, tmp_db_path):
        """更新不存在的 id 返回 0"""
        affected = update_record(tmp_db_path, "user", 999, {"username": "谁"})
        assert affected == 0


class TestDeleteRecord:
    """删除记录"""

    def test_delete(self, tmp_db_path):
        """删除后记录不存在"""
        uid = create_record(tmp_db_path, "user", {
            "username": "待删", "phone": "000", "identity": "D"
        })
        affected = delete_record(tmp_db_path, "user", uid)
        assert affected == 1
        records = read_records(tmp_db_path, "user", {"id": uid})
        assert len(records) == 0

    def test_delete_nonexistent(self, tmp_db_path):
        """删除不存在的 id 返回 0"""
        affected = delete_record(tmp_db_path, "user", 999)
        assert affected == 0


# =============================================================================
# 批量操作
# =============================================================================

class TestBatchCreateRecords:
    """批量插入"""

    def test_batch_create(self, tmp_db_path):
        """批量插入后所有记录可查询"""
        ids = batch_create_records(tmp_db_path, "user", [
            {"username": "a1", "phone": "1", "identity": "T"},
            {"username": "a2", "phone": "2", "identity": "T"},
            {"username": "a3", "phone": "3", "identity": "T"},
        ])
        records = read_records(tmp_db_path, "user")
        assert len(records) == 3
        usernames = [r["username"] for r in records]
        assert "a1" in usernames
        assert "a2" in usernames
        assert "a3" in usernames

    def test_batch_create_empty(self, tmp_db_path):
        """空列表返回 []"""
        ids = batch_create_records(tmp_db_path, "user", [])
        assert ids == []


class TestBatchUpdateRecords:
    """批量更新"""

    def test_batch_update(self, tmp_db_path):
        u1 = create_record(tmp_db_path, "user", {"username": "x", "phone": "1", "identity": "A"})
        u2 = create_record(tmp_db_path, "user", {"username": "y", "phone": "2", "identity": "B"})
        affected = batch_update_records(tmp_db_path, "user", [
            {"id": u1, "username": "x_new"},
            {"id": u2, "username": "y_new"},
        ])
        assert affected == 2
        records = read_records(tmp_db_path, "user")
        usernames = {r["username"] for r in records}
        assert usernames == {"x_new", "y_new"}

    def test_batch_update_empty(self, tmp_db_path):
        affected = batch_update_records(tmp_db_path, "user", [])
        assert affected == 0


class TestBatchDeleteRecords:
    """批量删除"""

    def test_batch_delete(self, tmp_db_path):
        u1 = create_record(tmp_db_path, "user", {"username": "d1", "phone": "1", "identity": "D"})
        u2 = create_record(tmp_db_path, "user", {"username": "d2", "phone": "2", "identity": "D"})
        u3 = create_record(tmp_db_path, "user", {"username": "d3", "phone": "3", "identity": "D"})
        affected = batch_delete_records(tmp_db_path, "user", [u1, u3])
        assert affected == 2
        records = read_records(tmp_db_path, "user")
        assert len(records) == 1
        assert records[0]["username"] == "d2"

    def test_batch_delete_empty(self, tmp_db_path):
        affected = batch_delete_records(tmp_db_path, "user", [])
        assert affected == 0


# =============================================================================
# 条件批量操作
# =============================================================================

class TestBatchUpdateByCondition:
    """按条件批量更新"""

    def test_update_by_condition(self, tmp_db_path):
        create_record(tmp_db_path, "user", {"username": "u1", "phone": "111", "identity": "T"})
        create_record(tmp_db_path, "user", {"username": "u2", "phone": "222", "identity": "T"})
        create_record(tmp_db_path, "user", {"username": "u3", "phone": "333", "identity": "S"})
        affected = batch_update_by_condition(
            tmp_db_path, "user",
            conditions={"identity": "T"},
            updates={"phone": "000"}
        )
        assert affected == 2
        records = read_records(tmp_db_path, "user", {"identity": "T"})
        for r in records:
            assert r["phone"] == "000"


class TestBatchDeleteByCondition:
    """按条件批量删除"""

    def test_delete_by_condition(self, tmp_db_path):
        create_record(tmp_db_path, "user", {"username": "k1", "phone": "1", "identity": "K"})
        create_record(tmp_db_path, "user", {"username": "k2", "phone": "2", "identity": "K"})
        create_record(tmp_db_path, "user", {"username": "k3", "phone": "3", "identity": "L"})
        affected = batch_delete_by_condition(tmp_db_path, "user", {"identity": "K"})
        assert affected == 2
        records = read_records(tmp_db_path, "user")
        assert len(records) == 1
        assert records[0]["identity"] == "L"


# =============================================================================
# 安全校验
# =============================================================================

class TestTableValidation:
    """表名白名单验证"""

    def test_unknown_table_create(self, tmp_db_path):
        with pytest.raises(ValueError, match="不在白名单"):
            create_record(tmp_db_path, "unknown_table", {"x": 1})

    def test_unknown_table_read(self, tmp_db_path):
        with pytest.raises(ValueError, match="不在白名单"):
            read_records(tmp_db_path, "hack_table")

    def test_unknown_table_update(self, tmp_db_path):
        with pytest.raises(ValueError, match="不在白名单"):
            update_record(tmp_db_path, "evil_table", 1, {"x": 1})

    def test_unknown_table_delete(self, tmp_db_path):
        with pytest.raises(ValueError, match="不在白名单"):
            delete_record(tmp_db_path, "drop_table", 1)

    def test_unknown_table_batch_create(self, tmp_db_path):
        with pytest.raises(ValueError, match="不在白名单"):
            batch_create_records(tmp_db_path, "malicious", [{"x": 1}])

    def test_known_table_allowed(self, tmp_db_path):
        """user 表在白名单内，操作正常"""
        uid = create_record(tmp_db_path, "user", {
            "username": "test", "phone": "000", "identity": "safe"
        })
        assert uid is not None
