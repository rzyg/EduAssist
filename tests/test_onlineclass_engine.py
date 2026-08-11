"""core.onlineclass.engine 单元测试 —— 变量替换/条件/循环/分支(fake page)。"""
from __future__ import annotations

import sys

import pytest
import yaml

from core.onlineclass.actions import ACTION_HANDLERS
from core.onlineclass.engine import CourseEngine

SAMPLE_YAML = """\
global:
  retry: 1
env:
  base_url: "https://example.com"
  greeting: "你好"

check_login:
  - action: log
    message: "start ${base_url}"
"""


@pytest.fixture
def engine(tmp_path):
    """真实加载一个临时 YAML 配置的引擎"""
    cfg = tmp_path / "engine.yaml"
    cfg.write_text(SAMPLE_YAML, encoding="utf-8")
    return CourseEngine(cfg)


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch):
    """打桩 time.sleep,避免重试/循环中的真实等待拖慢测试"""
    monkeypatch.setattr("time.sleep", lambda *a, **k: None)


def make_engine(context=None, env=None, retry=0) -> CourseEngine:
    """绕过 __init__(不读文件),直接构造带初始状态的引擎"""
    e = CourseEngine.__new__(CourseEngine)
    e.context = dict(context or {})
    e._env_source = dict(env or {})
    e._iterations = {}
    e.retry = retry
    e._stop_check = None
    e._captcha_request = None
    return e


class FakeLocator:
    def __init__(self, count: int):
        self._count = count

    def count(self) -> int:
        return self._count


class FakePage:
    """按预设序列返回 count,并记录 click 次数"""

    def __init__(self, next_counts=None):
        self._next = iter(next_counts or [])
        self.clicks = 0

    def locator(self, selector):
        return FakeLocator(next(self._next, 0))

    def click(self, selector):
        self.clicks += 1


# ── 初始化 ─────────────────────────────────────────────────────────────
def test_init_loads_config(engine):
    assert engine.retry == 1
    assert engine.context == {}
    assert engine._env_source["base_url"] == "https://example.com"
    assert "check_login" in engine.config


# ── 变量替换 ───────────────────────────────────────────────────────────
def test_replace_vars_recursive():
    e = make_engine(context={"name": "张三"}, env={"base": "https://x"})
    value = {"message": "hi ${name} @ ${base}", "items": ["${name}"], "nested": {"k": "${base}/a"}}
    replaced = e._replace_vars(value)
    assert replaced["message"] == "hi 张三 @ https://x"
    assert replaced["items"] == ["张三"]
    assert replaced["nested"]["k"] == "https://x/a"


def test_replace_vars_context_precedence():
    e = make_engine(context={"v": "ctx"}, env={"v": "env"})
    assert e._replace_vars("${v}") == "ctx"


def test_replace_vars_undefined_keeps_placeholder():
    e = make_engine()
    assert e._replace_vars("${undefined_var}") == "${undefined_var}"


def test_resolve_var_nested():
    e = make_engine(context={"user": {"name": "张三"}})
    assert e._resolve_var("user.name") == "张三"


# ── 条件求值 ───────────────────────────────────────────────────────────
def test_compare_values_type_fallback():
    # str 与 int 混比不抛异常,统一转字符串比较
    assert CourseEngine._compare_values("5", 10, ">") is True  # "5" > "10"(字典序)
    assert CourseEngine._compare_values(10, "5", ">") is False
    assert CourseEngine._compare_values(5, "5", "==") is False


@pytest.mark.parametrize(
    "expr,want",
    [
        ("n >= 5", True),
        ("n > 5", False),
        ("n < 6", True),
        ("n <= 4", False),
        ("n == 5", True),
        ("n != 5", False),
        ("n == '5'", False),  # 引号内的字符串不参与数值比较
        ("n == 5.0", True),
    ],
)
def test_eval_condition_comparisons(expr, want):
    e = make_engine(context={"n": 5})
    assert e._eval_condition(expr) is want


