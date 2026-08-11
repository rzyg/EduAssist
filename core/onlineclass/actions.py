"""配置驱动的核心动作实现。

每个动作函数签名统一为: ``fn(page, context, step) -> Any``
- ``page``    : Playwright 的 Page 对象
- ``context`` : 执行过程中的全局上下文(dict),用于步骤间传值(get_text 通过 save_as 写入)
- ``step``    : 已做变量替换后的 step(dict),含 action / selector / value / save_as 等字段

这里不直接依赖 Page 的实例化方式,便于单独测试与替换浏览器对象。
"""
from __future__ import annotations

from typing import Any

from loguru import logger


def _get_target(step: dict) -> Any:
    """解析操作目标:优先 ``on`` 字段(元素对象或选择器),否则 ``selector``。

    ``on`` 由 for_each 循环注入,取值为 ElementHandle 或字符串选择器;
    动作函数据此决定调用元素自身方法还是 page 方法。
    兼容 YAML 1.1 陷阱:裸 ``on:`` 会被 safe_load 解析为布尔 ``True`` 键。
    """
    if "on" in step:
        return step["on"]
    if True in step:
        return step[True]
    return step["selector"]


def navigate(page: Any, context: dict, step: dict) -> Any:
    """导航到目标 URL。参数: url"""
    url = step["url"]
    logger.info(f"navigate -> {url}")
    return page.goto(url)


def navigate_back(page: Any, context: dict, step: dict) -> Any:
    logger.info("navigate_back")
    return page.go_back()


def click(page: Any, context: dict, step: dict) -> Any:
    """点击元素。参数: selector 或 on"""
    target = _get_target(step)
    if hasattr(target, "click"):
        logger.info(f"click(element) -> {target}")
        return target.click()
    logger.info(f"click -> {target}")
    return page.click(target)


def click_force(page: Any, context: dict, step: dict) -> Any:
    """强制点击,忽略阻挡/不可见。参数: selector 或 on"""
    target = _get_target(step)
    if hasattr(target, "click"):
        logger.info(f"click(force, element) -> {target}")
        return target.click(force=True)
    logger.info(f"click(force) -> {target}")
    return page.click(target, force=True)


# 敏感输入的选择器关键字:匹配时日志打码,避免密码/验证码明文落盘
_SENSITIVE_HINTS = ("password", "passwd", "pwd", "captcha", "密码", "验证码")


def fill(page: Any, context: dict, step: dict) -> Any:
    """向输入框填入内容。参数: selector, value"""
    selector = step["selector"]
    value = step.get("value", "")
    # 打码条件: 选择器含敏感关键字, 或填入的值恰为已保存的密码/验证码
    sensitive_selector = any(hint in selector.lower() for hint in _SENSITIVE_HINTS)
    sensitive_value = value in (context.get("password"), context.get("captcha"))
    if sensitive_selector or sensitive_value:
        logger.info(f"fill -> {selector} = ****")
    else:
        logger.info(f"fill -> {selector} = {value!r}")
    return page.fill(selector, value)


def wait_for_selector(page: Any, context: dict, step: dict) -> Any:
    """等待元素出现,支持 state / timeout。参数: selector, state?, timeout?"""
    selector = step["selector"]
    state = step.get("state", "visible")
    timeout = step.get("timeout")
    kwargs: dict[str, Any] = {"state": state}
    if timeout is not None:
        kwargs["timeout"] = timeout
    logger.info(f"wait_for_selector -> {selector} (state={state})")
    return page.wait_for_selector(selector, **kwargs)


def get_text(page: Any, context: dict, step: dict) -> Any:
    """读取元素文本并写入 context。参数: selector 或 on, save_as(必填)"""
    target = _get_target(step)
    save_as = step.get("save_as")
    if not save_as:
        raise ValueError(f"get_text 动作缺少 save_as 字段 (target={target!r})")
    if hasattr(target, "text_content"):
        text = target.text_content()
    else:
        text = page.text_content(target)
    context[save_as] = text
    logger.info(f"get_text -> {target} = {text!r} (context['{save_as}'])")
    return text


def get_url(page: Any, context: dict, step: dict) -> Any:
    """获取当前页面 URL 并写入 context。参数: save_as?"""
    url = page.url
    save_as = step.get("save_as")
    if save_as:
        context[save_as] = url
    logger.info(f"get_url -> {url}" + (f" (context['{save_as}'])" if save_as else ""))
    return url


