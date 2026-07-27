<script lang="ts" setup>
import {onMounted, ref} from 'vue'
import {useMessage} from 'naive-ui'
import {useRouter} from 'vue-router'
import {apiFetch} from '../config'

const message = useMessage()
const router = useRouter()

const loading = ref(false)
const showConfirm = ref(false)
const showRestartOverlay = ref(false)
const restartStatus = ref('')

const serverHost = ref('')
const serverPort = ref(8000)
const devMode = ref(false)
const pathOutput = ref('')
const pathData = ref('')
const pathLogs = ref('')

// 保存原始值，用于检测是否变更
let origHost = ''
let origPort = 8000
let origDevMode = false
let origOutput = ''
let origData = ''
let origLogs = ''

async function loadConfig() {
  loading.value = true
  try {
    const [cfgRes, devModeVal] = await Promise.all([
      apiFetch('/api/v1/config'),
      import('../config').then(m => m.getDevMode()).catch(() => false),
    ])

    const data = await cfgRes.json()
    const cfg = data.config
    serverHost.value = origHost = cfg.server.host
    serverPort.value = origPort = cfg.server.port
    devMode.value = origDevMode = cfg.dev_mode ?? devModeVal
    pathOutput.value = origOutput = cfg.paths.output
    pathData.value = origData = cfg.paths.data
    pathLogs.value = origLogs = cfg.paths.logs
  } catch (e: any) {
    message.error(`加载配置失败：${e.message}`)
  } finally {
    loading.value = false
  }
}

function hasChanges(): boolean {
  return serverHost.value !== origHost
      || serverPort.value !== origPort
      || devMode.value !== origDevMode
      || pathOutput.value !== origOutput
      || pathData.value !== origData
      || pathLogs.value !== origLogs
}

function handleSaveClick() {
  if (!hasChanges()) {
    message.info('未检测到配置变更')
    return
  }
  showConfirm.value = true
}

async function confirmSaveAndRestart() {
  showConfirm.value = false
  const needsRestart = serverHost.value !== origHost
      || serverPort.value !== origPort
      || devMode.value !== origDevMode

  try {
    const body = {
      server: {host: serverHost.value, port: serverPort.value},
      paths: {output: pathOutput.value, data: pathData.value, logs: pathLogs.value},
      dev_mode: devMode.value,
    }
    const res = await apiFetch('/api/v1/config', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body),
    })
    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail || '保存失败')
    }
  } catch (e: any) {
    message.error(`保存配置失败：${e.message}`)
    return
  }

  // 保存成功，更新原始值
  origHost = serverHost.value
  origPort = serverPort.value
  origDevMode = devMode.value
  origOutput = pathOutput.value
  origData = pathData.value
  origLogs = pathLogs.value

  if (!needsRestart) {
    message.success('配置已保存')
    router.push({name: 'home'})
    return
  }

  // 需要重启 → 显示加载遮罩
  showRestartOverlay.value = true

  try {
    const {invoke} = await import('@tauri-apps/api/core')

    restartStatus.value = '正在停止后端…'
    await invoke('kill_backend')
    await new Promise(r => setTimeout(r, 500))

    restartStatus.value = '正在启动后端…'
    await invoke('start_backend')

    restartStatus.value = '等待后端就绪…'
    const newUrl = `http://${serverHost.value}:${serverPort.value}`
    for (let i = 0; i < 30; i++) {
      await new Promise(r => setTimeout(r, 1000))
      try {
        const res = await fetch(`${newUrl}/health`, {signal: AbortSignal.timeout(1500)})
        if (res.ok && (await res.json()).status === 'ok') {
          restartStatus.value = '就绪！'
          await new Promise(r => setTimeout(r, 500))
          router.push({name: 'home'})
          return
        }
      } catch { /* 等待中 */
      }
    }
    message.warning('后端重启超时，请手动刷新')
  } catch (e: any) {
    message.error(`重启失败：${e.message}`)
  } finally {
    showRestartOverlay.value = false
  }
}

onMounted(loadConfig)
</script>

<template>
  <div class="setting-container">
    <n-card title="系统设置" style="padding-top: 1rem;height: 100vh">
      <n-form v-if="!loading" label-placement="left" label-width="120">
        <n-divider title-position="left">服务器</n-divider>
        <n-form-item label="监听地址">
          <n-input v-model:value="serverHost" placeholder="127.0.0.1"/>
        </n-form-item>
        <n-form-item label="监听端口">
          <n-input-number v-model:value="serverPort" :max="65535" :min="1" style="width: 160px"/>
        </n-form-item>
        <n-form-item label="开发者模式">
          <n-switch v-model:value="devMode"/>
          <n-text depth="3" style="margin-left: 8px; font-size: 13px;">
            {{ devMode ? '开启（跳过 token 验证）' : '关闭' }}
          </n-text>
        </n-form-item>

        <n-divider title-position="left">路径</n-divider>
        <n-form-item label="输出目录">
          <n-input v-model:value="pathOutput" placeholder="output"/>
        </n-form-item>
        <n-form-item label="数据目录">
          <n-input v-model:value="pathData" placeholder="data"/>
        </n-form-item>
        <n-form-item label="日志目录">
          <n-input v-model:value="pathLogs" placeholder="logs"/>
        </n-form-item>

        <n-form-item>
          <n-button block type="primary" @click="handleSaveClick">
            保存配置
          </n-button>
        </n-form-item>
      </n-form>
      <n-spin v-else size="large" style="display: flex; justify-content: center; padding: 48px 0;"/>
    </n-card>

    <!-- 二次确认 -->
    <n-modal
        v-model:show="showConfirm"
        :mask-closable="false"
        :negative-text="'取消'"
        :positive-text="'确认'"
        preset="dialog"
        title="确认保存"
        @positive-click="confirmSaveAndRestart"
        @negative-click="showConfirm = false"
    >
      {{
        serverHost !== origHost || serverPort !== origPort || devMode !== origDevMode
            ? '服务器配置已变更，保存后将重启后端。确认？'
            : '确认保存配置？'
      }}
    </n-modal>

    <!-- 重启遮罩 -->
    <n-modal
        v-model:show="showRestartOverlay"
        :closeable="false"
        :mask-closable="false"
        style="width: 360px;"
    >
      <n-card :bordered="false" style="text-align: center; padding: 32px 0;">
        <n-spin size="large"/>
        <p style="margin-top: 20px; font-size: 15px; color: #888;">
          {{ restartStatus }}
        </p>
      </n-card>
    </n-modal>
  </div>
</template>
