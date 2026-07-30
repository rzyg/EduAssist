<template>
  <transition mode="out-in" name="startup-fade">
    <StartupScreen
        v-if="initializing"
        :error="initFailed"
        :status="initStatus"
        @retry="retryInit"
    />
    <MainLayout v-else/>
  </transition>

  <!-- 更新弹窗 -->
  <n-modal
      v-model:show="showUpdateModal"
      title="发现新版本"
      preset="dialog"
      positive-text="立即更新"
      negative-text="稍后提醒"
      :mask-closable="false"
      @positive-click="handleUpdate"
      @negative-click="showUpdateModal = false"
  >
    <template #default>
      <div style="margin-bottom: 12px;">
        <span style="font-weight: 600; font-size: 16px;">版本 {{ updateInfo?.version }}</span>
        <span style="margin-left: 8px; color: #888; font-size: 13px;">当前版本 {{ currentVersion }}</span>
      </div>
      <div style="white-space: pre-wrap; font-size: 13px; line-height: 1.6; color: #555;">{{ updateInfo?.changelog }}</div>
      <div v-if="downloading" style="margin-top: 12px; color: #1890ff;">正在下载更新…</div>
    </template>
  </n-modal>
</template>

<script lang="ts" setup>
import {onMounted, ref, nextTick} from 'vue'
import {getApiBase} from './config'
import StartupScreen from './components/StartupScreen.vue'
import MainLayout from './components/MainLayout.vue'

const initializing = ref(true)
const initFailed = ref(false)
const initStatus = ref('')
let backendUrl = 'http://127.0.0.1:8000'

// ── 自动更新 ──────────────────────────────────────────────────────────
interface UpdateInfo {
  version: string
  changelog: string
  download_url: string
}
const currentVersion = ref('')
const updateInfo = ref<UpdateInfo | null>(null)
const showUpdateModal = ref(false)
const downloading = ref(false)
const VERSION_CHECK_URL = 'https://alist.bbts.fun/d/下班工具箱/.version.json'

async function checkForUpdate() {
  try {
    const {invoke} = await import('@tauri-apps/api/core')
    currentVersion.value = await invoke('get_app_version') as string
    const res = await fetch(VERSION_CHECK_URL, {signal: AbortSignal.timeout(5000)})
    if (!res.ok) return
    const remote: UpdateInfo = await res.json()
    if (remote.version && compareVersions(remote.version, currentVersion.value) > 0) {
      updateInfo.value = remote
      showUpdateModal.value = true
    }
  } catch { /* 静默忽略 */ }
}

function compareVersions(a: string, b: string): number {
  const pa = a.split('.').map(Number), pb = b.split('.').map(Number)
  for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
    const na = pa[i] || 0, nb = pb[i] || 0
    if (na > nb) return 1
    if (na < nb) return -1
  }
  return 0
}

async function handleUpdate() {
  if (!updateInfo.value?.download_url) return
  downloading.value = true
  try {
    const {invoke} = await import('@tauri-apps/api/core')
    await invoke('download_and_install', {url: updateInfo.value.download_url})
  } catch (e) {
    console.error('更新失败:', e)
    downloading.value = false
    showUpdateModal.value = false
  }
}

async function checkAlive(): Promise<boolean> {
  try {
    const res = await fetch(`${backendUrl}/health`, {signal: AbortSignal.timeout(1500)})
    return res.ok && (await res.json()).status === 'ok'
  } catch {
    return false
  }
}

async function doInit() {
  initFailed.value = false

  // 0. 从 config.yaml 获取后端真实地址
  backendUrl = await getApiBase()

  // 1. 快速检测，不在线才尝试拉起（不阻塞动画）
  const wasAlive = await checkAlive()
  if (!wasAlive) {
    try {
      const {invoke} = await import('@tauri-apps/api/core')
      invoke('start_backend').catch(() => {
      })
    } catch { /* 非 Tauri 环境 */
    }
  }

  // 2. 至少播放 1.5s 动画（无论后端状态）
  initStatus.value = '加载中…'
  await new Promise(r => setTimeout(r, 1500))

  // 3. 1.5s 后检测是否在线
  if (await checkAlive()) {
    initializing.value = false
    nextTick(() => checkForUpdate())
    return
  }

  // 4. 不在线 → 继续等待
  initStatus.value = '正在启动后端…'
  for (let i = 0; i < 15; i++) {
    await new Promise(r => setTimeout(r, 1000))
    if (await checkAlive()) {
      initializing.value = false
      nextTick(() => checkForUpdate())
      return
    }
  }

  // 5. 超时 → 显示重试按钮
  initStatus.value = '后端启动失败，请确认后端已启动'
  initFailed.value = true
}

function retryInit() {
  doInit()
}

onMounted(doInit)

// ── 全局禁止右键菜单 ────────────────────────────────────────────
onMounted(() => document.addEventListener('contextmenu', e => e.preventDefault()))
</script>

<style>
img {
  -webkit-user-drag: none;
  user-select: none;
}

.startup-fade-enter-active,
.startup-fade-leave-active {
  transition: opacity 0.5s ease;
}

.startup-fade-enter-from,
.startup-fade-leave-to {
  opacity: 0;
}
</style>