def test_eval_condition_truthy_and_negation():
    e = make_engine(context={"flag": True, "off": False})
    assert e._eval_condition("flag")
    assert not e._eval_condition("off")
    assert e._eval_condition("!off")
    assert not e._eval_condition("!flag")
    assert e._eval_condition(None)  # 无条件视为真


# ── while 循环(do-while) ───────────────────────────────────────────────
def test_while_loop_do_while():
    page = FakePage([1, 0])  # 第一轮 has_next=1,第二轮 0
    e = make_engine()
    e._execute_loop(page, {
        "while": {"key": "learning", "max_iterations": 10, "condition": "has_next"},
        "steps": [
            {"action": "count_elements", "selector": ".next", "save_as": "has_next"},
            {"action": "click", "selector": ".next", "when": "has_next"},
        ],
    })
    assert e.context["learning_iteration"] == 2  # 第一轮无条件执行
    assert page.clicks == 1  # 最后一轮 has_next=0,when 跳过 click


def test_while_loop_max_iterations():
    page = FakePage([1, 1, 1, 1, 1])  # 永远有下一页
    e = make_engine()
    e._execute_loop(page, {
        "while": {"key": "k", "max_iterations": 3, "condition": "has_next"},
        "steps": [{"action": "count_elements", "selector": ".next", "save_as": "has_next"}],
    })
    assert e.context["k_iteration"] == 3  # 恰好执行 3 次


def test_loop_no_condition_still_bounded():
    e = make_engine()
    e._execute_loop(FakePage([]), {"while": {"key": "l", "max_iterations": 2}, "steps": []})
    assert e.context["l_iteration"] == 2


def test_nested_while_contains_foreach(monkeypatch):
    """while 内嵌 for_each:内层 var 延迟解析(不预替换)"""
    seen = []
    monkeypatch.setitem(ACTION_HANDLERS, "mark", lambda p, c, s: seen.append(s["message"]))
    e = make_engine()
    e._execute_loop(None, {
        "while": {"key": "outer", "max_iterations": 2},
        "steps": [
            {"for_each": {"items": ["a", "b"], "var": "it"},
             "steps": [{"action": "mark", "message": "${it}"}]},
        ],
    })
    assert seen == ["a", "b", "a", "b"]


def test_nested_foreach_contains_while(monkeypatch):
    """for_each 内嵌 while:每个元素内层循环 2 轮"""
    seen = []
    monkeypatch.setitem(ACTION_HANDLERS, "mark", lambda p, c, s: seen.append(s["message"]))
    e = make_engine()
    e._execute_foreach(None, {
        "for_each": {"items": ["x", "y"], "var": "it"},
        "steps": [
            {"while": {"key": "inner", "max_iterations": 2},
             "steps": [{"action": "mark", "message": "${it}"}]},
        ],
    })
    assert seen == ["x", "x", "y", "y"]


def test_nested_while_contains_while(monkeypatch):
    """while 内嵌 while:内层可引用外层迭代计数 ${o_iteration}"""
    seen = []
    monkeypatch.setitem(ACTION_HANDLERS, "mark", lambda p, c, s: seen.append(s["message"]))
    e = make_engine()
    e._execute_loop(None, {
        "while": {"key": "o", "max_iterations": 2},
        "steps": [
            {"while": {"key": "i", "max_iterations": 2},
             "steps": [{"action": "mark", "message": "${o_iteration}-${i_iteration}"}]},
        ],
    })
    assert seen == ["1-1", "1-2", "2-1", "2-2"]


def test_loop_wait_between(monkeypatch):
    sleeps = {"n": 0}
    monkeypatch.setattr("time.sleep", lambda s: sleeps.__setitem__("n", sleeps["n"] + 1))
    e = make_engine()
    e._execute_loop(FakePage([]), {"while": {"key": "w", "max_iterations": 2, "wait_between": 1}, "steps": []})
    assert sleeps["n"] == 2


