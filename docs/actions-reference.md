# 动作参考手册（Actions Reference）

本文档逐一说明「自动刷课」执行引擎中**每一个可用动作**的参数与作用，供编写 YAML 剧本
时查阅。所有动作都写在 `core/onlineclass/actions.py` 中，统一签名
`fn(page, context, step)`，由引擎的 `run_action` 按 `step["action"]` 分发。

## 0. 通用 step 字段

每个 step 都是一个 YAML 映射，除动作专属参数外，以下字段对所有动作通用：

- `action`（必填，字符串）：要执行的动作名称，例如 `navigate`、`click`。拼写错误会抛出
  `ValueError: 未知的 action`。
- `name`（可选，字符串）：该步骤的显示名，用于日志与报错提示。缺省时用 `action` 名称。
- `when`（可选，字符串）：条件表达式。求值为假时跳过整个步骤（不执行、不重试）。
  语法见《使用文档》第 5 节：支持真值判断、`!` 取反、六种比较运算符。
- `save_as`（可选，字符串）：把动作的返回值写入 `context[save_as]`，供后续 `${save_as}`
  引用。部分动作（如 `get_text`）要求必填；其余动作由引擎兜底写入。
- `on`（可选）：**元素对象**，来自 `for_each` 循环注入（`on: "${var}"`）。提供后动作
  直接操作该元素，不再用 `selector` 查找。⚠️ YAML 中必须写 `"on"`（带引号），裸写
  `on:` 会被解析为布尔值。
- `selector` 与 `on` 的关系：两者都有时 `on` 优先；都没有时动作抛错。

---

## 1. 导航类

### navigate

**作用**：跳转到指定 URL，流程的起点。

- **Playwright API**：`page.goto(url)`
- **参数**：
  - `url`（必填，字符串）：目标地址，支持 `https://...` 完整地址，也支持 `${变量}`
    引用（如 `"${base_url}/my/index"`）。
- **返回**：页面响应对象（一般不用）；没有写入 context 的副作用。

示例：

```yaml
- action: navigate
  url: "https://www.teachersedu.cn/my/index"

- action: navigate
  url: "${base_url}${index_path}"   # 变量拼接
```

### navigate_back

**作用**：浏览器后退一页。

- **Playwright API**：`page.go_back()`
- **参数**：无。
- **返回**：前一页的响应对象或 `None`。

示例：

```yaml
- action: navigate_back
```

---

## 2. 交互类

### click

**作用**：点击元素，最核心的操作。会等待元素可点击后执行。

- **Playwright API**：`page.click(selector)`，或元素对象的 `element.click()`（`on` 模式）
- **参数**：
  - `selector`（与 `on` 二选一，字符串）：CSS 选择器，支持 Playwright 扩展语法
    （如 `a:has-text('课程')`、`>> nth=1`）。
  - `on`（可选）：for_each 注入的元素对象。
- **返回**：`None`。

示例：

```yaml
- action: click
  selector: ".next-page"

- action: click
  "on": "${course}"          # for_each 循环中点击当前元素
```

### click_force

**作用**：强制点击，跳过可点击性检查（元素被遮挡 / 不可见时也能点）。

- **Playwright API**：`page.click(selector, force=True)`，或 `element.click(force=True)`
- **参数**：同 `click`（`selector` / `on` 二选一）。
- **适用场景**：元素上有透明遮罩、动画未结束、被判定不可见但实际可交互时。

示例：

```yaml
- action: click_force
  selector: "span.text_5"
```

### fill

**作用**：向输入框填入文本（账号、密码、搜索词等）。填入前自动清空原内容。

- **Playwright API**：`page.fill(selector, value)`
- **参数**：
  - `selector`（必填，字符串）：输入框选择器。
  - `value`（可选，字符串，默认 `""`）：要填入的内容，支持 `${变量}` 引用。
- **安全说明**：选择器包含 `password` / `captcha` / `密码` / `验证码` 等关键字，
  或填入值恰好等于 context 中的密码 / 验证码时，**日志会自动打码**为 `****`；
  实际填入页面的仍是真实值。
