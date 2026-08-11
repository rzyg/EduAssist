<script lang="ts" setup>
import {computed, h, onMounted, onUnmounted, ref} from 'vue'
import type {VNode} from 'vue'
import {useMessage} from 'naive-ui'
import type {DataTableColumns} from 'naive-ui'
import {
  NButton, NSpace, NTag, NText, NTooltip
} from 'naive-ui'
import {
  FileText as FileTextIcon,
  Key as KeyIcon,
  Plus as PlusIcon,
  Refresh as RefreshIcon
} from '@vicons/tabler'
import {apiFetch, apiGet, apiPost} from '../../config'

const message = useMessage()

// ── 类型（对齐 core/onlineclass/task_manager/task.py 的 to_dict 结构） ──
type TaskStatus = 'pending' | 'running' | 'waiting_captcha' | 'finished'
type TaskResult = 'success' | 'failed' | 'stopped'

interface LocalConfig {
  name: string
  created_at: string
}

interface TaskInfo {
  task_id: string
  config_name: string
  config_path: string
  status: TaskStatus
  result: TaskResult | null
  error_message: string | null
  playback_rate: number
  captcha_image: string | null
  context: Record<string, unknown>
  started_at: number | null
  finished_at: number | null
}

// ── 状态 / 结果文案 ──
const STATUS_LABEL: Record<TaskStatus, string> = {
  pending: '待启动',
  running: '运行中',
  waiting_captcha: '等待验证码',
  finished: '已结束',
}

const RESULT_META: Record<TaskResult, { label: string; type: 'success' | 'error' | 'default' }> = {
  success: {label: '成功', type: 'success'},
  failed: {label: '失败', type: 'error'},
  stopped: {label: '已停止', type: 'default'},
}

function statusTagType(t: TaskInfo): 'default' | 'info' | 'warning' | 'success' | 'error' {
  switch (t.status) {
    case 'pending':
      return 'default'
    case 'running':
      return 'info'
    case 'waiting_captcha':
      return 'warning'
    case 'finished':
      return t.result === 'failed' ? 'error' : t.result === 'stopped' ? 'default' : 'success'
  }
}

// ── 任务列表 ──
const tasks = ref<TaskInfo[]>([])
const loadingTasks = ref(false)

async function loadTasks(silent = false) {
  if (!silent) loadingTasks.value = true
  try {
    tasks.value = await apiGet<TaskInfo[]>('/api/v1/tasks')
  } catch (e: any) {
    if (!silent) message.error(`加载任务列表失败：${e.message || e}`)
  } finally {
    loadingTasks.value = false
  }
}

// ── 流程配置 ──
const configs = ref<LocalConfig[]>([])
const loadingConfigs = ref(false)

async function loadConfigs() {
  loadingConfigs.value = true
  try {
    configs.value = await apiGet<LocalConfig[]>('/api/v1/configs/local')
  } catch (e: any) {
    message.error(`加载流程配置失败：${e.message || e}`)
  } finally {
    loadingConfigs.value = false
  }
}

const configOptions = computed(() =>
    configs.value.map(c => ({label: c.name, value: c.name}))
)

// ── 创建任务表单 ──
const configName = ref<string | null>(null)
const username = ref('')
const password = ref('')
const playbackRate = ref<number>(1)

type HeadlessMode = 'follow' | 'headless' | 'headful'
const headlessMode = ref<HeadlessMode>('follow')
const headlessOptions = [
  {label: '跟随剧本（默认）', value: 'follow'},
  {label: '无头模式（后台静默）', value: 'headless'},
  {label: '有头模式（显示浏览器）', value: 'headful'},
]
const headlessMap: Record<HeadlessMode, boolean | null> = {
  follow: null,
  headless: true,
  headful: false,
}

const creating = ref(false)