# ── for_each 循环 ──────────────────────────────────────────────────────
def test_foreach_inject_and_cleanup(monkeypatch):
    seen = []

    def probe(page, context, step):
        seen.append(step.get("on"))
        return step.get("on")

    monkeypatch.setitem(ACTION_HANDLERS, "probe", probe)
    e = make_engine(context={"course_list": ["c1", "c2"]})
    e._execute_foreach(None, {
        "for_each": {"items": "${course_list}", "var": "course", "key": "fc"},
        "steps": [{"action": "probe", "on": "${course}", "save_as": "x"}],
    })
    assert seen == ["c1", "c2"]  # on 注入为逐项元素对象
    assert e.context["fc_iteration"] == 2
    assert "course" not in e.context  # 循环变量已清理


def test_foreach_max_iterations(monkeypatch):
    seen = []
    monkeypatch.setitem(ACTION_HANDLERS, "probe", lambda p, c, s: seen.append(s.get("on")))
    e = make_engine(context={"items": [1, 2, 3, 4, 5]})
    e._execute_foreach(None, {
        "for_each": {"items": "${items}", "var": "it", "max_iterations": 2},
        "steps": [{"action": "probe", "on": "${it}"}],
    })
    assert seen == [1, 2]


def test_foreach_items_not_list():
    e = make_engine(context={"x": "not-a-list"})
    with pytest.raises(ValueError, match="必须解析为列表"):
        e._execute_foreach(None, {"for_each": {"items": "${x}"}, "steps": []})


# ── if/else 分支 ───────────────────────────────────────────────────────
def test_if_then_branch(monkeypatch):
    trace = []
    monkeypatch.setitem(ACTION_HANDLERS, "mark", lambda p, c, s: trace.append(s["message"]))
    e = make_engine(context={"logged_in": True})
    e._execute_step(None, {"action": "if", "condition": "logged_in",
                           "then": [{"action": "mark", "message": "T"}],
                           "else": [{"action": "mark", "message": "F"}]})
    assert trace == ["T"]


def test_if_else_branch(monkeypatch):
    trace = []
    monkeypatch.setitem(ACTION_HANDLERS, "mark", lambda p, c, s: trace.append(s["message"]))
    e = make_engine(context={"logged_in": False})
    e._execute_step(None, {"action": "if", "condition": "logged_in",
                           "then": [{"action": "mark", "message": "T"}],
                           "else": [{"action": "mark", "message": "F"}]})
    assert trace == ["F"]


def test_if_with_comparison_condition(monkeypatch):
    trace = []
    monkeypatch.setitem(ACTION_HANDLERS, "mark", lambda p, c, s: trace.append(s["message"]))
    e = make_engine(context={"attempts": 3})
    e._execute_step(None, {"action": "if", "condition": "attempts >= 3",
                           "then": [{"action": "mark", "message": "max"}]})
    assert trace == ["max"]


def test_if_branch_steps_resolve_vars_at_execution(monkeypatch):
    """if 的 then/else 子步骤不应在 if 入口预替换:
    分支内 execute_script 更新变量后, log 应显示新值而非 if 入口时的旧值"""
    trace = []
    monkeypatch.setitem(ACTION_HANDLERS, "execute_script", lambda p, c, s: 850)
    monkeypatch.setitem(ACTION_HANDLERS, "log", lambda p, c, s: trace.append(s["message"]))
    e = make_engine(context={"video_count": 1, "remaining_seconds": 13})
    e._execute_step(None, {
        "action": "if",
        "condition": "video_count > 0",
        "then": [
            {"action": "execute_script", "script": "x", "save_as": "remaining_seconds"},
            {"action": "log", "message": "当前剩余秒数: ${remaining_seconds}"},
        ],
    })
    assert trace == ["当前剩余秒数: 850"], trace  # 修复前会打印 13


