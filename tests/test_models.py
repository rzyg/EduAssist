"""
core/score/models.py 单元测试

测试目标:
  - SubjectScore: NamedTuple 的创建与字段访问
  - Student: 构造函数、get_data 的几种查找路径
  - StreamingMap: 基本 CRUD、dunder 方法、JSON 序列化/反序列化
"""
import json
import pytest
from pathlib import Path
from core.score.models import SubjectScore, Student, StreamingMap, ClassManager, SubjectStatistics, ClassStatistics


# =============================================================================
# SubjectScore
# =============================================================================

class TestSubjectScore:
    """单科成绩与排名数据容器的基本行为"""

    def test_create(self):
        """能以 (score, class_rank, school_rank) 创建"""
        s = SubjectScore(95.5, 1, 3)
        assert s.score == 95.5
        assert s.class_rank == 1
        assert s.school_rank == 3

    def test_immutable(self):
        """NamedTuple 不可变，尝试修改会抛 AttributeError"""
        s = SubjectScore(80, 5, 10)
        with pytest.raises(AttributeError):
            s.score = 90

    def test_unpacking(self):
        """支持元组解包"""
        score, cr, sr = SubjectScore(100, 2, 4)
        assert score == 100
        assert cr == 2
        assert sr == 4


# =============================================================================
# Student
# =============================================================================

class TestStudent:
    """学生对象的数据查询功能"""

    @pytest.fixture
    def student(self):
        return Student(
            student_class="一班",
            name="测试生",
            selection="物化生",
            subjects={
                "语文": SubjectScore(120, 2, 5),
                "数学": SubjectScore(130, 1, 3),
            }
        )

    def test_get_score(self, student):
        """get_data('语文') 返回分数"""
        assert student.get_data("语文") == 120

    def test_get_class_rank(self, student):
        """get_data('语文班名') 返回班排名"""
        assert student.get_data("语文班名") == 2

    def test_get_school_rank(self, student):
        """get_data('语文校名') 返回校排名"""
        assert student.get_data("语文校名") == 5

    def test_get_unknown_subject(self, student):
        """查询不存在的科目返回 None 而不是抛异常"""
        assert student.get_data("不存在") is None

    def test_get_unknown_rank(self, student):
        """查询不存在的科目排名返回 None"""
        assert student.get_data("不存在班名") is None

    @pytest.fixture
    def student_empty(self):
        """无任何科目的学生"""
        return Student("二班", "空学生", {}, "")

    def test_empty_subjects(self, student_empty):
        """没有科目的学生查询任意内容都返回 None"""
        assert student_empty.get_data("语文") is None


# =============================================================================
# StreamingMap
# =============================================================================

class TestStreamingMap:
    """列映射表的增删改查与序列化"""

    def test_set_and_get(self):
        """set() 存入后 get() 能取出"""
        m = StreamingMap()
        m.set("姓名", 2)
        assert m.get("姓名") == 2

    def test_get_default(self):
        """get() 不存在的 key 返回默认值 None"""
        m = StreamingMap()
        assert m.get("不存在") is None

    def test_get_custom_default(self):
        """get() 可指定自定义默认值"""
        m = StreamingMap()
        assert m.get("不存在", -1) == -1

    def test_update(self):
        """update() 批量设置"""
        m = StreamingMap()
        m.update({"姓名": 2, "语文": 4})
        assert m["姓名"] == 2
        assert m["语文"] == 4

    def test_remove_existing(self):
        """remove() 移除已存在的 key"""
        m = StreamingMap()
        m.set("姓名", 2)
        m.remove("姓名")
        assert m.has("姓名") is False

    def test_remove_missing(self):
        """remove() 不存在的 key 不抛异常"""
        m = StreamingMap()
        m.remove("不存在")  # 不应抛异常

    def test_has(self):
        """has() 正确判断 key 是否存在"""
        m = StreamingMap()
        m.set("姓名", 2)
        assert m.has("姓名") is True
        assert m.has("年龄") is False

    def test_get_all(self):
        """get_all() 返回副本，修改副本不影响原对象"""
        m = StreamingMap()
        m.set("姓名", 2)
        copy = m.get_all()
        copy["姓名"] = 999
        assert m["姓名"] == 2

    def test_clear(self):
        """clear() 清空所有映射"""
        m = StreamingMap()
        m.set("姓名", 2)
        m.clear()
        assert len(m) == 0

    # ── dunder 方法 ──

    def test_getitem(self):
        """m['姓名'] 下标访问"""
        m = StreamingMap()
        m.set("姓名", 2)
        assert m["姓名"] == 2

    def test_getitem_missing(self):
        """不存在的 key 下标访问抛 KeyError"""
        m = StreamingMap()
        with pytest.raises(KeyError):
            _ = m["不存在"]

    def test_setitem(self):
        """m['姓名'] = 3 下标赋值"""
        m = StreamingMap()
        m["姓名"] = 3
        assert m["姓名"] == 3

    def test_contains(self):
        """"姓名" in mapping"""
        m = StreamingMap()
        m.set("姓名", 2)
        assert "姓名" in m
        assert "年龄" not in m

    def test_len(self):
        """len(mapping) 返回映射数量"""
        m = StreamingMap()
        m.set("a", 1)
        m.set("b", 2)
        assert len(m) == 2

    def test_repr(self):
        """repr 包含映射内容"""
        m = StreamingMap()
        m.set("a", 1)
        assert "StreamingMap" in repr(m)
        assert "a" in repr(m)

    # ── JSON 序列化 ──

    def test_save_and_load_file(self, tmp_path: Path):
        """save_to_file → load_from_file 往返一致"""
        m1 = StreamingMap()
        m1.update({"姓名": 2, "语文": 4})

        path = tmp_path / "mapping.json"
        m1.save_to_file(str(path))

        m2 = StreamingMap()
        m2.load_from_file(str(path))
        assert m2["姓名"] == 2
        assert m2["语文"] == 4

    def test_load_from_json_text(self):
        """load_from_json_text 从 JSON 字符串恢复"""
        m = StreamingMap()
        m.load_from_json_text('{"姓名": 2, "语文": 4}')
        assert m["姓名"] == 2
        assert m["语文"] == 4

    def test_load_from_json_text_invalid(self):
        """无效 JSON 字符串抛 json.JSONDecodeError"""
        m = StreamingMap()
        with pytest.raises(json.JSONDecodeError):
            m.load_from_json_text("这不是 JSON")


