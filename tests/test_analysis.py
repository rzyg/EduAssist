"""
core/score/analysis.py 单元测试

测试目标:
  - detect_selection_direction: 判断班级选科方向
  - run_statistics: 单科单双上线统计
  - analysis: 班级维度的完整统计流程
"""
import pytest
from core.score.models import (
    Student, SubjectScore, ClassManager, ClassStatistics,
    StreamingMap, SubjectStatistics,
)
from core.score.analysis import detect_selection_direction, run_statistics, analysis


# =============================================================================
# detect_selection_direction
# =============================================================================

class TestDetectSelectionDirection:
    """从学生列表判断选科方向"""

    def test_physics_direction(self):
        """有物理无历史 → 物理方向"""
        students = [
            Student("一班", "甲", {"物理": SubjectScore(95, 1, 3), "语文": SubjectScore(120, 1, 2)}, "物化生"),
        ]
        assert detect_selection_direction(students) == "物理"

    def test_history_direction(self):
        """有历史无物理 → 历史方向"""
        students = [
            Student("一班", "甲", {"历史": SubjectScore(85, 1, 5), "语文": SubjectScore(110, 2, 4)}, "史政地"),
        ]
        assert detect_selection_direction(students) == "历史"

    def test_unsplit(self):
        """同时有物理和历史 → 未分科"""
        students = [
            Student("一班", "甲", {"物理": SubjectScore(95, 1, 3), "历史": SubjectScore(85, 2, 5)}, "物化生"),
        ]
        assert detect_selection_direction(students) == "未分科"

    def test_no_subjects_raises(self):
        """没有任何选科信息 → 抛 ValueError"""
        students = [
            Student("一班", "甲", {"语文": SubjectScore(120, 1, 2)}, ""),
        ]
        with pytest.raises(ValueError, match="无法判断选科方向"):
            detect_selection_direction(students)

    def test_empty_list_raises(self):
        """空学生列表 → 抛 ValueError"""
        with pytest.raises(ValueError):
            detect_selection_direction([])

    def test_uses_first_student_only(self):
        """只检查第一个学生（走班场景设计如此）"""
        students = [
            Student("一班", "甲", {"物理": SubjectScore(95, 1, 3)}, "物化生"),
            Student("一班", "乙", {"历史": SubjectScore(80, 2, 5)}, "史政地"),
        ]
        # 第一个学生是物理，所以返回物理，无视第二个学生的历史
        assert detect_selection_direction(students) == "物理"


# =============================================================================
# run_statistics
# =============================================================================