- **返回**：`None`。

示例：

```yaml
- action: fill
  selector: "input[placeholder='请输入账号']"
  value: "${username}"

- action: fill
  selector: "#code"
  value: "${captcha}"        # 验证码(由 request_captcha 注入或 get_text 提取)
```

### select_option

**作用**：选择下拉框（`<select>`）的选项。

- **Playwright API**：`page.select_option(selector, value)`
- **参数**：
  - `selector`（必填，字符串）：下拉框选择器。
  - `value`（与 `values` 二选一，字符串）：要选中的选项 `value`。
  - `values`（与 `value` 二选一，列表）：多选时一次选中多个选项。
- **返回**：实际选中的选项值列表。
- **注意**：`value` 与 `values` 都不提供时抛 `ValueError`。

示例：

```yaml
- action: select_option
  selector: "#category"
  value: "cs"

- action: select_option
  selector: "#multi"
  values: ["a", "b"]
```

### hover

**作用**：鼠标悬停到元素上，触发下拉菜单、悬浮提示等。

- **Playwright API**：`page.hover(selector)`，或 `element.hover()`（`on` 模式）
- **参数**：`selector` / `on` 二选一。
- **返回**：`None`。

示例：

```yaml
- action: hover
  selector: ".nav-menu"
```

### press

**作用**：模拟键盘按键，如回车提交表单、Tab 切换焦点。

- **Playwright API**：`page.keyboard.press(key)`
- **参数**：
  - `key`（必填，字符串）：按键名，如 `Enter`、`Tab`、`Escape`、`Control+A`。
- **返回**：`None`。

示例：

```yaml
- action: fill
  selector: "input[name='username']"
  value: "${username}"
- action: press
  key: "Enter"               # 回车提交
```

---

## 3. 等待类

### wait_for_selector

**作用**：等待元素出现 / 消失，确保后续操作有效。**核心中的核心**——页面加载慢或
元素延迟渲染时，先等它再操作。

- **Playwright API**：`page.wait_for_selector(selector, state=..., timeout=...)`
- **参数**：
  - `selector`（必填，字符串）：要等待的元素选择器。
  - `state`（可选，字符串，默认 `"visible"`）：等待状态，可选
    `visible`（可见）/ `hidden`（隐藏）/ `attached`（存在于 DOM）/ `detached`（移出 DOM）。
  - `timeout`（可选，整数，毫秒）：超时时间，默认由 Playwright 决定（30 秒）。
    超时抛异常（会按 `global.retry` 重试）。
- **返回**：匹配的元素对象（一般不用）。

示例：

```yaml
- action: wait_for_selector
  selector: "input[placeholder='请输入账号']"
  state: "visible"
  timeout: 5000
```

### wait_for_url

**作用**：等待页面跳转到指定地址，用于判断登录或导航成功。

- **Playwright API**：`page.wait_for_url(url, timeout=...)`
- **参数**：
  - `url`（必填，字符串）：目标地址，支持 **glob 通配**，如 `**/my/index`、
    `https://example.com/course/*`。
  - `timeout`（可选，整数，毫秒）：超时时间。
- **返回**：`None`。

示例：

```yaml
- action: click
  selector: "${login_btn_selector}"
- action: wait_for_url
  url: "**/my/index"
  timeout: 10000
```

### sleep

**作用**：步骤级手动暂停指定时长，等待页面稳定、防请求过快。

- **实现**：`time.sleep()`，引擎直接等待（不涉及浏览器）。
- **参数**（二选一）：
  - `seconds`（可选，数字）：暂停秒数，支持小数（如 `2.5`）。更直观，推荐。
  - `ms`（可选，整数，默认 `0`）：暂停毫秒数。
- **优先级**：同时给出时 `seconds` 优先。
- **返回**：`None`。

示例：

```yaml
- action: sleep
  seconds: 5                 # 暂停 5 秒

- action: sleep
  ms: 2000                   # 等价写法: 2 秒
```

> 循环板块的轮询间隔不在这里配置，用 `while.wait_between` / `for_each.wait_between`（秒）。