def count_elements(page: Any, context: dict, step: dict) -> Any:
    """统计元素个数并写入 context。参数: selector, save_as(必填)"""
    selector = step["selector"]
    save_as = step.get("save_as")
    if not save_as:
        raise ValueError(f"count_elements 动作缺少 save_as 字段 (selector={selector!r})")
    count = page.locator(selector).count()
    context[save_as] = count
    logger.info(f"count_elements -> {selector} = {count} (context['{save_as}'])")
    return count


def select_option(page: Any, context: dict, step: dict) -> Any:
    """选择下拉框选项。参数: selector, value(或 values 列表)"""
    selector = step["selector"]
    value = step.get("value", step.get("values"))
    if value is None:
        raise ValueError(f"select_option 缺少 value 字段 (selector={selector!r})")
    logger.info(f"select_option -> {selector} = {value!r}")
    return page.select_option(selector, value)


def hover(page: Any, context: dict, step: dict) -> Any:
    """鼠标悬停,触发下拉菜单/提示。参数: selector 或 on"""
    target = _get_target(step)
    if hasattr(target, "hover"):
        logger.info(f"hover(element) -> {target}")
        return target.hover()
    logger.info(f"hover -> {target}")
    return page.hover(target)


def wait_for_url(page: Any, context: dict, step: dict) -> Any:
    """等待页面跳转完成,url 支持 glob 模式。参数: url, timeout?"""
    url = step["url"]
    timeout = step.get("timeout")
    kwargs: dict[str, Any] = {}
    if timeout is not None:
        kwargs["timeout"] = timeout
    logger.info(f"wait_for_url -> {url}")
    return page.wait_for_url(url, **kwargs)


def get_attribute(page: Any, context: dict, step: dict) -> Any:
    """读取元素属性(href/src 等)并写入 context。参数: selector 或 on, attribute, save_as?"""
    attribute = step["attribute"]
    target = _get_target(step)
    if hasattr(target, "get_attribute"):
        value = target.get_attribute(attribute)
    else:
        value = page.get_attribute(target, attribute)
    save_as = step.get("save_as")
    if save_as:
        context[save_as] = value
    logger.info(f"get_attribute -> {target} [{attribute}] = {value!r} (context['{save_as}'])" if save_as
                else f"get_attribute -> {target} [{attribute}] = {value!r}")
    return value


def get_list(page: Any, context: dict, step: dict) -> Any:
    """获取匹配元素的列表(ElementHandle),作为 for_each 的数据源。参数: selector, save_as?"""
    selector = step["selector"]
    elements = page.query_selector_all(selector)
    save_as = step.get("save_as")
    if save_as:
        context[save_as] = elements
    logger.info(f"get_list -> {selector} = {len(elements)} 个元素 (context['{save_as}'])" if save_as
                else f"get_list -> {selector} = {len(elements)} 个元素")
    return elements


def log(page: Any, context: dict, step: dict) -> Any:
    """输出日志。参数: message (可含 ${变量})"""
    message = step.get("message", "")
    logger.info(message)
    return message


def set_var(page: Any, context: dict, step: dict) -> Any:
    """给 context 变量赋值,供后续 when / if / ${变量} 引用。参数: name, value

    ``value`` 支持布尔 / 数字 / 字符串,也支持 ``${变量}`` 引用;
    赋值后可在条件表达式(when / if / while.condition)中直接判断,
    例如 ``when: "needs_login"``、``condition: "!needs_login"``。
    """
    name = step["name"]
    value = step.get("value")
    context[name] = value
    logger.info(f"set_var -> context['{name}'] = {value!r}")
    return value


def sleep(page: Any, context: dict, step: dict) -> Any:
    """等待指定时长(步骤级手动暂停)。参数二选一:
    - ``ms``: 毫秒(默认 0)
    - ``seconds``: 秒(更直观,如 ``seconds: 2`` 暂停 2 秒)
    ``seconds`` 优先于 ``ms``(同时给出时以 seconds 为准)。
    """
    import time

    seconds = float(step.get("seconds", 0) or 0)
    ms = int(step.get("ms", 0))
    if seconds > 0:
        ms = int(seconds * 1000)
    if ms > 0:
        logger.info(f"sleep -> {ms}ms")
        time.sleep(ms / 1000.0)
    return None


