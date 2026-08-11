"""core.onlineclass.actions 单元测试 —— 使用 fake page,不启动真实浏览器。"""
from __future__ import annotations

import pytest

from core.onlineclass.actions import ACTION_HANDLERS, _get_target, run_action

# 需求中标注为 P0 的六个动作
P0_ACTIONS = {"navigate", "click", "fill", "wait_for_selector", "get_text", "log"}


class FakeElement:
    """模拟 Playwright ElementHandle"""

    def __init__(self, name: str = "elem", text: str | None = None, attr: str | None = None):
        self.name = name
        self.text = text
        self.attr = attr
        self.calls: list = []

    def click(self, **kwargs):
        self.calls.append(("click", kwargs))
        return "clicked"

    def hover(self):
        self.calls.append(("hover",))
        return "hovered"

    def text_content(self):
        self.calls.append(("text_content",))
        return self.text

    def get_attribute(self, attribute):
        self.calls.append(("get_attribute", attribute))
        return self.attr

    def scroll_into_view_if_needed(self):
        self.calls.append(("scroll_into_view",))
        return "scrolled"


class FakeLocator:
    def __init__(self, selector: str):
        self.selector = selector

    def count(self):
        return 0

    def scroll_into_view_if_needed(self):
        return "scrolled"


class FakeKeyboard:
    def __init__(self, page: "FakePage"):
        self._page = page

    def press(self, key: str):
        self._page.calls.append(("keyboard.press", key))
        return None


class FakeMouse:
    def __init__(self, page: "FakePage"):
        self._page = page

    def wheel(self, dx: int, dy: int):
        self._page.calls.append(("mouse.wheel", dx, dy))
        return None


class FakeClock:
    """模拟 Playwright Clock:未安装时 fast_forward 抛异常"""

    def __init__(self, page: "FakePage"):
        self._page = page
        self.installed = False

    def install(self):
        self.installed = True
        self._page.calls.append(("clock.install",))

    def fast_forward(self, ms: int):
        if not self.installed:
            raise RuntimeError("Clock is not installed")
        self._page.calls.append(("clock.fast_forward", ms))
        return None


class FakePage:
    """记录调用并返回预设值的假 Page"""

    def __init__(self):
        self.calls: list = []
        self.url = "https://example.com/page"
        self._text = "页面文本"
        self._attr = "https://example.com/x"
        self._elements = [FakeElement(f"elem{i}") for i in range(2)]

    def goto(self, url):
        self.calls.append(("goto", url))
        return None

    def go_back(self):
        self.calls.append(("go_back",))
        return None

    def click(self, selector, **kwargs):
        self.calls.append(("click", selector, kwargs))
        return None

    def fill(self, selector, value):
        self.calls.append(("fill", selector, value))
        return None

    def wait_for_selector(self, selector, **kwargs):
        self.calls.append(("wait_for_selector", selector, kwargs))
        return None

    def text_content(self, selector):
        self.calls.append(("text_content", selector))
        return self._text

    def hover(self, selector):
        self.calls.append(("hover", selector))
        return None

    def wait_for_url(self, url, **kwargs):
        self.calls.append(("wait_for_url", url, kwargs))
        return None

    def get_attribute(self, selector, attribute):
        self.calls.append(("get_attribute", selector, attribute))
        return self._attr

    def query_selector_all(self, selector):
        self.calls.append(("query_selector_all", selector))
        return self._elements

    def select_option(self, selector, value):
        self.calls.append(("select_option", selector, value))
        return ["selected"]

    def locator(self, selector):
        self.calls.append(("locator", selector))
        return FakeLocator(selector)

    def evaluate(self, script):
        self.calls.append(("evaluate", script))
        return {"ok": True}

    @property
    def keyboard(self):
        return FakeKeyboard(self)

    @property
    def mouse(self):
        return FakeMouse(self)

    @property
    def clock(self):
        if not hasattr(self, "_clock"):
            self._clock = FakeClock(self)
        return self._clock

    def screenshot(self, **kwargs):
        self.calls.append(("screenshot", kwargs))
        return b"png-data"


@pytest.fixture
def page() -> FakePage:
    return FakePage()


# ── P0 回归 ────────────────────────────────────────────────────────────
def test_navigate(page):
    run_action("navigate", page, {}, {"url": "https://a.example"})
    assert page.calls == [("goto", "https://a.example")]


def test_navigate_back(page):
    run_action("navigate_back", page, {}, {})
    assert page.calls == [("go_back",)]