async function handleCreate() {
  if (!configName.value) {
    message.warning('请选择流程配置')
    return
  }
  if (!username.value.trim()) {
    message.warning('请输入账号')
    return
  }
  if (!password.value) {
    message.warning('请输入密码')
    return
  }
  creating.value = true
  try {
    await apiPost<TaskInfo>('/api/v1/tasks', {
      config_name: configName.value,
      username: username.value.trim(),
      password: password.value,
      headless: headlessMap[headlessMode.value],
      playbackRate: playbackRate.value || 1,
    })
    message.success('刷课任务已创建并启动')
    password.value = ''
    await loadTasks()
  } catch (e: any) {
    message.error(`创建任务失败：${e.message || e}`)
  } finally {
    creating.value = false
  }
}

// ── 启动 / 停止 / 删除 ──
async function startTask(row: TaskInfo) {
  try {
    await apiPost(`/api/v1/tasks/${row.task_id}/start`)
    message.success('任务已启动')
    await loadTasks()
  } catch (e: any) {
    message.error(`启动失败：${e.message || e}`)
  }
}

interface ConfirmMeta {
  title: string
  content: string
  okText: string
  danger: boolean
  run: () => Promise<void>
}

const showConfirm = ref(false)
const confirmMeta = ref<ConfirmMeta | null>(null)
const confirmLoading = ref(false)

function askStop(row: TaskInfo) {
  confirmMeta.value = {
    title: '停止任务',
    content: `确定停止任务「${row.config_name}」吗？浏览器窗口将关闭。`,
    okText: '停止',
    danger: false,
    run: async () => {
      await apiPost(`/api/v1/tasks/${row.task_id}/stop`)
      message.success('已请求停止任务')
      await loadTasks()
    },
  }
  showConfirm.value = true
}

function askDelete(row: TaskInfo) {
  confirmMeta.value = {
    title: '删除任务',
    content: `确定删除已结束任务「${row.config_name}」吗？该操作不可恢复。`,
    okText: '删除',
    danger: true,
    run: async () => {
      const res = await apiFetch(`/api/v1/tasks/${row.task_id}`, {method: 'DELETE'})
      if (!res.ok) {
        let detail = `请求失败 (${res.status})`
        try {
          const data = await res.json()
          if (data?.detail) detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)
        } catch { /* 响应体不是 JSON */
        }
        throw new Error(detail)
      }
      message.success('任务已删除')
      await loadTasks()
    },
  }
  showConfirm.value = true
}

async function runConfirm() {
  if (!confirmMeta.value) return
  confirmLoading.value = true
  try {
    await confirmMeta.value.run()
    showConfirm.value = false
  } catch (e: any) {
    message.error(`操作失败：${e.message || e}`)
  } finally {
    confirmLoading.value = false
  }
}

// ── 验证码提交 ──
const showCaptcha = ref(false)
const captchaTask = ref<TaskInfo | null>(null)
const captchaText = ref('')
const submittingCaptcha = ref(false)

function openCaptcha(row: TaskInfo) {
  captchaTask.value = row
  captchaText.value = ''
  showCaptcha.value = true
}

async function submitCaptcha() {
  if (!captchaTask.value) return
  const text = captchaText.value.trim()
  if (!text) {
    message.warning('请输入验证码')
    return
  }
  submittingCaptcha.value = true
  try {
    await apiPost(`/api/v1/tasks/${captchaTask.value.task_id}/captcha`, {captcha: text})
    message.success('验证码已提交，任务继续执行')
    showCaptcha.value = false
    await loadTasks()
  } catch (e: any) {
    message.error(`提交失败：${e.message || e}`)
  } finally {
    submittingCaptcha.value = false
  }
}

// ── 详情抽屉 ──
const showDetail = ref(false)
const detailTask = ref<TaskInfo | null>(null)

async function openDetail(row: TaskInfo) {
  try {
    detailTask.value = await apiGet<TaskInfo>(`/api/v1/tasks/${row.task_id}`)
  } catch {
    detailTask.value = row
  }
  showDetail.value = true
}

const ctxJson = computed(() =>
    detailTask.value ? JSON.stringify(detailTask.value.context, null, 2) : ''
)

