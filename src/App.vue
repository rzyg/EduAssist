<template>
  <StartupScreen
      v-if="initializing"
      :status="initStatus"
      :error="initFailed"
      @retry="retryInit"
  />
  <MainLayout v-else />
</template>

<script setup lang="ts">
import {ref, onMounted} from 'vue'
import {getApiBase} from './config'
import StartupScreen from './components/StartupScreen.vue'
import MainLayout from './components/MainLayout.vue'

const initializing = ref(true)
const initFailed = ref(false)
const initStatus = ref('')
let backendUrl = 'http://127.0.0.1:8000'

async function checkAlive(): Promise<boolean> {
  try {
    const res = await fetch(`${backendUrl}/health`, {signal: AbortSignal.timeout(1500)})
    return res.ok && (await res.json()).status === 'ok'
  } catch { return false }
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
      invoke('start_backend').catch(() => {})
    } catch { /* 非 Tauri 环境 */ }
  }

  // 2. 至少播放 1.5s 动画（无论后端状态）
  initStatus.value = '加载中…'
  await new Promise(r => setTimeout(r, 1500))

  // 3. 1.5s 后检测是否在线
  if (await checkAlive()) {
    initializing.value = false
    return
  }

  // 4. 不在线 → 继续等待
  initStatus.value = '正在启动后端…'
  for (let i = 0; i < 15; i++) {
    await new Promise(r => setTimeout(r, 1000))
    if (await checkAlive()) {
      initializing.value = false
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
</script>