class TestRunStatistics:
    """单班级各科单双上线统计"""

    @pytest.fixture
    def line_map(self) -> StreamingMap:
        m = StreamingMap()
        m.update({
            "物理总分_清北线": 600, "物理总分_985线": 550,
            "物理总分_211线": 500, "物理总分_特控线": 450,
            "物理语文_清北线": 130, "物理语文_985线": 120,
            "物理语文_211线": 110, "物理语文_特控线": 100,
            "物理英语_清北线": 130, "物理英语_985线": 120,
            "物理英语_211线": 110, "物理英语_特控线": 100,
            "物理数学_清北线": 140, "物理数学_985线": 130,
            "物理数学_211线": 120, "物理数学_特控线": 110,
        })
        return m

    @pytest.fixture
    def students(self):
        """3 名学生，总分/语文/数学/英语，总分 600/550/500"""
        return [
            Student("一班", "甲", {
                "总分": SubjectScore(600, 1, 2),
                "语文": SubjectScore(130, 1, 3),
                "数学": SubjectScore(142, 1, 2),
                "英语": SubjectScore(128, 1, 2),
            }, "物化生"),
            Student("一班", "乙", {
                "总分": SubjectScore(550, 2, 5),
                "语文": SubjectScore(120, 2, 5),
                "数学": SubjectScore(135, 2, 5),
                "英语": SubjectScore(118, 2, 6),
            }, "物化生"),
            Student("一班", "丙", {
                "总分": SubjectScore(500, 3, 8),
                "语文": SubjectScore(110, 3, 8),
                "数学": SubjectScore(125, 3, 8),
                "英语": SubjectScore(105, 3, 10),
            }, "物化生"),
        ]

    def test_total_count(self, students, line_map):
        """统计结果包含班级人数"""
        stats = run_statistics("一班", 3, students, line_map, "物理")
        assert stats.name == "一班"
        assert stats.count == 3

    def test_single_online(self, students, line_map):
        """总分清北线：甲(600)≥600，乙(550)<600，丙(500)<600 → 1人单上线"""
        stats = run_statistics("一班", 3, students, line_map, "物理")
        data = stats.get_statistics_data()
        # 甲 600 ≥ 清北线 600
        assert data["总分清北线"].single == 1

    def test_double_online(self, students, line_map):
        """语文学科双上线：总分也过线才计双上线"""
        stats = run_statistics("一班", 3, students, line_map, "物理")
        data = stats.get_statistics_data()
        # 甲: 语文 130 ≥ 物理语文_清北线 130, 总分 600 ≥ 物理总分_清北线 600 → 双上线
        assert data["语文清北线"].double == 1
        # 但 985线 不在 line_map 的物理分科键中... 等等，line_map 里有这些键

    def test_unsplit_direction(self, students):
        """direction='' 时，LineScore 键无前缀"""
        students[0].selection = ""
        line_map = StreamingMap()
        line_map.update({
            "总分_清北线": 600, "总分_985线": 550,
            "语文_清北线": 130, "语文_985线": 120,
        })
        stats = run_statistics("一班", 1, [students[0]], line_map, "")
        data = stats.get_statistics_data()
        assert data["总分清北线"].single == 1


# =============================================================================
# analysis (整合流程)
# =============================================================================

class TestAnalysis:
    """完整的班级统计流程"""

    @pytest.fixture
    def class_manager(self) -> ClassManager:
        mgr = ClassManager()
        mgr.add_student(Student("一班", "甲", {
            "总分": SubjectScore(600, 1, 2),
            "语文": SubjectScore(130, 1, 3),
            "物理": SubjectScore(95, 1, 5),
        }, "物化生"))
        mgr.add_student(Student("一班", "乙", {
            "总分": SubjectScore(500, 3, 8),
            "语文": SubjectScore(110, 3, 8),
            "物理": SubjectScore(80, 3, 12),
        }, "物化生"))
        mgr.add_student(Student("二班", "丙", {
            "总分": SubjectScore(550, 2, 5),
            "语文": SubjectScore(120, 2, 5),
            "物理": SubjectScore(88, 2, 8),
        }, "物化生"))
        return mgr

    @pytest.fixture
    def line_map(self) -> StreamingMap:
        m = StreamingMap()
        m.update({
            "物理总分_清北线": 600, "物理总分_985线": 550,
            "物理语文_清北线": 130, "物理语文_985线": 120,
        })
        return m

    def test_analysis_returns_tuple(self, class_manager, line_map):
        """analysis 返回 (statistics_list, direction)"""
        stats_list, direction = analysis(class_manager, line_map)
        assert isinstance(stats_list, list)
        assert direction == "物理"

    def test_analysis_two_classes(self, class_manager, line_map):
        """两个班级各有一条统计"""
        stats_list, direction = analysis(class_manager, line_map)
        assert len(stats_list) == 2

    def test_analysis_class_names(self, class_manager, line_map):
        """班级名称正确传递"""
        stats_list, _ = analysis(class_manager, line_map)
        names = [s.name for s in stats_list]
        assert "一班" in names
        assert "二班" in names

    def test_analysis_empty_raises(self, line_map):
        """空 ClassManager 抛 ValueError"""
        empty = ClassManager()
        with pytest.raises(ValueError, match="没有班级数据"):
            analysis(empty, line_map)
