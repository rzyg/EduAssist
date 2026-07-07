<script setup lang="ts">
import {ref, onMounted} from 'vue'
import {useMessage} from 'naive-ui'
import {useRouter} from 'vue-router'

const message = useMessage()
const router = useRouter()

const loading = ref(false)

const serverHost = ref('')
const serverPort = ref(8000)
const pathOutput = ref('')
const pathData = ref('')
const pathLogs = ref('')

async function loadConfig() {
  loading.value = true
  try {
    const res = await fetch('http://127.0.0.1:8000/api/v1/config')
    if (!res.ok) throw new Error('获取配置失败')
    const data = await res.json()
    const cfg = data.config
    serverHost.value = cfg.server.host
    serverPort.value = cfg.server.port
    pathOutput.value = cfg.paths.output
    pathData.value = cfg.paths.data
    pathLogs.value = cfg.paths.logs
  } catch (e: any) {
    message.error(`加载配置失败：${e.message}`)
  } finally {
    loading.value = false
  }
}

async function handleSave() {
  try {
    const body = {
      server: {host: serverHost.value, port: serverPort.value},
      paths: {output: pathOutput.value, data: pathData.value, logs: pathLogs.value},
    }
    const res = await fetch('http://127.0.0.1:8000/api/v1/config', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body),
    })
    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail || '保存失败')
    }
    message.success('配置已保存')
    router.push({name: 'home'})
  } catch (e: any) {
    message.error(`保存配置失败：${e.message}`)
  }
}

onMounted(loadConfig)
</script>

<template>
  <div class="setting-container">
    <n-card title="系统设置">
      <n-form label-placement="left" label-width="120" v-if="!loading">
        <n-divider title-position="left">服务器</n-divider>
        <n-form-item label="监听地址">
          <n-input v-model:value="serverHost" placeholder="127.0.0.1"/>
        </n-form-item>
        <n-form-item label="监听端口">
          <n-input-number v-model:value="serverPort" :min="1" :max="65535" style="width: 160px"/>
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
          <n-button type="primary" @click="handleSave" block>
            保存配置
          </n-button>
        </n-form-item>
      </n-form>
      <n-spin v-else size="large" style="display: flex; justify-content: center; padding: 48px 0;"/>
    </n-card>
  </div>
</template>

<style scoped>
.setting-container {
  max-width: 640px;
  margin: 0 auto;
}
</style>