---

## 4. 数据提取类

### get_text

**作用**：读取元素文本（如验证码文本、课程名、章节名）并存入 context。

- **Playwright API**：`page.text_content(selector)`，或 `element.text_content()`（`on` 模式）
- **参数**：
  - `selector` / `on` 二选一。
  - `save_as`（**必填**，字符串）：文本写入的 context 变量名，后续用 `${save_as}` 引用。
- **副作用**：`context[save_as] = 文本`（元素无文本时为 `None`）。
- **返回**：读取到的文本。

示例：

```yaml
- action: get_text
  selector: ".text_2"
  save_as: captcha
- action: fill
  selector: "#code"
  value: "${captcha}"
```

### get_url

**作用**：获取当前页面的完整 URL（判断跳转 / 登录是否成功），可选写入 context。

- **Playwright API**：`page.url`（同步属性）
- **参数**：
  - `save_as`（可选，字符串）：URL 写入的 context 变量名，后续用 `${save_as}` 引用。
- **副作用**：提供 `save_as` 时写入 `context[save_as]`。
- **返回**：当前页面 URL 字符串。

典型用法：先 `navigate` 跳转，再 `get_url` 判断是否落在目标页（登录检测），
或配合 `if` / `when` 分支：

```yaml
- action: navigate
  url: "https://www.teachersedu.cn"
- action: sleep
  seconds: 3
- action: get_url
  save_as: current_url
- action: if
  condition: "current_url == 'https://www.teachersedu.cn/my/index'"
  then:
    - action: log
      message: "已登录"
  else:
    - action: log
      message: "未登录"
```

### count_elements

**作用**：统计匹配元素的数量（判断某元素是否存在、列表有几项）并存入 context。

- **Playwright API**：`page.locator(selector).count()`
- **参数**：
  - `selector`（必填，字符串）：统计的选择器。
  - `save_as`（**必填**，字符串）：数量写入的 context 变量名。
- **典型用法**：配合 `while.condition` 判断"还有没有下一页"（为 0 即假，循环退出）。
- **返回**：数量（整数）。

示例：

```yaml
- action: count_elements
  selector: ".next-page"
  save_as: has_next
```

### get_attribute

**作用**：读取元素的属性值（`href` 链接、`src` 图片地址等），可选写入 context。

- **Playwright API**：`page.get_attribute(selector, attribute)`，
  或 `element.get_attribute(attribute)`（`on` 模式）
- **参数**：
  - `selector` / `on` 二选一。
  - `attribute`（必填，字符串）：属性名，如 `href`、`src`、`data-id`。
  - `save_as`（可选，字符串）：属性值写入的 context 变量名。
- **副作用**：提供 `save_as` 时写入 `context[save_as]`。
- **返回**：属性值（元素无该属性时为 `None`）。

示例：

```yaml
- action: get_attribute
  selector: "video source"
  attribute: "src"
  save_as: video_src
```

### get_list

**作用**：获取匹配元素的对象列表，作为 `for_each` 循环的数据源，可选写入 context。

- **Playwright API**：`page.query_selector_all(selector)`
- **参数**：
  - `selector`（必填，字符串）：列表元素的选择器。
  - `save_as`（可选，字符串）：元素列表写入的 context 变量名。
- **副作用**：提供 `save_as` 时写入 `context[save_as]`（元素对象列表）。
- **返回**：元素对象列表。

示例：

```yaml
- action: get_list
  selector: ".course-item a"
  save_as: course_list
```

---

## 5. 页面控制类

### scroll

**作用**：滚动页面或元素，让懒加载内容出现。两种模式：

- **滚动到元素**（`selector` / `on` 模式）：
  - **Playwright API**：`page.locator(selector).scroll_into_view_if_needed()` 或元素自身方法。
  - 把目标元素滚动到可视区域，常用于"列表懒加载需先滚动才加载更多"。