def scroll(page: Any, context: dict, step: dict) -> Any:
    """滚动页面或元素。二选一:
    - selector / on: 滚动到元素可见(scroll_into_view_if_needed)
    - dx / dy: 鼠标滚轮增量(page.mouse.wheel),默认 (0, 0)
    """
    if "selector" in step or "on" in step:
        target = _get_target(step)
        if hasattr(target, "scroll_into_view_if_needed"):
            logger.info(f"scroll(element) -> {target}")
            return target.scroll_into_view_if_needed()
        logger.info(f"scroll -> {target}")
        return page.locator(target).scroll_into_view_if_needed()
    dx = int(step.get("dx", 0))
    dy = int(step.get("dy", 0))
    logger.info(f"scroll(wheel) -> dx={dx}, dy={dy}")
    return page.mouse.wheel(dx, dy)


def execute_script(page: Any, context: dict, step: dict) -> Any:
    """执行自定义 JavaScript。参数: script, save_as?

    返回值规则:
    - 脚本返回值是 **dict 时自动合并进 context**(支持一次写回多个变量,
      如 ``(() => ({ remaining_seconds: 850, done: true }))()``)
    - 提供 ``save_as`` 时,返回值整体写入 ``context[save_as]``
    - 其他返回值(数字/字符串等)原样返回,不做处理
    """
    script = step["script"]
    logger.info(f"execute_script -> {script[:60]!r}")
    result = page.evaluate(script)
    if isinstance(result, dict):
        context.update(result)  # 返回值 dict 自动合并,JS 可写回多个变量
    return result


def press(page: Any, context: dict, step: dict) -> Any:
    """模拟键盘按键(回车提交等)。参数: key"""
    key = step["key"]
    logger.info(f"press -> {key}")
    return page.keyboard.press(key)


def fast_forward(page: Any, context: dict, step: dict) -> Any:
    """快进 Playwright 虚拟时钟。参数: ms(毫秒)

    首次调用会懒安装虚拟时钟(clock.install),之后可通过
    ``page.clock.fast_forward`` 跳过页面计时器。
    """
    ms = int(step["ms"])
    logger.info(f"fast_forward -> {ms}ms")
    try:
        page.clock.fast_forward(ms)
    except Exception:
        # 时钟未安装:先安装再快进(安装后从当前时间继续,不影响真实时间)
        page.clock.install()
        page.clock.fast_forward(ms)
    return None


def screenshot(page: Any, context: dict, step: dict) -> Any:
    """截图保存,用于调试或记录证据。参数: path(必填), full_page?

    相对路径基于项目根目录,自动创建父目录。
    """
    from pathlib import Path

    from core.config import BASE_DIR

    path = step["path"]
    full_page = bool(step.get("full_page", False))
    dest = Path(path)
    if not dest.is_absolute():
        dest = BASE_DIR / dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    logger.info(f"screenshot -> {dest} (full_page={full_page})")
    return page.screenshot(path=str(dest), full_page=full_page)


# action 名称 -> 处理函数
ACTION_HANDLERS: dict[str, Any] = {
    "navigate": navigate,
    "navigate_back": navigate_back,
    "click": click,
    "click_force": click_force,
    "fill": fill,
    "wait_for_selector": wait_for_selector,
    "get_text": get_text,
    "get_url": get_url,
    "count_elements": count_elements,
    "select_option": select_option,
    "hover": hover,
    "wait_for_url": wait_for_url,
    "get_attribute": get_attribute,
    "get_list": get_list,
    "log": log,
    "set_var": set_var,
    "sleep": sleep,
    "scroll": scroll,
    "execute_script": execute_script,
    "press": press,
    "fast_forward": fast_forward,
    "screenshot": screenshot,
}


def run_action(action: str, page: Any, context: dict, step: dict) -> Any:
    """根据 action 名称分发到对应处理函数。

    未知 action 会抛出 ValueError,避免配置拼写错误被静默忽略。
    """
    handler = ACTION_HANDLERS.get(action)
    if handler is None:
        raise ValueError(f"未知的 action: {action!r}")
    return handler(page, context, step)
