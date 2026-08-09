"""
core/allowance/utils/holiday.py 与 core/route/allowance.py 单元测试

测试目标:
  - 离校/返校计算（含跨年边界、补班日、多假期段）
  - 同步入库的幂等性
  - 读库优先的获取逻辑
  - get_calendar 路由返回结构
  - 修改假期表接口（update_holiday_record 数据层 + PUT /update_holiday 路由层）
"""
import asyncio
import json
import sqlite3
from unittest import mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.allowance.utils import holiday as H
from core.route.allowance import get_calendar, router, update_holiday


# =============================================================================
# 辅助：在每个测试之前初始化 holiday 表
# =============================================================================

@pytest.fixture(autouse=True)
def setup_holiday_db(tmp_db_path: str):
    """在每个测试前创建 holiday 表"""
    with sqlite3.connect(tmp_db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS holiday (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                year INTEGER NOT NULL,
                month_day TEXT NOT NULL,
                holiday INTEGER NOT NULL,
                leave_school INTEGER NOT NULL DEFAULT 0,
                return_school INTEGER NOT NULL DEFAULT 0,
                schedule_modification TEXT,
                remark TEXT,
                UNIQUE(year, month_day)
            )
        """)
    yield


def fake_holiday_dict(year: int) -> dict:
    """模拟 timor.tech 返回：元旦 2 天连假 + 02-15 补班"""
    return {
        "01-01": {"holiday": True, "date": f"{year}-01-01"},
        "01-02": {"holiday": True, "date": f"{year}-01-02"},
        "02-15": {"holiday": False, "date": f"{year}-02-15"},
    }


# =============================================================================
# 离校/返校计算
# =============================================================================

class TestComputeDayFlags:
    def test_leave_and_return_flags(self):
        """段首前一天离校（跨年到 12-31），段尾返校"""
        recs = H._compute_day_flags(2026, fake_holiday_dict(2026))
        by_md = {r["month_day"]: r for r in recs}
        # 段首 01-01 的前一天是 2025-12-31，按真实年份入库
        assert by_md["12-31"]["year"] == 2025
        assert by_md["12-31"]["leave_school"] == 1
        # 段尾 01-02 返校
        assert by_md["01-02"]["return_school"] == 1
        # 假期日标记
        assert by_md["01-01"]["holiday"] == 1
        # 补班日（holiday=false）入库，非离校/返校
        assert by_md["02-15"]["holiday"] == 0
        assert by_md["02-15"]["leave_school"] == 0
        assert by_md["02-15"]["return_school"] == 0

    def test_all_booleans_not_empty(self):
        """除课表修改/备注外，其余字段均显式赋值不为空"""
        recs = H._compute_day_flags(2026, fake_holiday_dict(2026))
        assert recs
        for r in recs:
            assert r["holiday"] in (0, 1)
            assert r["leave_school"] in (0, 1)
            assert r["return_school"] in (0, 1)
            assert r["schedule_modification"] is None
            assert r["remark"] is None

    def test_multi_blocks(self):
        """多个不连续假期段各自计算离校/返校"""
        data = {
            "04-04": {"holiday": True, "date": "2026-04-04"},
            "04-05": {"holiday": True, "date": "2026-04-05"},
            "05-01": {"holiday": True, "date": "2026-05-01"},
        }
        recs = H._compute_day_flags(2026, data)
        by_md = {r["month_day"]: r for r in recs}
        assert by_md["04-03"]["leave_school"] == 1
        assert by_md["04-05"]["return_school"] == 1
        assert by_md["04-30"]["leave_school"] == 1
        assert by_md["05-01"]["return_school"] == 1
        # 段内日期不再重复标记离校
        assert by_md["04-04"]["leave_school"] == 0


# =============================================================================
# 同步入库
# =============================================================================

class TestSyncHolidayData:
    def test_sync_idempotent(self, tmp_db_path):
        """已有该年数据时跳过，不重复请求网络"""
        with mock.patch.object(H, "_fetch_holiday_data", side_effect=fake_holiday_dict) as m:
            assert H.sync_holiday_data(2026, tmp_db_path) == 4
            assert m.call_count == 1
            assert H.sync_holiday_data(2026, tmp_db_path) == 0
            assert m.call_count == 1

    def test_sync_writes_records(self, tmp_db_path):
        """入库后可读回完整记录"""
        with mock.patch.object(H, "_fetch_holiday_data", side_effect=fake_holiday_dict):
            H.sync_holiday_data(2026, tmp_db_path)
        recs = H.get_holiday_data(2026, tmp_db_path)
        assert [r["month_day"] for r in recs] == ["01-01", "01-02", "02-15"]
        assert recs[0]["holiday"] is True
        assert recs[2]["holiday"] is False


# =============================================================================
# 读取逻辑
# =============================================================================

class TestGetHolidayData:
    def test_reads_db_without_fetch(self, tmp_db_path):
        """库中有数据时直接读取，不请求网络"""
        with mock.patch.object(H, "_fetch_holiday_data", side_effect=fake_holiday_dict) as m:
            H.sync_holiday_data(2026, tmp_db_path)
            recs = H.get_holiday_data(2026, tmp_db_path)
            assert m.call_count == 1
        assert len(recs) == 3

    def test_auto_sync_when_missing(self, tmp_db_path):
        """库中无该年数据时自动请求并入库"""
        with mock.patch.object(H, "_fetch_holiday_data", side_effect=fake_holiday_dict) as m:
            recs = H.get_holiday_data(2027, tmp_db_path)
            assert m.call_count == 1
        assert len(recs) == 3

    def test_booleans(self, tmp_db_path):
        """读取后布尔字段为 Python bool"""
        with mock.patch.object(H, "_fetch_holiday_data", side_effect=fake_holiday_dict):
            H.sync_holiday_data(2026, tmp_db_path)
        for r in H.get_holiday_data(2026, tmp_db_path):
            assert isinstance(r["holiday"], bool)
            assert isinstance(r["leave_school"], bool)
            assert isinstance(r["return_school"], bool)


# =============================================================================
# 路由返回结构
# =============================================================================

class TestGetCalendar:
    def test_return_structure(self):
        """返回 {"holiday": {"01-01": {数据库字段..., date}}}，不含 first_day"""
        sample = [
            {"id": 1, "year": 2026, "month_day": "01-01", "holiday": True,
             "leave_school": False, "return_school": False,
             "schedule_modification": None, "remark": None},
        ]

        async def main():
            with mock.patch("core.route.allowance.get_holiday_data", return_value=sample):
                resp = await get_calendar(year=2026)
            assert "first_day" not in resp
            assert list(resp["holiday"].keys()) == ["01-01"]
            assert resp["holiday"]["01-01"]["date"] == "2026-01-01"
            assert resp["holiday"]["01-01"]["holiday"] is True
            assert resp["holiday"]["01-01"]["leave_school"] is False

        asyncio.run(main())


# =============================================================================
# 跨年同步修复（sync 判断与 UPSERT 合并）
# =============================================================================

class TestCrossYearSync:
    def test_get_triggers_sync_when_only_cross_year_record(self, tmp_db_path):
        """2025 只有跨年自动生成的离校记录（holiday=false）时，获取仍触发同步"""
        conn = sqlite3.connect(tmp_db_path)
        conn.execute(
            "INSERT INTO holiday (year, month_day, holiday, leave_school, return_school) "
            "VALUES (2025, '12-31', 0, 1, 0)"
        )
        conn.commit()
        conn.close()

        def fetch_2025(year):
            assert year == 2025
            return {"01-01": {"holiday": True, "date": "2025-01-01"},
                    "01-02": {"holiday": True, "date": "2025-01-02"}}

        with mock.patch.object(H, "_fetch_holiday_data", side_effect=fetch_2025) as m:
            recs = H.get_holiday_data(2025, tmp_db_path)
            assert m.call_count == 1  # 必须触发请求
            assert len(recs) > 1      # 不再只有 1 条
            by_md = {r["month_day"]: r for r in recs}
            assert by_md["01-01"]["holiday"] is True
            assert by_md["12-31"]["leave_school"] is True  # 跨年离校标记保留
            # 同步完成后再次获取不再请求
            H.get_holiday_data(2025, tmp_db_path)
            assert m.call_count == 1

    def test_upsert_merges_cross_year_conflict(self, tmp_db_path):
        """同一天双来源（一年假期 + 另一年离校日）合并布尔标记，人工字段保留"""
        def fetch_2026(year):
            return {"01-01": {"holiday": True, "date": "2026-01-01"},
                    "01-02": {"holiday": True, "date": "2026-01-02"}}

        def fetch_2025(year):
            return {"12-31": {"holiday": True, "date": "2025-12-31"}}

        with mock.patch.object(H, "_fetch_holiday_data", side_effect=fetch_2026):
            H.sync_holiday_data(2026, tmp_db_path)  # 生成 2025-12-31 离校记录

        # 人工维护该天字段
        H.update_holiday_record(2025, "12-31", schedule_modification={"x": 1},
                                remark="人工", db_path=tmp_db_path)

        with mock.patch.object(H, "_fetch_holiday_data", side_effect=fetch_2025):
            assert H.sync_holiday_data(2025, tmp_db_path) == 2  # 12-31 + 12-30 离校

        from core.db.CRUD import read_records
        row = read_records(tmp_db_path, "holiday", {"year": 2025, "month_day": "12-31"})[0]
        assert row["holiday"] == 1          # 假期标记合并
        assert row["leave_school"] == 1     # 离校标记保留
        assert row["return_school"] == 1    # 段尾返校合并
        assert row["schedule_modification"] is not None  # 人工字段未被覆盖
        assert row["remark"] == "人工"

    def test_sync_skips_when_has_holiday_records(self, tmp_db_path):
        """该年已有 holiday=true 记录时同步跳过且不请求"""
        def fetch_2026(year):
            return {"01-01": {"holiday": True, "date": "2026-01-01"}}

        with mock.patch.object(H, "_fetch_holiday_data", side_effect=fetch_2026) as m:
            assert H.sync_holiday_data(2026, tmp_db_path) == 2  # 01-01 + 12-31 离校
            assert m.call_count == 1
            assert H.sync_holiday_data(2026, tmp_db_path) == 0
            assert m.call_count == 1


# =============================================================================
# 修改假期表（数据层 update_holiday_record）
# =============================================================================

class TestUpdateHolidayRecord:
    def test_create_when_missing(self, tmp_db_path):
        """表中不存在该天 → 新增，holiday 固定 false，默认布尔为 false"""
        r = H.update_holiday_record(2026, "03-05", leave_school=True, remark="春游", db_path=tmp_db_path)
        assert r["holiday"] is False
        assert r["leave_school"] is True
        assert r["return_school"] is False
        assert r["remark"] == "春游"
        assert r["schedule_modification"] is None

    def test_partial_update_keeps_others(self, tmp_db_path):
        """已存在 → 只更新传入字段，未传字段保持原值"""
        H.update_holiday_record(2026, "03-05", leave_school=True, remark="春游", db_path=tmp_db_path)
        r = H.update_holiday_record(2026, "03-05", return_school=True,
                                    schedule_modification={"早读": "取消"}, db_path=tmp_db_path)
        assert r["leave_school"] is True      # 保持
        assert r["return_school"] is True     # 本次更新
        assert "早读" in r["schedule_modification"] and "取消" in r["schedule_modification"]
        assert r["remark"] == "春游"           # 保持

    def test_idempotent_no_duplicate(self, tmp_db_path):
        """同一天多次提交不会重复新增记录"""
        from core.db.CRUD import read_records
        H.update_holiday_record(2026, "03-05", leave_school=True, db_path=tmp_db_path)
        H.update_holiday_record(2026, "03-05", remark="", db_path=tmp_db_path)
        rows = read_records(tmp_db_path, "holiday", {"year": 2026})
        assert len(rows) == 1

    def test_invalid_month_day(self, tmp_db_path):
        """非法月日抛 ValueError"""
        for bad in ("02-30", "13-01", "3-05", "03/05", "abc"):
            with pytest.raises(ValueError):
                H.update_holiday_record(2026, bad, db_path=tmp_db_path)

    def test_schedule_modification_serialization(self, tmp_db_path):
        """课表修改 dict 序列化为 JSON 字符串；传 {} 表示清空"""
        r = H.update_holiday_record(2026, "03-06", schedule_modification={"a": 1}, db_path=tmp_db_path)
        assert json.loads(r["schedule_modification"]) == {"a": 1}
        r2 = H.update_holiday_record(2026, "03-06", schedule_modification={}, db_path=tmp_db_path)
        assert r2["schedule_modification"] == "{}"


# =============================================================================
# 修改假期表（路由层 PUT /update_holiday）
# =============================================================================

class TestUpdateHolidayRoute:
    def test_put_ok(self):
        """合法请求返回 200 与完整记录（含 date）"""
        sample = {"id": 7, "year": 2026, "month_day": "03-05", "holiday": False,
                  "leave_school": True, "return_school": False,
                  "schedule_modification": None, "remark": "x"}
        app = FastAPI()
        app.include_router(router)
        with mock.patch("core.route.allowance.update_holiday_record", return_value=dict(sample)):
            client = TestClient(app)
            resp = client.put("/api/v1/allowance/update_holiday",
                              json={"year": 2026, "month_day": "03-05", "leave_school": True})
        assert resp.status_code == 200
        assert resp.json()["date"] == "2026-03-05"
        assert resp.json()["leave_school"] is True

    def test_put_missing_required(self):
        """缺必填字段 year 返回 422"""
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        resp = client.put("/api/v1/allowance/update_holiday", json={"month_day": "03-05"})
        assert resp.status_code == 422

    def test_put_bad_year_type(self):
        """year 非整数返回 422"""
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        resp = client.put("/api/v1/allowance/update_holiday", json={"year": "abc", "month_day": "03-05"})
        assert resp.status_code == 422

    def test_put_value_error_to_422(self):
        """数据层 ValueError（非法日期）→ 422 且带 detail"""
        app = FastAPI()
        app.include_router(router)
        with mock.patch("core.route.allowance.update_holiday_record",
                        side_effect=ValueError("invalid date 2026-02-30")):
            client = TestClient(app)
            resp = client.put("/api/v1/allowance/update_holiday",
                              json={"year": 2026, "month_day": "02-30"})
        assert resp.status_code == 422
        assert "invalid date" in resp.text

    def test_put_server_error_to_500(self):
        """其他异常 → 500"""
        app = FastAPI()
        app.include_router(router)
        with mock.patch("core.route.allowance.update_holiday_record",
                        side_effect=RuntimeError("boom")):
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.put("/api/v1/allowance/update_holiday",
                              json={"year": 2026, "month_day": "03-05"})
        assert resp.status_code == 500
