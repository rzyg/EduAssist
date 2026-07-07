<template>
  <StartupScreen v-if="initializing" :status="initStatus" />
  <MainLayout v-else />
</template>

<script setup lang="ts">
import {ref, onMounted} from 'vue'
import {createDiscreteApi} from 'naive-ui'
import {API_BASE} from './config'
import StartupScreen from './components/StartupScreen.vue'
import MainLayout from './components/MainLayout.vue'

const {message} = createDiscreteApi(['message'])

const initializing = ref(true)
const initStatus = ref('')

async function checkAlive(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/health`, {signal: AbortSignal.timeout(1500)})
    return res.ok && (await res.json()).status === 'ok'
  } catch { return false }
}

async function initApp() {
  initStatus.value = '正在连接后端…'
  for (let i = 0; i < 3; i++) {
    if (await checkAlive()) { initializing.value = false; return }
    await new Promise(r => setTimeout(r, 500))
  }

  initStatus.value = '正在启动后端…'
  try {
    const {invoke} = await import('@tauri-apps/api/core')
    await invoke('start_backend')
  } catch {
    initializing.value = false
    message.warning('后端未启动，请手动运行 python core/main.py')
    return
  }

  initStatus.value = '等待后端就绪…'
  for (let i = 0; i < 30; i++) {
    await new Promise(r => setTimeout(r, 1000))
    if (await checkAlive()) {
      initStatus.value = '就绪！'
      await new Promise(r => setTimeout(r, 300))
      initializing.value = false
      return
    }
  }

  initializing.value = false
  message.warning('后端启动超时，请手动检查')
}

onMounted(initApp)
</script>
