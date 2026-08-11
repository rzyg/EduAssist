"""配置驱动的执行引擎 —— “翻译官”。

加载 data/onlineclass 下的 YAML 剧本,将声明式的 step 逐条翻译为
Playwright 的 Python API 调用。

支持特性:
- ``${变量名}`` 占位符递归替换(context 优先,其次 env)
- 板块(section)顺序执行;线性步骤支持 ``when`` 条件跳过
- 板块级 while 循环与 for_each 遍历(max_iterations / wait_between / condition)
- 步骤级 ``action: if`` 分支(then / else)
- 关键动作的重试机制(global.retry)
"""
from __future__ import annotations

import base64
import re
import time
from pathlib import Path
from typing import Any, Callable

import yaml
from loguru import logger

from core.onlineclass.actions import run_action

# 顶层中不作为板块执行的固定键
_META_KEYS = {"global", "env"}
_VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")


class TaskStoppedError(Exception):
    """任务被外部请求停止,引擎在下一个检查点抛出并终止执行。"""


def _ensure_proactor_policy() -> Any:
    """确保当前事件循环策略支持子进程(Playwright 启动 driver 需要)。

    uvicorn 在 Windows 会把全局策略设为 ``WindowsSelectorEventLoopPolicy``,
    其 ``create_subprocess_exec`` 抛 ``NotImplementedError``,导致 Playwright
    无法启动浏览器进程。这里临时切换为 ``WindowsProactorEventLoopPolicy``,
    并返回切换前的原策略,供调用方在 Playwright 停止后恢复。
    非 Windows 或策略本就可用时返回 ``None``。
    """
    import asyncio
    import sys

    if sys.platform == "win32":
        policy = asyncio.get_event_loop_policy()
        if isinstance(policy, asyncio.WindowsSelectorEventLoopPolicy):
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            return policy
    return None