def test_click_selector(page):
    run_action("click", page, {}, {"selector": "#btn"})
    assert page.calls == [("click", "#btn", {})]


def test_click_force(page):
    run_action("click_force", page, {}, {"selector": "#btn"})
    assert page.calls == [("click", "#btn", {"force": True})]


def test_fill(page):
    run_action("fill", page, {}, {"selector": "#name", "value": "张三"})
    assert page.calls == [("fill", "#name", "张三")]


def test_fill_redacts_sensitive_selector(page, caplog):
    """敏感选择器(密码/验证码等)填入时日志打码,真实值仍传入 page.fill"""
    from loguru import logger as _logger

    handler_id = _logger.add(caplog.handler, format="{message}", level="INFO")
    try:
        run_action("fill", page, {}, {"selector": "#password", "value": "hunter2"})
    finally:
        _logger.remove(handler_id)
    assert "****" in caplog.text
    assert "hunter2" not in caplog.text
    assert page.calls == [("fill", "#password", "hunter2")]


def test_fill_redacts_value_match(page, caplog):
    """值等于 context 中已保存的密码/验证码时日志打码(即使选择器不敏感)"""
    from loguru import logger as _logger

    ctx = {"password": "secret123"}
    handler_id = _logger.add(caplog.handler, format="{message}", level="INFO")
    try:
        run_action("fill", page, ctx, {"selector": "#generic-input", "value": "secret123"})
    finally:
        _logger.remove(handler_id)
    assert "****" in caplog.text
    assert "secret123" not in caplog.text
    assert page.calls == [("fill", "#generic-input", "secret123")]


def test_fill_default_value(page):
    run_action("fill", page, {}, {"selector": "#name"})
    assert page.calls == [("fill", "#name", "")]


def test_wait_for_selector_defaults(page):
    run_action("wait_for_selector", page, {}, {"selector": ".box"})
    assert page.calls == [("wait_for_selector", ".box", {"state": "visible"})]


def test_wait_for_selector_timeout(page):
    run_action("wait_for_selector", page, {}, {"selector": ".box", "state": "hidden", "timeout": 3000})
    assert page.calls == [("wait_for_selector", ".box", {"state": "hidden", "timeout": 3000})]


def test_get_text_save_to_context(page):
    ctx: dict = {}
    result = run_action("get_text", page, ctx, {"selector": "#t", "save_as": "title"})
    assert result == "页面文本"
    assert ctx["title"] == "页面文本"


def test_get_url_save_to_context(page):
    ctx: dict = {}
    result = run_action("get_url", page, ctx, {"save_as": "current_url"})
    assert result == "https://example.com/page"
    assert ctx["current_url"] == "https://example.com/page"


def test_get_url_without_save_as(page):
    result = run_action("get_url", page, {}, {})
    assert result == "https://example.com/page"


def test_count_elements(page):
    ctx: dict = {}
    result = run_action("count_elements", page, ctx, {"selector": ".item", "save_as": "n"})
    assert result == 0
    assert ctx["n"] == 0


def test_log_returns_message():
    assert run_action("log", None, {}, {"message": "hi"}) == "hi"


def test_set_var_boolean():
    ctx: dict = {}
    run_action("set_var", None, ctx, {"name": "needs_login", "value": True})
    assert ctx["needs_login"] is True


def test_set_var_number_and_string():
    ctx: dict = {}
    run_action("set_var", None, ctx, {"name": "retry_count", "value": 3})
    run_action("set_var", None, ctx, {"name": "course_name", "value": "高等数学"})
    assert ctx["retry_count"] == 3
    assert ctx["course_name"] == "高等数学"


def test_set_var_with_placeholder():
    """value 支持 ${变量} 引用(引擎在步骤执行前完成替换)"""
    ctx: dict = {}
    run_action("set_var", None, ctx, {"name": "base", "value": "${username}"})
    assert ctx["base"] == "${username}"  # 未定义时保留原文;替换逻辑在引擎 _replace_vars


def test_sleep_zero_is_noop():
    assert run_action("sleep", None, {}, {"ms": 0}) is None


def test_sleep_seconds(monkeypatch):
    slept = []
    monkeypatch.setattr("time.sleep", lambda s: slept.append(s))
    run_action("sleep", None, {}, {"seconds": 2.5})
    assert slept == [2.5]  # 秒直接换算后调用 time.sleep


def test_sleep_seconds_precedence(monkeypatch):
    slept = []
    monkeypatch.setattr("time.sleep", lambda s: slept.append(s))
    run_action("sleep", None, {}, {"seconds": 1, "ms": 500})
    assert slept == [1.0]  # 同时给出时 seconds 优先