- **滚轮增量**（`dx` / `dy` 模式，无 selector / on 时）：
  - **Playwright API**：`page.mouse.wheel(dx, dy)`
  - `dx`（可选，整数，默认 `0`）：水平滚动量（像素）。
  - `dy`（可选，整数，默认 `0`）：垂直滚动量（像素）。
- **返回**：`None`。

示例：

```yaml
- action: scroll
  selector: "#video-area"    # 滚动到视频区

- action: scroll
  dx: 0
  dy: 800                    # 向下滚 800 像素
```

### execute_script

**作用**：执行自定义 JavaScript，处理复杂或特殊场景。

- **Playwright API**：`page.evaluate(script)`
- **参数**：
  - `script`（必填，字符串）：要执行的 JS 代码。
  - `save_as`（可选，字符串）：把返回值整体写入 `context[save_as]`。
- **返回值规则**（写回 context 的三种方式）：
  - **返回值是 dict → 自动合并进 context**：JS 里 `return {...}` 即可一次写回多个
    变量，无需 `save_as`。例如
    `"(() => { const n = parseInt(document.querySelector('.x').textContent); return { remaining_seconds: n }; })()"`
    会把 `remaining_seconds` 写入 context。
  - **提供 `save_as`**：返回值（数字/字符串等）写入 `context[save_as]`，如
    `script: "window.location.href"` + `save_as: current_url`。
  - 其他返回值原样返回，不做处理。
- **安全提醒**：脚本内容会被原样执行。剧本是本地可信文件时可用；不要从不可信来源
  拼接脚本内容。注意 **`context` 是 Python 侧变量，浏览器里不存在**——不要写
  `context['x'] = ...`（会 `ReferenceError`），请用 `return {...}` 或 `save_as`。
- **返回**：JS 表达式结果（dict 时已自动合并进 context）。

示例——读取剩余时间并写回 `remaining_seconds`，供后续 `log` / `if` 引用：

```yaml
- action: execute_script
  script: "(() => { const el = document.querySelector('.countdown'); return { remaining_seconds: el ? parseInt(el.textContent) : 0 }; })()"
- action: log
  message: "当前剩余秒数: ${remaining_seconds}"   # 取到的是上一步写回的新值
- action: if
  condition: "remaining_seconds <= 10"
  then:
    - action: log
      message: "即将完成"
```

### screenshot

**作用**：截图保存，用于调试或记录证据。

- **Playwright API**：`page.screenshot(path=..., full_page=...)`
- **参数**：
  - `path`（**必填**，字符串）：保存路径。相对路径基于**项目根目录**（`BASE_DIR`），
    绝对路径原样使用；父目录不存在时自动创建。支持 `${变量}` 引用。
  - `full_page`（可选，布尔，默认 `false`）：`true` 时截取整页（含滚动未显示部分），
    `false` 只截当前可视区域。
- **返回**：截图的二进制内容（一般不用）。

示例：

```yaml
- action: screenshot
  path: "output/onlineclass/evidence.png"
  full_page: false
```

### fast_forward

**作用**：快进 Playwright **虚拟时钟**，跳过视频播放计时器等按时间推进的机制。

- **Playwright API**：`page.clock.fast_forward(ms)`
- **参数**：
  - `ms`（必填，整数）：快进的毫秒数。
- **注意**：首次调用会自动安装虚拟时钟（懒安装）。它只影响 Playwright 的虚拟时间，
  **不影响真实时间**；若页面导航发生在首次调用之前，时间轴控制可能不完整，建议配合
  `sleep` 兜底。
- **返回**：`None`。

示例：

```yaml
- action: fast_forward
  ms: 60000                  # 快进 60 秒
```

### set_var

**作用**：给 context 变量赋值（如登录检测后写入 `needs_login`），供后续 `when` / `if` /
`while.condition` 判断或 `${变量}` 引用。不做任何浏览器操作。

- **实现**：直接写 `context[name] = value`
- **参数**：
  - `name`（必填，字符串）：要赋值的 context 变量名。
  - `value`（必填，任意类型）：赋的值。支持：
    - 布尔：`true` / `false`（YAML 原生布尔）
    - 数字：`3`、`2.5`
    - 字符串：`"高等数学"`
    - `${变量}` 引用：`"${username}"`（由引擎先替换再赋值）