class CourseEngine:
    def __init__(self, config_path: str | Path):
        config_path = Path(config_path)
        with open(config_path, "r", encoding="utf-8") as f:
            self.config: dict = yaml.safe_load(f) or {}
        # 全局上下文,用于步骤间传递数据
        self.context: dict[str, Any] = {}
        # 关键步骤重试次数
        self.retry: int = int(self.config.get("global", {}).get("retry", 2))
        # 各循环的迭代计数(key 用于区分多条循环)
        self._iterations: dict[str, int] = {}
        self._env_source: dict[str, Any] = self.config.get("env") or {}
        # 停止检查回调(run 时传入,循环/步骤间隙调用;命中抛 TaskStoppedError)
        self._stop_check: Callable[[], bool] | None = None
        # 验证码请求回调(run 时传入;request_captcha 指令调用,阻塞返回验证码文本)
        self._captcha_request: Callable[[str], str] | None = None
        # 当前活动 page(run 期间有效,供任务中心查询/截图)
        self.page: Any = None

    def _check_stop(self) -> None:
        """在循环/板块间隙检查停止请求,命中则抛 TaskStoppedError。"""
        if self._stop_check is not None and self._stop_check():
            raise TaskStoppedError("任务收到停止请求")

    # ── 验证码等待 ─────────────────────────────────────────────────────
    def _request_captcha(self, page: Any, step: dict) -> str:
        """``request_captcha`` 指令:提取验证码图片并阻塞等待外部提交。

        参数(三选一):
        - ``image_url``: 直接使用验证码图片 URL
        - ``image_selector``: 截图该元素作为验证码图片
        - 缺省: 截取整页作为验证码图片
        返回的验证码文本会注入 ``context["captcha"]`` 供后续 ${captcha} 引用。
        """
        if self._captcha_request is None:
            raise ValueError("引擎未启用验证码回调,request_captcha 需要 run(captcha_request=...)")
        image = self._capture_captcha_image(page, step)
        logger.info("request_captcha -> 等待外部提交验证码")
        text = self._captcha_request(image)  # 阻塞,直到外部提交或任务停止
        self.context["captcha"] = text
        logger.info(f"request_captcha -> 收到验证码 (长度 {len(text)})")
        return text

    @staticmethod
    def _capture_captcha_image(page: Any, step: dict) -> str:
        """按步骤参数提取验证码图片,返回 data URL(``data:image/png;base64,...``)。"""
        image_url = step.get("image_url")
        if image_url:
            return str(image_url)
        image_selector = step.get("image_selector")
        if image_selector:
            data = page.locator(image_selector).screenshot()
        else:
            data = page.screenshot()
        encoded = base64.b64encode(data).decode("ascii")
        return f"data:image/png;base64,{encoded}"

    # ── 变量替换 ─────────────────────────────────────────────────────────
    def _resolve_var(self, name: str) -> Any:
        """按 名字 -> context -> env 的顺序解析变量值。

        支持 ``a.b`` 形式的嵌套取值,sep 记为点号。
        """
        parts = name.split(".")
        if parts[0] in self.context:
            value = self.context
        elif parts[0] in self._env_source:
            value = self._env_source
        else:
            raise KeyError(f"未定义的变量: {name!r}")
        for key in parts:
            if isinstance(value, dict):
                value = value[key]
            else:
                raise KeyError(f"变量 {name!r} 的取值路径非法")
        return value

    def _replace_in_string(self, text: str) -> str:
        def _repl(match: re.Match) -> str:
            name = match.group(1).strip()
            try:
                return str(self._resolve_var(name))
            except KeyError as exc:
                logger.warning(f"替换失败,保留原文: {exc}")
                return match.group(0)

        return _VAR_PATTERN.sub(_repl, text)

    def _replace_vars(self, value: Any) -> Any:
        """递归替换字符串 / 列表 / 字典中的 ``${变量}`` 占位符。"""
        if isinstance(value, str):
            return self._replace_in_string(value)
        if isinstance(value, list):
            return [self._replace_vars(item) for item in value]
        if isinstance(value, dict):
            return {key: self._replace_vars(item) for key, item in value.items()}
        return value

    # ── 条件求值 ─────────────────────────────────────────────────────────
    def _eval_condition(self, expr: str) -> bool:
        """求值循环 / when 的条件表达式。

        规则:
        - ``var``     -> context["var"] 为真(可含 a.b)
        - ``!var``    -> context["var"] 为假
        - ``var == x`` / ``var != x`` / ``var > x`` ... -> 与 x 比较
          (支持 ==, !=, >, >=, <, <= 六种运算符)
        """
        if expr is None:
            return True
        expr = expr.strip()
        # 比较运算符:两字符的必须排在单字符之前(如 >= 先于 >)
        for op in (">=", "<=", "==", "!=", ">", "<"):
            if op in expr:
                left, right = expr.split(op, 1)
                lhs: Any = self._resolve_var(left.strip())
                rhs = self._trim_value(right.strip())
                if lhs is None or str(lhs).strip() == "null":
                    lhs = None
                return self._compare_values(lhs, rhs, op)
        negate = expr.startswith("!")
        name = expr[1:].strip() if negate else expr
        try:
            val = self._resolve_var(name)
        except KeyError:
            val = None
        return not bool(val) if negate else bool(val)

    @staticmethod
    def _compare_values(lhs: Any, rhs: Any, op: str) -> bool:
        """数值优先、字符串兜底的比较,避免 str 与 int 混比抛 TypeError。"""
        try:
            if op == "==":
                return bool(lhs == rhs)
            if op == "!=":
                return bool(lhs != rhs)
            if op == ">":
                return bool(lhs > rhs)
            if op == ">=":
                return bool(lhs >= rhs)
            if op == "<":
                return bool(lhs < rhs)
            if op == "<=":
                return bool(lhs <= rhs)
            return False
        except TypeError:
            pass
        # 类型不匹配(如 str 与 int)时统一转字符串比较
        left_s, right_s = str(lhs), str(rhs)
        if op == "==":
            return left_s == right_s
        if op == "!=":
            return left_s != right_s
        if op == ">":
            return left_s > right_s
        if op == ">=":
            return left_s >= right_s
        if op == "<":
            return left_s < right_s
        if op == "<=":
            return left_s <= right_s
        return False

    @staticmethod
    def _trim_value(raw: str) -> Any:
        """去掉比较表达式右值的引号并尝试转数字/布尔。"""
        raw = raw.strip()
        if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
            return raw[1:-1]
        if raw in ("True", "true"):
            return True
        if raw in ("False", "false"):
            return False
        try:
            return int(raw)
        except ValueError:
            pass
        try:
            return float(raw)
        except ValueError:
            pass
        return raw

    def _save_context(self, step: dict, result: Any) -> None:
        """将 action 结果写入 context。actions 内部(get_text/count)也会写,
        这里兜底处理通用 ``save_as`` 字段。"""
        save_as = step.get("save_as")
        if save_as and result is not None:
            self.context[save_as] = result

    # ── 单步执行(含重试) ────────────────────────────────────────────────
    def _execute_step(self, page: Any, step: dict) -> Any:
        # 嵌套板块(无 action 且含 while/for_each/steps 键): 不预替换变量,
        # 直接递归分发 —— 内层步骤在真正执行时再解析变量,支持循环变量延迟引用
        # (如 while 内嵌 for_each 时, ${var} 需等内层循环写入后才可解析)
        if isinstance(step, dict) and "action" not in step and (
            "while" in step or "for_each" in step or "steps" in step
        ):
            when = step.get("when")
            if when and not self._eval_condition(when):
                logger.info(f"[] 跳过 step (when={when!r})")
                return None
            if "while" in step:
                self._execute_loop(page, step)
            elif "for_each" in step:
                self._execute_foreach(page, step)
            else:
                self._execute_section(page, self._get_steps(step))
            return None

        # if 指令: 只替换 condition 本身, then / else 子步骤**延迟到执行时替换**
        # (否则分支内步骤更新变量后, log 等仍显示 if 入口处固化的旧值)
        if isinstance(step, dict) and step.get("action") == "if":
            when = step.get("when")
            if when and not self._eval_condition(when):
                logger.info(f"[] 跳过 step (when={when!r})")
                return None
            condition = step.get("condition")
            if isinstance(condition, str):
                condition = self._replace_in_string(condition)
            branch = "then" if self._eval_condition(condition) else "else"
            branch_steps = step.get(branch) or []
            logger.info(f"[if] 条件 {condition!r} -> 执行 {branch} 分支 ({len(branch_steps)} 步)")
            if branch_steps:
                self._execute_section(page, branch_steps)
            return None

        step = self._replace_vars(step)  # 先替换变量
        if not isinstance(step, dict):
            raise ValueError(f"step 必须是字典, 实际为: {type(step).__name__}")

        action = step.get("action")

        # 支持可选的 when 条件跳过(对嵌套板块同样生效)
        when = step.get("when")
        if when and not self._eval_condition(when):
            logger.info(f"[] 跳过 step (when={when!r})")
            return None

        if not action:
            raise ValueError(f"step 缺少 action 字段: {step!r}")

        # 验证码指令:提取图片并阻塞等待外部提交
        # 有意放在重试循环之外:验证码等待天然可重试(用户重新提交),无需引擎重试
        if action == "request_captcha":
            return self._request_captcha(page, step)

        # 板块调用指令:执行 login 后可重新调用 check_login 等,实现板块级流程复用
        # 有意放在重试循环之外:板块整体失败由其内部步骤各自重试
        if action == "call_section":
            section_name = str(step["section"])
            section_cfg = self.config.get(section_name)
            if section_cfg is None:
                raise ValueError(f"板块 {section_name!r} 不存在,无法调用")
            logger.info(f"[call_section] 调用板块: {section_name}")
            self._dispatch_section(page, section_name, section_cfg)
            return None

        name = step.get("name", action)
        attempts = max(1, self.retry + 1)
        for attempt in range(1, attempts + 1):
            try:
                result = run_action(action, page, self.context, step)
                self._save_context(step, result)
                return result
            except TaskStoppedError:
                raise  # 停止请求不参与重试
            except Exception as exc:
                message = (f"step '{name}' action={action} 第 {attempt}/{attempts} 次失败: {exc}")
                if attempt < attempts:
                    logger.warning(f"{message}, 稍后重试...")
                    time.sleep(1.0)
                else:
                    logger.error(message)
                    raise

    # ── 线性板块 ─────────────────────────────────────────────────────────
    @staticmethod
    def _get_steps(section_cfg: dict) -> list:
        """提取板块步骤列表(只认 ``steps`` 键)。"""
        return section_cfg.get("steps") or []

    def _execute_section(self, page: Any, steps: list) -> None:
        if not steps:
            return
        for step in steps:
            logger.debug(f"- {step}")
            self._execute_step(page, step)

    # ── while 循环板块 ───────────────────────────────────────────────────
    def _execute_loop(self, page: Any, loop_cfg: dict) -> None:
        """执行 while 循环(do-while 语义)。

        loop_cfg 结构::

            while:
              key: learning      # 可选,用于区分多条循环的计数
              max_iterations: 10
              wait_between: 1    # 秒
              condition: has_next # 可选,context 变量为真则继续
            steps: [...]

        语义:无条件先执行一轮 steps,再按 condition 决定是否继续,
        因此 condition 引用的变量可在 steps 内写入(如 count_elements)。
        """
        steps = self._get_steps(loop_cfg) if isinstance(loop_cfg, dict) else []
        while_cfg = loop_cfg.get("while") or {}
        key = str(while_cfg.get("key", "__main__"))
        max_iterations = int(while_cfg.get("max_iterations", 0)) or 0
        wait_between = float(while_cfg.get("wait_between", 0) or 0)
        condition = while_cfg.get("condition")

        self._iterations[key] = 0
        while True:
            self._check_stop()
            # 上限保护,避免死循环(恰好执行 max_iterations 次)
            if max_iterations > 0 and self._iterations[key] >= max_iterations:
                logger.info(f"loop[{key}] 达到 max_iterations={max_iterations},退出")
                break

            # 将当前迭代计数(1-based)写入 context,可在步骤/condition 中引用
            self._iterations[key] += 1
            self.context[f"{key}_iteration"] = self._iterations[key]
            logger.info(f"loop[{key}] 第 {self._iterations[key]} 次迭代")
            self._execute_section(page, steps)

            if wait_between > 0:
                time.sleep(wait_between)

            # do-while:执行完 steps 后,按 condition 决定是否继续
            if condition and not self._eval_condition(condition):
                logger.info(f"loop[{key}] 条件 {condition!r} 不成立,退出")
                break

    # ── for_each 循环板块 ────────────────────────────────────────────────
    def _execute_foreach(self, page: Any, foreach_cfg: dict) -> None:
        """执行 for_each 遍历。

        foreach_cfg 结构::

            for_each:
              items: "${course_list}"   # 引用 get_list 结果或内嵌数组
              var: course               # 循环变量名(写入 context, 值为元素/标量)
              max_iterations: 20        # 可选,防失控截断
              wait_between: 1           # 可选,每项间隔(秒)
            steps: [...]

        循环体内可通过 ``on: "${var}"`` 直接操作当前元素(ElementHandle):
        引擎把元素对象注入 on 字段,变量替换对非字符串对象原样保留。
        """
        steps = self._get_steps(foreach_cfg) if isinstance(foreach_cfg, dict) else []
        cfg = foreach_cfg.get("for_each") or {}
        var = str(cfg.get("var", "item"))
        key = str(cfg.get("key", var))
        max_iterations = int(cfg.get("max_iterations", 0)) or 0
        wait_between = float(cfg.get("wait_between", 0) or 0)
        items_expr = cfg.get("items")
        if isinstance(items_expr, str):
            name = items_expr.strip()
            if name.startswith("${") and name.endswith("}"):  # 剥离 ${} 占位符
                name = name[2:-1]
            items = self._resolve_var(name)
        else:
            items = items_expr
        if not isinstance(items, (list, tuple)):
            raise ValueError(f"for_each.items 必须解析为列表, 实际为: {type(items).__name__}")
        if max_iterations > 0:
            items = list(items)[:max_iterations]

        self._iterations[key] = 0
        total = len(items)
        for idx, item in enumerate(items):
            self._check_stop()
            self._iterations[key] = idx + 1
            self.context[f"{key}_iteration"] = idx + 1
            self.context[var] = item
            # 将 on: "${var}" 纯占位符替换为元素对象(兼容 YAML 裸 on -> True 键)
            prepared = []
            for step in steps:
                step = dict(step)
                for field in ("on", True):
                    if field in step and isinstance(step[field], str) and step[field] == f"${{{var}}}":
                        step[field] = item
                prepared.append(step)
            logger.info(f"foreach[{key}] 第 {idx + 1}/{total} 项")
            self._execute_section(page, prepared)
            if wait_between > 0:
                time.sleep(wait_between)
        self.context.pop(var, None)  # 清理循环变量,避免污染后续板块

    # ── 板块分发 ────────────────────────────────────────────────────────
    def _dispatch_section(self, page: Any, section_name: str, section_cfg: Any) -> None:
        logger.info(f"== 执行板块: {section_name} ==")
        if section_cfg is None:
            return
        if isinstance(section_cfg, dict) and "while" in section_cfg:
            self._execute_loop(page, section_cfg)
        elif isinstance(section_cfg, dict) and "for_each" in section_cfg:
            self._execute_foreach(page, section_cfg)
        elif isinstance(section_cfg, dict) and "steps" in section_cfg:
            self._execute_section(page, self._get_steps(section_cfg))
        elif isinstance(section_cfg, list):
            self._execute_section(page, section_cfg)
        else:
            raise ValueError(f"板块 {section_name!r} 无法识别: {section_cfg!r}")

    # ── 浏览器启动 ──────────────────────────────────────────────────────
    @staticmethod
    def _launch_page(global_cfg: dict) -> Any:
        """启动持久化浏览器上下文并返回首个 page。

        优先复用现有用户目录(cookies / 登录态),与 run.py 保持一致。
        """
        from core.config import DATA_DIR

        globals_cfg = global_cfg or {}
        user_data_dir = Path(DATA_DIR) / "browser-profile"
        user_data_dir.mkdir(parents=True, exist_ok=True)

        from playwright.sync_api import sync_playwright

        headless = bool(globals_cfg.get("headless", False))
        channel = globals_cfg.get("channel", "msedge")
        start_url = globals_cfg.get("start_url")

        # uvicorn(Windows) 把全局事件循环策略设为 Selector,不支持子进程;
        # 在启动 Playwright 前临时切换为 Proactor,原策略挂到 page 上供任务结束恢复
        prev_policy = _ensure_proactor_policy()
        pw = sync_playwright().start()
        launch_kwargs: dict[str, Any] = {"headless": headless, "channel": channel}
        if not headless:
            # 有界面模式:禁用模拟视口,让页面跟随真实窗口大小,全屏/缩放即时生效
            # (默认固定 1280x720 模拟视口,与手动调整的窗口大小脱钩;
            #  注意 viewport=None 在 Python 侧会被过滤,须用 no_viewport=True)
            launch_kwargs["no_viewport"] = True
        context = pw.chromium.launch_persistent_context(
            str(user_data_dir),
            **launch_kwargs,
        )
        # 反检测: playwright-stealth(默认启用;global.stealth: false 可关闭;
        # 库缺失/失败时警告并继续,不阻断任务)
        if bool(globals_cfg.get("stealth", True)):
            try:
                from playwright_stealth import Stealth

                Stealth().apply_stealth_sync(context)
                logger.info("playwright-stealth 反检测已应用")
            except Exception as exc:
                logger.warning(f"playwright-stealth 应用失败(继续运行): {exc}")
        page = context.pages[0] if context.pages else context.new_page()
        if start_url:
            page.goto(start_url)
        # 挂载便于 finally 关闭
        page._pw = pw
        page._pw_context = context
        page._pw_prev_policy = prev_policy
        return page

    # ── 主入口 ─────────────────────────────────────────────────────────
    def run(
        self,
        page: Any = None,
        close_browser: bool = True,
        stop_check: Callable[[], bool] | None = None,
        captcha_request: Callable[[str], str] | None = None,
        headless: bool | None = None,
    ) -> Any:
        """执行全部板块。

        - ``page`` 为 None 时自动启动浏览器(借用 data/browser-profile 持久化目录)
        - ``stop_check``: 可选回调,板块/循环间隙调用;返回 True 时抛
          ``TaskStoppedError`` 终止执行(任务中心停止机制)
        - ``captcha_request``: 可选回调;剧本中 ``request_captcha`` 指令调用,
          传入验证码图片 data URL,阻塞返回外部提交的验证码文本
        - ``headless``: 可选;None 时沿用剧本 ``global.headless``,否则覆盖之
          (True 无头 / False 有头)
        - 返回关闭后的 page(供外部继续操作)或 None
        """
        own_page = page is None
        try:
            if own_page:
                globals_cfg = dict(self.config.get("global") or {})
                if headless is not None:
                    globals_cfg["headless"] = headless
                page = self._launch_page(globals_cfg)
            self.page = page
            self._stop_check = stop_check
            self._captcha_request = captcha_request
            for section_name, section_cfg in self.config.items():
                if section_name in _META_KEYS:
                    continue
                self._check_stop()
                self._dispatch_section(page, section_name, section_cfg)
            return page
        finally:
            self._stop_check = None
            self._captcha_request = None
            if own_page and close_browser and page is not None:
                pw = getattr(page, "_pw", None)
                if pw is not None:
                    pw.stop()