# ── 注册表 ─────────────────────────────────────────────────────────────
def test_p0_actions_registered():
    assert P0_ACTIONS <= set(ACTION_HANDLERS)


def test_log():
    run_action("log", None, {}, {"message": "hello"})  # 不抛异常即可


# ── P1 动作 ────────────────────────────────────────────────────────────
def test_select_option(page):
    run_action("select_option", page, {}, {"selector": "#cat", "value": "cs"})
    assert page.calls == [("select_option", "#cat", "cs")]


def test_select_option_missing_value(page):
    with pytest.raises(ValueError):
        run_action("select_option", page, {}, {"selector": "#cat"})


def test_hover(page):
    run_action("hover", page, {}, {"selector": ".menu"})
    assert page.calls == [("hover", ".menu")]


def test_wait_for_url(page):
    run_action("wait_for_url", page, {}, {"url": "**/my/index", "timeout": 5000})
    assert page.calls == [("wait_for_url", "**/my/index", {"timeout": 5000})]


def test_get_attribute_save_to_context(page):
    ctx: dict = {}
    result = run_action("get_attribute", page, ctx, {"selector": "a", "attribute": "href", "save_as": "link"})
    assert result == "https://example.com/x"
    assert ctx["link"] == "https://example.com/x"


def test_get_list_save_to_context(page):
    ctx: dict = {}
    result = run_action("get_list", page, ctx, {"selector": ".course-item", "save_as": "courses"})
    assert len(result) == 2
    assert ctx["courses"] is result


# ── P2/P3 动作 ─────────────────────────────────────────────────────────
def test_scroll_to_selector(page):
    run_action("scroll", page, {}, {"selector": "#video"})
    assert page.calls == [("locator", "#video")]


def test_scroll_wheel(page):
    run_action("scroll", page, {}, {"dx": 0, "dy": 800})
    assert page.calls == [("mouse.wheel", 0, 800)]


def test_execute_script(page):
    result = run_action("execute_script", page, {}, {"script": "window.scrollTo(0, 9999)"})
    assert page.calls == [("evaluate", "window.scrollTo(0, 9999)")]
    assert result == {"ok": True}


def test_press(page):
    run_action("press", page, {}, {"key": "Enter"})
    assert page.calls == [("keyboard.press", "Enter")]


def test_fast_forward_lazy_install(page):
    # 时钟未安装:懒安装后快进
    run_action("fast_forward", page, {}, {"ms": 30000})
    assert page.calls == [("clock.install",), ("clock.fast_forward", 30000)]
    # 已安装:直接快进
    run_action("fast_forward", page, {}, {"ms": 1000})
    assert page.calls[-1] == ("clock.fast_forward", 1000)


def test_screenshot_absolute_path(page, tmp_path):
    dest = tmp_path / "shots" / "evidence.png"
    run_action("screenshot", page, {}, {"path": str(dest), "full_page": True})
    assert page.calls == [("screenshot", {"path": str(dest), "full_page": True})]
    assert dest.parent.exists()


def test_screenshot_missing_path(page):
    with pytest.raises(KeyError):
        run_action("screenshot", page, {}, {})


# ── on 字段元素操作 ────────────────────────────────────────────────────
def test_click_on_element(page):
    elem = FakeElement("course", attr="https://c/1")
    result = run_action("click", page, {}, {"on": elem})
    assert result == "clicked"
    assert elem.calls == [("click", {})]
    assert page.calls == []  # 元素模式不触达 page


def test_get_text_on_element(page):
    ctx: dict = {}
    elem = FakeElement("course", text="高等数学")
    run_action("get_text", page, ctx, {"on": elem, "save_as": "name"})
    assert ctx["name"] == "高等数学"
    assert elem.calls == [("text_content",)]


def test_get_target_true_key_compat():
    """YAML 1.1 裸 on: 被解析为布尔 True 键,应兼容"""
    assert _get_target({True: "${course}"}) == "${course}"
    assert _get_target({"on": "X", True: "Y"}) == "X"  # 显式 on 优先


# ── 错误处理 ───────────────────────────────────────────────────────────
def test_unknown_action(page):
    with pytest.raises(ValueError, match="未知的 action"):
        run_action("unknown_action", page, {}, {})


def test_get_text_missing_save_as(page):
    with pytest.raises(ValueError, match="save_as"):
        run_action("get_text", page, {}, {"selector": "#t"})