- **返回**：赋的值。

**典型用法——登录检测后标记，登录环节按标记跳过**：

```yaml
# 检测是否已登录
check_login:
  - action: navigate
    url: "https://www.teachersedu.cn"
  - action: sleep
    seconds: 3
  - action: get_url
    save_as: current_url
  - action: if
    condition: "current_url == 'https://www.teachersedu.cn/my/index'"
    then:
      - action: set_var
        name: needs_login
        value: false          # 已在登录页 → 不需要登录
    else:
      - action: set_var
        name: needs_login
        value: true           # 不在登录页 → 需要登录

# 登录环节:根据标记决定是否执行
login:
  - action: log
    message: "开始登录流程"
  - action: fill
    selector: "input[name='username']"
    value: "${username}"
    when: "needs_login"       # 仅当需要登录时填写账号
  - action: fill
    selector: "input[name='password']"
    value: "${password}"
    when: "needs_login"
  - action: click
    selector: "span.login-btn"
    when: "needs_login"
  - action: log
    message: "已登录,跳过登录环节"
    when: "!needs_login"
```

条件判断规则见《使用文档》第 5 节：`needs_login` 为真值（`true` / 非 0 数字 /
非空字符串）时 `when: "needs_login"` 通过；`!needs_login` 取反。

### log

**作用**：输出一条日志，用于流程标记与排查。不做任何浏览器操作。

- **实现**：`loguru.logger.info(message)`
- **参数**：
  - `message`（可选，字符串，默认 `""`）：要输出的内容，支持 `${变量}` 引用。
- **返回**：消息本身。

示例：

```yaml
- action: log
  message: "正在学习第 ${learning_iteration} 页"
```

---

## 6. 引擎级指令与流程控制（不是普通动作）

以下不是 `actions.py` 里的动作，而是引擎在 `_execute_step` / `_dispatch_section` 中
直接拦截处理的**指令与流程控制**，不参与 `global.retry` 重试，也不在
`ACTION_HANDLERS` 中。

### if

**作用**：条件分支——按 `condition` 求值，执行 `then` 或 `else` 子步骤列表（支持嵌套）。

- **参数**：
  - `condition`（必填，字符串）：条件表达式（真值 / `!` 取反 / 六种比较），支持 `${变量}`。
  - `then`（可选，列表）：条件为真时执行的子步骤。
  - `else`（可选，列表）：条件为假时执行的子步骤（可省略）。
- **变量替换时机**：`condition` 在求值前替换；**`then` / `else` 子步骤在真正执行时才
  替换变量**——因此分支内先更新变量（如 `execute_script` + `save_as`）再引用
  （如 `log`）时，取到的是更新后的新值。
- **返回**：`None`。

示例：

```yaml
- action: if
  condition: "login_box_count > 0"
  then:
    - action: fill
      selector: "#user"
      value: "${username}"
  else:
    - action: log
      message: "已处于登录态"
```

### request_captcha

**作用**：请求验证码——提取验证码图片，把任务置为 `waiting_captcha` 状态**阻塞等待**
外部（前端用户）提交，收到验证码后注入 `context["captcha"]` 并继续执行。
由任务中心配合使用，详见《使用文档》第 12 章"验证码交互"。

- **参数**（图片来源三选一）：
  - `image_url`（可选，字符串）：直接使用该 URL 作为验证码图片。
  - `image_selector`（可选，字符串）：截图该元素作为验证码图片。
  - 都不提供：截取整页作为验证码图片。
- **副作用**：`context["captcha"] = 用户提交的验证码`。
- **返回**：验证码文本。

示例：

```yaml
- action: request_captcha
  image_selector: ".captcha-img"
- action: fill
  selector: "#code"
  value: "${captcha}"
```

### while（板块级循环）

**作用**：重复执行一组步骤，直到条件不成立或达到上限。典型场景：翻页刷课，
"还有下一页就继续"。