def test_if_condition_env_var_replaced(monkeypatch):
    """condition 中引用 env 变量(${base_url})仍应正常替换后再求值"""
    trace = []
    monkeypatch.setitem(ACTION_HANDLERS, "log", lambda p, c, s: trace.append(s["message"]))
    e = make_engine(context={"current_url": "https://x/login"}, env={"base_url": "https://x"})
    e._execute_step(None, {
        "action": "if",
        "condition": "current_url != '${base_url}/login'",
        "then": [{"action": "log", "message": "T"}],
        "else": [{"action": "log", "message": "F"}],
    })
    assert trace == ["F"]  # current_url == base_url/login,走 else


def test_if_skipped_by_when(monkeypatch):
    trace = []
    monkeypatch.setitem(ACTION_HANDLERS, "mark", lambda p, c, s: trace.append(s["message"]))
    e = make_engine(context={"logged_in": True})
    result = e._execute_step(None, {"action": "if", "when": "!logged_in", "condition": "logged_in",
                                    "then": [{"action": "mark", "message": "T"}]})
    assert result is None
    assert trace == []


# ── when 条件跳过 ──────────────────────────────────────────────────────
def test_when_skip_step(monkeypatch):
    trace = []
    monkeypatch.setitem(ACTION_HANDLERS, "mark", lambda p, c, s: trace.append(s["message"]))
    e = make_engine(context={"ok": False})
    e._execute_step(None, {"action": "mark", "message": "x", "when": "ok"})
    assert trace == []


def test_execute_step_replaces_vars(engine):
    assert engine._execute_step(None, {"action": "log", "message": "hi ${greeting}"}) == "hi 你好"


def test_execute_step_unknown_action(engine):
    with pytest.raises(ValueError, match="未知的 action"):
        engine._execute_step(None, {"action": "no_such"})


def test_save_context(engine):
    engine._save_context({"save_as": "k"}, "v")
    assert engine.context["k"] == "v"
    engine._save_context({"save_as": "k2"}, None)  # None 不写入
    assert "k2" not in engine.context


# ── 重试机制 ───────────────────────────────────────────────────────────
def test_retry_then_succeed(monkeypatch):
    attempts = {"n": 0}

    def flaky(page, context, step):
        attempts["n"] += 1
        if attempts["n"] < 2:
            raise RuntimeError("boom")
        return "ok"

    monkeypatch.setitem(ACTION_HANDLERS, "flaky", flaky)
    e = make_engine(retry=1)
    result = e._execute_step(None, {"action": "flaky"})
    assert result == "ok"
    assert attempts["n"] == 2


def test_retry_exhausted_raises(monkeypatch):
    def always_fail(page, context, step):
        raise RuntimeError("boom")

    monkeypatch.setitem(ACTION_HANDLERS, "boom", always_fail)
    e = make_engine(retry=0)
    with pytest.raises(RuntimeError):
        e._execute_step(None, {"action": "boom"})


# ── 主入口 run ─────────────────────────────────────────────────────────
def test_request_captcha_instruction(monkeypatch):
    """request_captcha 指令:提取图片(整页截图→data URL)、经回调取文本、注入 context"""
    class _FakePage:
        def __init__(self):
            self.shots = []

        def screenshot(self, **kwargs):
            self.shots.append(kwargs)
            return b"PNG-DATA"

    received = {}

    def captcha_cb(image):
        received["image"] = image
        return "ABC12"

    e = make_engine()
    e._captcha_request = captcha_cb
    page = _FakePage()
    result = e._execute_step(page, {"action": "request_captcha"})
    assert result == "ABC12"
    assert e.context["captcha"] == "ABC12"  # 验证码注入上下文,供 ${captcha} 引用
    assert received["image"].startswith("data:image/png;base64,")


def test_request_captcha_without_callback():
    e = make_engine()
    with pytest.raises(ValueError, match="未启用验证码回调"):
        e._execute_step(None, {"action": "request_captcha"})


