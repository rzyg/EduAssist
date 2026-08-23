# AGENTS.md — EduAssist（下班工具箱）

面向 AI 编码代理与人类协作者的仓库指南。改动代码前先通读本文，尤其「关键设计约束」与「防幻觉铁律」。

## 项目概述

EduAssist 是专为汝州一高教师开发的本地优先 Windows 桌面应用（Tauri + Vue + Python FastAPI），把老师从重复性事务中解放出来。产物是单一
NSIS 安装包，本地运算、开箱即用。

模块真实状态（以代码为准，README 进度表滞后，差异见文末）：

- **成绩分析** — 已实现：score/ 全链路 + 前端 2 页 + 测试
- **PDF 工具箱** — 已实现：pdf/ 3 模块 + 前端 4 页 + 测试
- **津贴计算** — 部分实现：allowance/ + 前端 2 页 + 测试（README 标为 Pro 规划中）
- **自动刷课** — 后端引擎已成型（动作引擎 + 任务中心 + 反检测 + 测试），前端为占位页（construction.vue）
- **辅助排课** — 仅后端雏形（core/timetable/main.py，OR-Tools 排课模型），无前端与 API 路由
- **普通版/Pro 开关** — README 声称前端功能开关区分，代码中未找到实现

## 技术栈

| 层       | 技术                                                                                   | 说明                                          |
|----------|----------------------------------------------------------------------------------------|-----------------------------------------------|
| 前端     | Vue 3 + TypeScript + Naive UI + Vite（unplugin-auto-import / unplugin-vue-components） | 跑在系统 WebView；dev 端口 1420（strictPort） |
| 桌面壳   | Tauri 2.0（Rust）+ tauri-plugin-opener                                                 | 托盘、静默更新、后端进程管理                  |
| 后端引擎 | Python 3.11 + FastAPI + uvicorn；生产 Nuitka 编成单 exe                                | 运算全本地；REST /api/v1/*                    |

后端依赖（core/requirements.txt）：playwright/playwright-stealth（刷课）、pypdf/pikepdf（PDF）、openpyxl（Excel）、aiosqlite（本地队列）、httpx（AI
代理/云端）、loguru（日志）、pyyaml（配置）；开发：pytest/pytest-asyncio/ruff/nuitka。

## 核心命令

### 前端

- `pnpm dev`（等价 `npm run dev`）— 单跑 Vite dev server（端口 1420；浏览器调试时后端地址回退 http://127.0.0.1:7410）
- `pnpm build` — vue-tsc 类型检查 + vite 构建到 dist/

### 后端（开发）

后端由 Rust 壳在 `pnpm tauri dev` 时自动拉起；也可单独启动：

- `conda run -n eduassist python -m core.main`（lib.rs 首选；回退 `.venv/Scripts/python.exe -m core.main`）
- core/main.py 内部启动 uvicorn，监听 config.yaml 的 server.host/port（默认 127.0.0.1:7410）
- 依赖：`pip install -r core/requirements.txt`；刷课模块还需 `playwright install`

### 测试与 lint

- `python -m pytest tests/ -v` — 单元测试（tests/conftest.py 提供内存 Excel / 分数线 / 学生夹具）
- `ruff check core/` — Python lint

### 构建 / 打包（Windows）

1. 后端 exe：
   `python -m nuitka --standalone --output-dir=pydist --output-filename=main --enable-plugin=no-qt --follow-imports --lto=no --remove-output --jobs=0 core/main.py --windows-console-mode=disable --include-package=openpyxl --assume-yes-for-downloads` →
   pydist/main.dist/main.exe
2. `pnpm tauri build` — beforeBuildCommand 要求 pydist 存在（自动复制到 src-tauri/core），随后编译前端与 Rust
3. 安装包：`src-tauri/target/release/bundle/nsis/*.exe`；应用版本以 src-tauri/tauri.conf.json 为准（当前 1.3.3，package.json
   的 0.1.0 不可信）

CI：.github/workflows/build-deploy.yml，tag v* 触发，Windows runner，产物上传 GitHub Release 并 scp 部署。

## 项目结构（三段式）

```
src/                前端（Vue 3）
  config.ts         统一请求层（getApiBase / apiFetch / apiGet / apiPost / apiUpload）——唯一允许访问后端的地方
  router/index.ts   路由（/analysis /transcript /pdf/* /allowance/* /about /setting /fuck-the-online-class）
  pages/            score/（成绩单、分析） pdf/（merge/split/compress/edit） allowance/（calendar、attendance）
  components/       MainLayout / ScoreForm / DragArea / StartupScreen
src-tauri/          桌面壳（Rust）
  src/lib.rs        Tauri 命令：start/kill/restart_backend、get_token、get_backend_url、get_dev_mode、download_and_install；托盘与日志
  tauri.conf.json   productName、version、NSIS 配置、resources: core/**
core/               后端引擎（Python FastAPI）
  main.py           入口：uvicorn + Bearer 鉴权中间件 + 异常兜底 + parent_watchdog
  config.py         config.yaml 读写（缺字段自动回写默认）
  route/            /api/v1/* 路由：auth / score / pdf / onlineclass / allowance / config
  score/            成绩解析（extract / map / models / analysis）+ 输出（成绩单、分析）
  onlineclass/      刷课：动作引擎（actions / engine）+ task_manager 任务中心 + 反检测
  pdf/              merge / split / compress
  allowance/        津贴：check/（load_data、statistics、output）+ utils/holiday.py
  db/               本地 SQLite（aiosqlite：init / CRUD）
tests/              pytest 单元测试
docs/               frontend-backend.md、onlineclass.md、actions-reference.md
config.yaml         server.host/port、paths、dev_mode
```

## 关键设计约束

### 进程管理（禁止手动 kill）

- 后端生命周期完全由 Rust 壳管理：`start_backend` / `kill_backend` / `restart_backend` 命令启停；壳退出 / 托盘退出时用
  taskkill /F /T 杀进程树。
- 后端内置 parent_watchdog（core/parent_watchdog.py）：监控壳启动时注入的环境变量 EDUASSIST_PARENT_PID，父进程消失即 os._
  exit (0) 毫秒级自杀，防止残留占用 core/main.exe（否则 NSIS 安装器无法替换文件）。
- 约束：不要绕过壳手动启动 / 杀后端——手动启动拿不到随机 token；手动 kill 会与 watchdog 冲突并留下残留进程。

### 安全鉴权

- Rust 每次启动生成随机 token（时间戳 hex），前端经 `get_token` 命令获取，所有请求带 `Authorization: Bearer <token>`。
- 后端中间件校验（core/main.py）：/health 与 OPTIONS 放行；EDUASSIST_TOKEN 为空（dev 模式）放行。
- config.yaml 的 dev_mode 只控制是否跳过 Bearer 验证，不决定监听地址。

### 前端-后端通信

- 前端只经 src/config.ts 发请求（自动拼 base + 注入 token），页面组件禁止直接 fetch。
- 路由前缀统一 /api/v1/*，健康检查 /health；后端地址由 Rust `get_backend_url` 决定（dev 固定 http://127.0.0.1:7410，生产读
  config.yaml）。

### 配置

- config.yaml 是唯一配置源：Python（core/config.py）与 Rust（lib.rs read_config）各自解析同一文件；后端启动自动补齐缺失字段并回写。
- 新增配置项须同时更新 core/config.py 的 DEFAULT_CONFIG 与 lib.rs 的 ServerConfig / AppConfig 结构体。

## 防幻觉铁律

1. **不确定文件路径**：先 dir / glob 确认再动手，禁止凭印象写路径。
2. **不确定第三方库 API**：先查 package.json（前端）/ core/requirements.txt（后端），再查源码或官方文档，禁止编造 API 签名。
3. **不确定配置项或设计意图**：先查 config.yaml / docs/ / README；仍不确定就询问用户，严禁猜测。
4. 改代码前先读原文件；改完跑 `python -m pytest tests/ -v` 验证。

## AI 提交权限规则（严格执行）

1. **允许自动执行**：`git add .` 和 `git commit -m "..."`（生成符合规范的提交信息）。
2. **禁止自动执行**：`git push`。当你准备推送时，必须先向我报告：
    - 即将推送的提交列表（最近 3 条 commit hash 和 message）
    - 当前分支名称 等我输入“确认推送”或“push”指令后，你才可以执行 `git push`。
3. **提交前自检**：在执行 `git commit` 之前，必须先运行：
    - 前端改动：`pnpm build`（仅类型检查部分，即 `vue-tsc --noEmit`）
    - Python 改动：`ruff check core/`（快速 lint，不跑全量测试）
    - Rust 改动：`cargo check`（不生成二进制，比 `build` 快 80%） 如无错误才可提交。全量测试（pytest）可在 push 前手动触发。

## Git 分支策略（严格执行）

### 分支创建规则

1. **大功能（预估耗时 > 2 小时，或涉及多个文件跨层改动）**：
    - 必须从 `main` 切出新分支，命名格式：`feat/<功能名>` 或 `fix/<问题名>`（例如 `feat-onlineclass-retry`）。
    - 开发完成后，在本地切回 `main`，执行 `git merge <分支名>`，合并后删除本地分支（`git branch -d <分支名>`）。
    - **禁止**在 GitHub 上创建 PR，本地合并后直接推送 `main` 即可。

2. **小功能（预估耗时 < 30 分钟，单文件或单模块改动）**：
    - 直接在 `main` 分支上开发、提交、推送，无需切分支。

3. **灰色地带（预估 30 分钟 ~ 2 小时）**：
    - 默认切分支处理（安全优先）。如果改完后发现改动很小，可以 squash 合并回 `main`。

## 输出格式规范

**上下文确认**：每次回复的第一行，必须是 `开始执行喵~` 。