# =============================================================================
# ClassManager
# =============================================================================

class TestClassManager:
    """班级管理器的分组与查询功能"""

    # ── 辅助夹具 ──

    @pytest.fixture
    def student_a(self):
        return Student("一班", "甲", {"语文": SubjectScore(100, 1, 2)}, "物化生")

    @pytest.fixture
    def student_b(self):
        return Student("一班", "乙", {"数学": SubjectScore(90, 2, 5)}, "物化生")

    @pytest.fixture
    def student_c(self):
        return Student("二班", "丙", {"英语": SubjectScore(80, 3, 8)}, "史政地")

    def test_add_and_get_class(self, student_a, student_b, student_c):
        """添加学生后能按班级获取"""
        mgr = ClassManager()
        mgr.add_student(student_a)
        mgr.add_student(student_b)
        mgr.add_student(student_c)

        class1 = mgr.get_class("一班")
        assert len(class1) == 2
        assert class1[0].name == "甲"
        assert class1[1].name == "乙"

        class2 = mgr.get_class("二班")
        assert len(class2) == 1
        assert class2[0].name == "丙"

    def test_get_all_classes(self, student_a, student_c):
        """获取所有班级名称"""
        mgr = ClassManager()
        mgr.add_student(student_a)
        mgr.add_student(student_c)
        classes = mgr.get_all_classes()
        assert "一班" in classes
        assert "二班" in classes
        assert len(classes) == 2

    def test_get_student_count(self, student_a, student_b):
        """统计班级人数"""
        mgr = ClassManager()
        mgr.add_student(student_a)
        mgr.add_student(student_b)
        assert mgr.get_student_count("一班") == 2
        assert mgr.get_student_count("三班") == 0  # 不存在的班

    def test_get_nonexistent_class(self):
        """不存在的班级返回空列表"""
        mgr = ClassManager()
        assert mgr.get_class("不存在") == []

    def test_empty_class_list(self):
        """空管理器返回空班级列表"""
        mgr = ClassManager()
        assert mgr.get_all_classes() == []

    def test_skip_student_without_class(self):
        """没有班级信息的学生跳过添加"""
        mgr = ClassManager()
        no_class = Student(None, "无名氏", {"总分": SubjectScore(500, 1, 1)}, "")
        mgr.add_student(no_class)
        assert mgr.get_all_classes() == []

    def test_export_to_dict(self, student_a, student_c):
        """导出为字典格式"""
        mgr = ClassManager()
        mgr.add_student(student_a)
        mgr.add_student(student_c)
        exported = mgr.export_to_dict()
        assert isinstance(exported, dict)
        assert "一班" in exported
        assert len(exported["一班"]) == 1


# =============================================================================
# SubjectStatistics
# =============================================================================

class TestSubjectStatistics:
    """单科统计数据"""

    def test_default_zero(self):
        """默认单双上线均为 0"""
        s = SubjectStatistics()
        assert s.single == 0
        assert s.double == 0

    def test_increment_single(self):
        """单上线自增"""
        s = SubjectStatistics()
        s.single += 1
        assert s.single == 1

    def test_increment_double(self):
        """双上线自增"""
        s = SubjectStatistics()
        s.double += 1
        assert s.double == 1


# =============================================================================
# ClassStatistics
# =============================================================================

class TestClassStatistics:
    """班级各科单双上线统计"""

    @pytest.fixture
    def stats(self):
        return ClassStatistics("高三1班", 50)

    def test_init(self, stats):
        """初始化班级名称和学生人数"""
        assert stats.name == "高三1班"
        assert stats.count == 50

    def test_init_subject(self, stats):
        """init_subject 创建科目统计对象"""
        stats.init_subject("语文清北线")
        assert "语文清北线" in stats.statistics
        assert stats.statistics["语文清北线"].single == 0

    def test_init_subject_idempotent(self, stats):
        """重复 init_subject 不会覆盖已有数据"""
        stats.init_subject("总分985线")
        stats.increment_single("总分985线")
        stats.init_subject("总分985线")  # 再次调用
        assert stats.statistics["总分985线"].single == 1

    def test_increment_single(self, stats):
        """单上线计数自增"""
        stats.init_subject("数学985线")
        stats.increment_single("数学985线")
        assert stats.statistics["数学985线"].single == 1

    def test_increment_double(self, stats):
        """双上线计数自增"""
        stats.init_subject("数学985线")
        stats.increment_double("数学985线")
        assert stats.statistics["数学985线"].double == 1

    def test_get_statistics_data(self, stats):
        """get_statistics_data 返回副本（浅拷贝：新 key 不影响原数据）"""
        stats.init_subject("总分清北线")
        stats.increment_single("总分清北线")
        data = stats.get_statistics_data()
        # 在副本中添加新 key，不影响原数据
        data["新增测试"] = SubjectStatistics(99, 99)
        assert "新增测试" not in stats.statistics
        # 删除副本中的 key，不影响原数据
        del data["总分清北线"]
        assert "总分清北线" in stats.statistics