def test_call_section_invokes_other_section(monkeypatch, tmp_path):
    """call_section: 一个板块内调用另一个板块(login 后重新调用 check_login)"""
    cfg = tmp_path / "c.yaml"
    cfg.write_text(yaml.safe_dump({
        "global": {"retry": 0},
        "check_login": [{"action": "mark", "message": "check_login"}],
        "login": [
            {"action": "mark", "message": "login"},
            {"action": "call_section", "section": "check_login"},
            {"action": "mark", "message": "login_done"},
        ],
    }, allow_unicode=True), encoding="utf-8")
    trace = []
    monkeypatch.setitem(ACTION_HANDLERS, "mark", lambda p, c, s: trace.append(s["message"]))
    engine = CourseEngine(cfg)
    engine.run(page="fake", close_browser=False)
    assert trace == ["check_login", "login", "check_login", "login_done"]


def test_call_section_missing_raises(monkeypatch, tmp_path):
    cfg = tmp_path / "c.yaml"
    cfg.write_text(yaml.safe_dump({
        "global": {"retry": 0},
        "a": [{"action": "call_section", "section": "no_such"}],
    }, allow_unicode=True), encoding="utf-8")
    engine = CourseEngine(cfg)
    with pytest.raises(ValueError, match="不存在"):
        engine.run(page="fake", close_browser=False)


@pytest.mark.skipif(sys.platform != "win32", reason="仅 Windows 事件循环策略相关")
def test_ensure_proactor_policy_switches():
    """uvicorn 的 Selector 策略不支持子进程,应被切换为 Proactor 并返回原策略"""
    import asyncio

    from core.onlineclass.engine import _ensure_proactor_policy

    original = asyncio.get_event_loop_policy()
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        prev = _ensure_proactor_policy()
        assert prev is not None
        assert isinstance(
            asyncio.get_event_loop_policy(), asyncio.WindowsProactorEventLoopPolicy
        )
        # 幂等:再次调用时已可用,返回 None
        assert _ensure_proactor_policy() is None
    finally:
        asyncio.set_event_loop_policy(original)


def test_dispatch_section_runs_steps(engine):
    engine.retry = 0
    engine._dispatch_section(None, "check_login", {"steps": [{"action": "log", "message": "hello"}]})


def test_execute_step_expands_nested_steps(engine, monkeypatch):
    """步骤列表中出现 {'steps': [...]} 嵌套板块时递归展开执行(用户报错场景)"""
    trace = []
    monkeypatch.setitem(ACTION_HANDLERS, "mark", lambda p, c, s: trace.append(s["message"]))
    engine.retry = 0
    engine._execute_section(None, [
        {"steps": [{"action": "mark", "message": "a"}]},   # 嵌套板块
        {"action": "mark", "message": "b"},                # 普通步骤
    ])
    assert trace == ["a", "b"]


def test_execute_step_missing_action_raises(engine):
    """既无 action 也无 steps 的字典仍应报错"""
    engine.retry = 0
    with pytest.raises(ValueError, match="缺少 action"):
        engine._execute_step(None, {"foo": 1})


def test_dispatch_section_invalid(engine):
    with pytest.raises(ValueError, match="无法识别"):
        engine._dispatch_section(None, "bad", {"foo": 1})


def test_run_executes_sections_in_order(tmp_path, monkeypatch):
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text(yaml.safe_dump({
        "global": {"retry": 0},
        "env": {"u": "x"},
        "sec1": [{"action": "log", "message": "a"}],
        "sec2": {"steps": [{"action": "log", "message": "b"}]},
    }, allow_unicode=True), encoding="utf-8")
    trace = []
    monkeypatch.setitem(ACTION_HANDLERS, "log", lambda p, c, s: trace.append(s["message"]))
    engine = CourseEngine(cfg)
    engine.run(page="fake", close_browser=False)
    assert trace == ["a", "b"]