- **配置位置**：作为**板块**的顶层键（与 `steps` 平级），不是 step 里的 action。
- **参数**（都在 `while` 键下）：
  - `key`（可选，字符串）：循环计数键名，用于区分多条循环。执行期间
    `context["{key}_iteration"]` 为当前迭代次数（从 1 开始）。
  - `max_iterations`（可选，整数）：最大迭代次数，**防死循环保护**（恰好执行 N 次）。
  - `wait_between`（可选，数字，秒）：每轮之间的暂停间隔。
  - `condition`（可选，字符串）：条件表达式。**执行完一轮 steps 后**求值，
    为真则继续下一轮（do-while 语义），为假退出。未定义变量视为假。
  - `steps`（必填，列表）：每轮执行的步骤。
- **语义要点**：**先执行一轮 steps，再判断 condition**——因此 `condition` 引用的
  变量（如 `has_next`）应在本轮 steps 内写入（用 `count_elements` / `get_url` /
  `set_var` 等）。
- **支持嵌套**：`steps` 里可以再放 `while` / `for_each` 嵌套板块，循环可任意嵌套
  （如"翻页外层 + 每页遍历课程内层"）。内层循环的变量（`var`、`{key}_iteration`）
  在真正执行时才解析，可在步骤中直接引用外层循环的变量。
- **返回**：`None`。

示例：

```yaml
learning_loop:
  while:
    key: learning
    max_iterations: 10      # 防死循环保护
    wait_between: 2
    condition: "has_next"   # context["has_next"] 为真则继续
  steps:
    - action: count_elements
      selector: ".next-page"
      save_as: has_next     # 本轮写入,循环末尾判断
    - action: log
      message: "正在学习第 ${learning_iteration} 页"
    - action: click
      selector: ".next-page"
      when: "has_next"      # 最后一轮 has_next=0,不再点击
```

**嵌套示例——while 外层翻页 + for_each 内层遍历每页的课程**：

```yaml
study_all:
  while:
    key: page
    max_iterations: 10
    condition: "has_next"
  steps:
    - action: get_list
      selector: ".course-item"
      save_as: page_courses
    - for_each:                  # 嵌套 for_each 板块
        items: "${page_courses}"
        var: course
      steps:
        - action: get_text
          "on": "${course}"
          save_as: course_name
        - action: log
          message: "第 ${page_iteration} 页: ${course_name}"
        - action: click
          "on": "${course}"
        - action: wait_for_url
          url: "**/course/*"
    - action: count_elements
      selector: ".next-page"
      save_as: has_next
```

### for_each（板块级遍历）

**作用**：遍历一个元素列表（`get_list` 的结果）或普通数组，对每一项执行一组步骤。
典型场景：遍历课程 / 章节列表逐个点击进入。

- **配置位置**：作为**板块**的顶层键（与 `steps` 平级）。
- **参数**（都在 `for_each` 键下）：
  - `items`（必填）：要遍历的列表。写 `${变量名}` 引用 context 中的列表
    （如 `${course_list}`，由 `get_list` 写入），或直接内嵌数组
    （`["a", "b"]`）。
  - `var`（必填，字符串）：循环变量名。每轮 `context[var]` 为当前项
    （元素对象或标量）。
  - `key`（可选，字符串）：计数键名；执行期间 `context["{key}_iteration"]`
    为当前序号（从 1 开始）。
  - `max_iterations`（可选，整数）：最多遍历前 N 项（防失控截断）。
  - `wait_between`（可选，数字，秒）：每项之间的暂停间隔。
  - `steps`（必填，列表）：对每一项执行的步骤。
- **on 字段配合**：当 `items` 是元素列表时，steps 内用
  `"on": "${var}"` **直接操作当前元素**（点击 / 悬停 / 读文本 / 读属性）。
  ⚠️ `on` 是 YAML 布尔别名，必须写 `"on"`（带引号）。
- **清理**：遍历结束后 `context[var]` 会被移除，避免污染后续板块。
- **返回**：`None`。

示例：