// ── 展示辅助 ──
function shortId(id: string): string {
  return id.length > 24 ? `${id.slice(0, 10)}…${id.slice(-6)}` : id
}

function fmtTime(ts: number | null): string {
  if (!ts) return '—'
  const d = new Date(ts * 1000)
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}

function fmtIso(iso: string): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString('zh-CN', {hour12: false})
}

function fmtDuration(t: TaskInfo): string {
  if (!t.started_at) return '—'
  const end = t.finished_at ?? Date.now() / 1000
  const s = Math.max(0, Math.floor(end - t.started_at))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60
  const p = (n: number) => String(n).padStart(2, '0')
  return h > 0 ? `${h}:${p(m)}:${p(sec)}` : `${p(m)}:${p(sec)}`
}

// ── 表格列定义 ──
function rowKey(row: TaskInfo): string {
  return row.task_id
}

const columns: DataTableColumns<TaskInfo> = [
  {
    title: '任务',
    key: 'task_id',
    width: 190,
    render: row => h(NTooltip, {content: row.task_id}, {
      trigger: () => h(NText, {depth: 3, style: 'font-family: monospace; font-size: 12px;'},
          {default: () => shortId(row.task_id)}),
    }),
  },
  {
    title: '配置',
    key: 'config_name',
    width: 130,
    render: row => h(NText, {strong: true}, {default: () => row.config_name}),
  },
  {
    title: '状态',
    key: 'status',
    width: 110,
    render: row => h(NTag, {type: statusTagType(row), size: 'small', bordered: false},
        {default: () => STATUS_LABEL[row.status]}),
  },
  {
    title: '结果',
    key: 'result',
    width: 80,
    render: row => {
      if (row.status !== 'finished' || !row.result) {
        return h(NText, {depth: 3}, {default: () => '—'})
      }
      const meta = RESULT_META[row.result]
      return h(NTag, {type: meta.type, size: 'small', bordered: false}, {default: () => meta.label})
    },
  },
  {
    title: '倍速',
    key: 'playback_rate',
    width: 70,
    render: row => h(NText, {depth: 2}, {default: () => `${row.playback_rate}x`}),
  },
  {
    title: '开始时间',
    key: 'started_at',
    width: 165,
    render: row => h(NText, {depth: 3, style: 'font-size: 12px;'}, {default: () => fmtTime(row.started_at)}),
  },
  {
    title: '耗时',
    key: 'duration',
    width: 80,
    render: row => h(NText, {depth: 2}, {default: () => fmtDuration(row)}),
  },
  {
    title: '操作',
    key: 'actions',
    width: 235,
    fixed: 'right',
    render: row => h(NSpace, {size: 4}, {
      default: () => {
        const btns: VNode[] = []
        if (row.status === 'pending') {
          btns.push(h(NButton, {size: 'small', type: 'primary', onClick: () => startTask(row)},
              {default: () => '启动'}))
        }
        if (row.status === 'running') {
          btns.push(h(NButton, {size: 'small', type: 'warning', onClick: () => askStop(row)},
              {default: () => '停止'}))
        }
        if (row.status === 'waiting_captcha') {
          btns.push(h(NButton, {size: 'small', type: 'warning', onClick: () => openCaptcha(row)},
              {default: () => '提交验证码'}))
          btns.push(h(NButton, {size: 'small', onClick: () => askStop(row)}, {default: () => '停止'}))
        }
        btns.push(h(NButton, {size: 'small', quaternary: true, onClick: () => openDetail(row)},
            {default: () => '详情'}))
        if (row.status === 'finished') {
          btns.push(h(NButton, {size: 'small', type: 'error', ghost: true, onClick: () => askDelete(row)},
              {default: () => '删除'}))
        }
        return btns
      },
    }),
  },
]

// ── 轮询刷新 ──
let pollTimer: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  loadConfigs()
  loadTasks()
  pollTimer = setInterval(() => loadTasks(true), 3000)
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<template>
  <div class="onlineclass-container">
    <n-grid :cols="1" item-responsive responsive="screen" :x-gap="16" :y-gap="16">
      <n-grid-item span="1 m:2">
        <!-- 创建任务 -->
        <n-card title="新建刷课任务" class="card" :bordered="true">
          <n-form label-placement="top">
            <n-form-item label="流程配置" required>
              <n-select
                  v-model:value="configName"
                  :options="configOptions"
                  :loading="loadingConfigs"
                  placeholder="选择刷课流程（data/onlineclass/*.yaml）"
                  clearable
              />
              <n-alert
                  v-if="!loadingConfigs && configOptions.length === 0"
                  type="warning"
                  :show-icon="false"
                  style="margin-top: 8px; font-size: 12px;"
              >
                未发现流程配置。请在<b>配置下载</b>页面下载配置
              </n-alert>
            </n-form-item>
            <n-form-item label="账号" required>
              <n-input v-model:value="username" placeholder="登录账号"/>
            </n-form-item>
            <n-form-item label="密码" required>
              <n-input v-model:value="password" type="password" show-password-on="click" placeholder="登录密码"/>
            </n-form-item>
            <n-grid :cols="2" :x-gap="12">
              <n-grid-item>
                <n-form-item label="播放倍速">
                  <n-input-number v-model:value="playbackRate" :min="1" :step="1" style="width: 100%"/>
                </n-form-item>
              </n-grid-item>
              <n-grid-item>
                <n-form-item label="浏览器模式">
                  <n-select v-model:value="headlessMode" :options="headlessOptions"/>
                </n-form-item>
              </n-grid-item>
            </n-grid>
            <n-button type="primary" block :loading="creating" @click="handleCreate">
              <template #icon>
                <n-icon>
                  <PlusIcon/>
                </n-icon>
              </template>
              创建并启动任务
            </n-button>
          </n-form>
        </n-card>

        <!-- 流程配置列表 -->
        <n-card title="本地流程配置" class="card" :bordered="true">
          <n-empty v-if="!loadingConfigs && configs.length === 0" description="暂无本地流程配置" size="small"/>
          <n-spin v-else :show="loadingConfigs">
            <n-list>
              <n-list-item v-for="cfg in configs" :key="cfg.name">
                <template #prefix>
                  <n-icon :size="20" :depth="3">
                    <FileTextIcon/>
                  </n-icon>
                </template>
                <span class="cfg-name">{{ cfg.name }}.yaml</span>
                <n-text depth="3" style="font-size: 12px; margin-left: 8px;">
                  创建于 {{ fmtIso(cfg.created_at) }}
                </n-text>
              </n-list-item>
            </n-list>
          </n-spin>
        </n-card>
      </n-grid-item>

      <n-grid-item span="1 m:3">
        <!-- 任务中心 -->
        <n-card title="任务中心" class="card" :bordered="true">
          <template #header-extra>
            <n-space align="center" :size="8">
              <n-text depth="3" style="font-size: 12px;">每 3 秒自动刷新</n-text>
              <n-button quaternary size="small" @click="loadTasks()">
                <template #icon>
                  <n-icon>
                    <RefreshIcon/>
                  </n-icon>
                </template>
                刷新
              </n-button>
            </n-space>
          </template>
          <n-data-table
              :columns="columns"
              :data="tasks"
              :loading="loadingTasks"
              :row-key="rowKey"
              :scroll-x="1060"
              size="small"
              :bordered="false"
          />
        </n-card>
      </n-grid-item>
    </n-grid>

    <!-- 停止 / 删除确认 -->
    <n-modal v-model:show="showConfirm" :mask-closable="false">
      <n-card
          :title="confirmMeta?.title"
          :style="{width: '420px'}"
          :bordered="true"
          role="dialog"
          aria-modal="true"
      >
        <p style="margin: 0; color: #555; line-height: 1.6;">{{ confirmMeta?.content }}</p>
        <template #footer>
          <n-space justify="end">
            <n-button size="small" @click="showConfirm = false">取消</n-button>
            <n-button
                size="small"
                :type="confirmMeta?.danger ? 'error' : 'warning'"
                :loading="confirmLoading"
                @click="runConfirm"
            >
              {{ confirmMeta?.okText }}
            </n-button>
          </n-space>
        </template>
      </n-card>
    </n-modal>

    <!-- 验证码弹窗 -->
    <n-modal v-model:show="showCaptcha" :mask-closable="false">
      <n-card title="提交验证码" :style="{width: '420px'}" :bordered="true" role="dialog" aria-modal="true">
        <template #header-extra>
          <n-icon :size="20">
            <KeyIcon/>
          </n-icon>
        </template>
        <div v-if="captchaTask" style="text-align: center;">
          <p style="margin: 0 0 12px; font-size: 13px; color: #888;">
            任务「{{ captchaTask.config_name }}」执行中遇到验证码，请人工识别后提交
          </p>
          <img
              :src="captchaTask.captcha_image || ''"
              alt="验证码图片"
              style="max-width: 100%; border: 1px solid #eee; border-radius: 4px;"
          />
          <n-input
              v-model:value="captchaText"
              placeholder="请输入验证码"
              style="margin-top: 12px;"
              @keyup.enter="submitCaptcha"
          />
        </div>
        <template #footer>
          <n-space justify="end">
            <n-button size="small" @click="showCaptcha = false">取消</n-button>
            <n-button size="small" type="primary" :loading="submittingCaptcha" @click="submitCaptcha">
              提交验证码
            </n-button>
          </n-space>
        </template>
      </n-card>
    </n-modal>

    <!-- 详情抽屉 -->
    <n-drawer v-model:show="showDetail" :width="480">
      <n-drawer-content
          :title="detailTask ? `任务详情 · ${detailTask.config_name}` : '任务详情'"
          closable
      >
        <template v-if="detailTask">
          <n-descriptions label-placement="left" bordered :column="1" size="small">
            <n-descriptions-item label="任务 ID">
              <span style="font-family: monospace; font-size: 12px;">{{ detailTask.task_id }}</span>
            </n-descriptions-item>
            <n-descriptions-item label="配置路径">{{ detailTask.config_path }}</n-descriptions-item>
            <n-descriptions-item label="状态">
              <n-tag :type="statusTagType(detailTask)" size="small" :bordered="false">
                {{ STATUS_LABEL[detailTask.status] }}
              </n-tag>
            </n-descriptions-item>
            <n-descriptions-item label="结果">
              {{ detailTask.status === 'finished' && detailTask.result ? RESULT_META[detailTask.result].label : '—' }}
            </n-descriptions-item>
            <n-descriptions-item label="播放倍速">{{ detailTask.playback_rate }}x</n-descriptions-item>
            <n-descriptions-item label="开始时间">{{ fmtTime(detailTask.started_at) }}</n-descriptions-item>
            <n-descriptions-item label="结束时间">{{ fmtTime(detailTask.finished_at) }}</n-descriptions-item>
          </n-descriptions>

          <n-alert v-if="detailTask.error_message" type="error" title="错误信息" style="margin-top: 12px;">
            {{ detailTask.error_message }}
          </n-alert>

          <div style="margin-top: 16px;">
            <n-text depth="2" style="font-weight: 600;">执行上下文（实时进度数据）</n-text>
            <pre class="ctx-pre">{{ ctxJson }}</pre>
          </div>
        </template>
      </n-drawer-content>
    </n-drawer>
  </div>
</template>

<style scoped>
.onlineclass-container {
  height: 100%;
  overflow-y: auto;
  box-sizing: border-box;
}

.card {
  margin-bottom: 16px;
}

.cfg-name {
  font-weight: 600;
}

.ctx-pre {
  margin: 8px 0 0;
  padding: 10px 12px;
  background: #f6f7f9;
  border: 1px solid #eee;
  border-radius: 6px;
  font-size: 12px;
  line-height: 1.5;
  max-height: 320px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