```yaml
course_loop:
  for_each:
    items: "${course_list}"   # get_list 保存的元素列表
    var: course
    key: courses
    max_iterations: 20
    wait_between: 1
  steps:
    - action: get_list
      selector: ".course-item a"
      save_as: course_list
    - action: get_text
      "on": "${course}"       # 读取当前元素文本
      save_as: course_name
    - action: log
      message: "进入课程: ${course_name}"
    - action: click
      "on": "${course}"       # 点击当前元素
```

### call_section

**作用**：板块级流程调用——执行另一个板块（如 `login` 执行完重新调用 `check_login`），
实现流程复用与重检测。被调用的板块可以是列表 / steps / while / for_each 任意形式。

- **参数**：
  - `section`（必填，字符串）：要调用的**板块名**（顶层键，不带路径；支持 `${变量}`）。
- **行为**：找到该板块并整体执行（其内部步骤各自执行/重试）；板块不存在抛
  `ValueError`。
- **注意**：调用链由用户控制，**避免写成无限递归**（如 check_login → login →
  check_login 的循环要配 `set_var` / `if` 等退出条件）。
- **返回**：`None`。

示例——`login` 结束后重新检测登录态：

```yaml
check_login:
  - action: navigate
    url: "${base_url}"
  - action: get_url
    save_as: current_url
  - action: if
    condition: "current_url == '${base_url}${index_path}'"
    then:
      - action: set_var
        name: needs_login
        value: false
    else:
      - action: set_var
        name: needs_login
        value: true

login:
  - action: if
    condition: "needs_login == True"
    then:
      - action: fill
        selector: "${account_selector}"
        value: "${username}"
      - action: click
        selector: "${login_btn_selector}"
      - action: call_section     # 登录完成后重新调用 check_login
        section: check_login
```

### when（步骤级条件跳过）

**作用**：给**任意 step** 附加条件，条件不成立时跳过该步骤（不执行、不重试）。
也作用于 `if`、嵌套板块等。

- **位置**：step 内的通用字段（见第 0 节）。
- **参数**：`when`（字符串）：条件表达式（真值 / `!` 取反 / 六种比较）。
- **返回**：跳过时返回 `None`。

示例：

```yaml
- action: fill
  selector: "input[name='username']"
  value: "${username}"
  when: "needs_login"         # 仅当需要登录时才填

- action: log
  message: "已登录,跳过登录"
  when: "!needs_login"
```

---

## 7. 速查：动作与必填参数一览

以下用文字列出每个动作的**必填参数**（可选参数见上文对应小节）：

- `navigate`：`url`
- `navigate_back`：无
- `click`：`selector` 或 `on`
- `click_force`：`selector` 或 `on`
- `fill`：`selector`（`value` 可选，默认空）
- `wait_for_selector`：`selector`（`state` / `timeout` 可选）
- `get_text`：`selector` 或 `on`，`save_as`
- `get_url`：无（`save_as` 可选）
- `count_elements`：`selector`，`save_as`
- `select_option`：`selector`，`value` 或 `values`
- `hover`：`selector` 或 `on`
- `wait_for_url`：`url`（`timeout` 可选）
- `get_attribute`：`selector` 或 `on`，`attribute`（`save_as` 可选）
- `get_list`：`selector`（`save_as` 可选）
- `log`：无（`message` 可选）
- `set_var`：`name`，`value`
- `sleep`：无（`seconds` 或 `ms` 可选）
- `scroll`：`selector` / `on` 与 `dx` / `dy` 二选一
- `execute_script`：`script`
- `press`：`key`
- `fast_forward`：`ms`
- `screenshot`：`path`（`full_page` 可选）
- `if`（指令）：`condition`（`then` / `else` 可选）
- `request_captcha`（指令）：`image_url` / `image_selector` 二选一或省略
- `call_section`（指令）：`section`
- `while`（板块）：`steps`；`key` / `max_iterations` / `wait_between` / `condition` 可选
- `for_each`（板块）：`items`，`var`，`steps`；`key` / `max_iterations` / `wait_between` 可选
- `when`（通用字段）：`条件表达式`（加到任意 step 上，假则跳过）
