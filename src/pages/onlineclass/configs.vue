<script lang="ts" setup>
import {computed, h, onMounted, ref} from 'vue'
import {useMessage} from 'naive-ui'
import type {DataTableColumns} from 'naive-ui'
import {
  NButton, NSpace, NTag, NText
} from 'naive-ui'
import {
  Download as DownloadIcon,
  Refresh as RefreshIcon
} from '@vicons/tabler'
import {apiGet, apiPost} from '../../config'

const message = useMessage()

// ── 类型 ──
interface OnlineConfig {
  name: string
  updated_at: string | null
}

interface LocalConfig {
  name: string
  created_at: string
}

interface DownloadResult {
  downloaded: {name: string; path: string}[]
  failed: {name: string; error: string}[]
}

// ── 数据 ──
const onlineConfigs = ref<OnlineConfig[]>([])
const localConfigs = ref<LocalConfig[]>([])
const loadingOnline = ref(false)
const loadingLocal = ref(false)
const downloading = ref(false)
const checkedNames = ref<string[]>([])

const localNames = computed(() => new Set(localConfigs.value.map(c => c.name)))

// 合并下载状态,便于表格展示「已下载 / 未下载」
const rows = computed<Array<OnlineConfig & {downloaded: boolean}>>(() =>
    onlineConfigs.value.map(c => ({...c, downloaded: localNames.value.has(c.name)}))
)

// ── 加载 ──
async function loadOnlineConfigs(silent = false) {
  if (!silent) loadingOnline.value = true
  try {
    onlineConfigs.value = await apiGet<OnlineConfig[]>('/api/v1/configs/online')
  } catch (e: any) {
    message.error(`获取在线配置列表失败：${e.message || e}`)
  } finally {
    loadingOnline.value = false
  }
}

async function loadLocalConfigs() {
  loadingLocal.value = true
  try {
    localConfigs.value = await apiGet<LocalConfig[]>('/api/v1/configs/local')
  } catch (e: any) {
    message.error(`加载本地配置失败：${e.message || e}`)
  } finally {
    loadingLocal.value = false
  }
}

// ── 下载 ──
async function handleDownload() {
  const names = checkedNames.value
  if (names.length === 0) {
    message.warning('请先勾选要下载的配置')
    return
  }
  downloading.value = true
  try {
    const res = await apiPost<DownloadResult>('/api/v1/configs/download', {names})
    if (res.downloaded.length > 0) {
      message.success(`已下载 ${res.downloaded.length} 个配置到 data/onlineclass/`)
    }
    if (res.failed.length > 0) {
      const detail = res.failed.map(f => `${f.name}（${f.error}）`).join('；')
      message.error(`下载失败 ${res.failed.length} 个：${detail}`)
    }
    if (res.downloaded.length === 0 && res.failed.length === 0) {
      message.info('未下载任何配置')
    }
    checkedNames.value = []
    await loadLocalConfigs()
  } catch (e: any) {
    message.error(`下载失败：${e.message || e}`)
  } finally {
    downloading.value = false
  }
}

// ── 展示辅助 ──
function fmtIso(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString('zh-CN', {hour12: false})
}

function rowKey(row: OnlineConfig): string {
  return row.name
}

function onCheckedChange(keys: Array<string | number>) {
  checkedNames.value = keys.map(String)
}

// ── 表格列 ──
const columns: DataTableColumns<OnlineConfig & {downloaded: boolean}> = [
  {type: 'selection', width: 44},
  {
    title: '配置名称',
    key: 'name',
    render: row => h(NText, {strong: true}, {default: () => row.name}),
  },
  {
    title: '更新时间',
    key: 'updated_at',
    width: 190,
    render: row => h(NText, {depth: 3, style: 'font-size: 12px;'},
        {default: () => fmtIso(row.updated_at)}),
  },
  {
    title: '状态',
    key: 'downloaded',
    width: 100,
    render: row => row.downloaded
        ? h(NTag, {type: 'success', size: 'small', bordered: false}, {default: () => '已下载'})
        : h(NTag, {size: 'small', bordered: false}, {default: () => '未下载'}),
  },
]

onMounted(() => {
  loadOnlineConfigs()
  loadLocalConfigs()
})
</script>

<template>
  <div class="configs-container">
    <n-card title="在线配置下载" class="card" :bordered="true">
      <template #header-extra>
        <n-space align="center" :size="8">
          <n-text depth="3" style="font-size: 12px;">已勾选 {{ checkedNames.length }} 个</n-text>
          <n-button quaternary size="small" :loading="loadingOnline" @click="loadOnlineConfigs()">
            <template #icon>
              <n-icon>
                <RefreshIcon/>
              </n-icon>
            </template>
            刷新
          </n-button>
          <n-button
              type="primary"
              size="small"
              :loading="downloading"
              :disabled="checkedNames.length === 0"
              @click="handleDownload"
          >
            <template #icon>
              <n-icon>
                <DownloadIcon/>
              </n-icon>
            </template>
            下载选中
          </n-button>
        </n-space>
      </template>

      <n-alert type="info" :show-icon="false" style="margin-bottom: 12px; font-size: 12px;">
        从在线配置仓库拉取剧本列表，勾选后点击「下载选中」，将自动保存到
        <b>data/onlineclass/</b> 目录（目录不存在会自动创建）。
      </n-alert>

      <n-data-table
          :columns="columns"
          :data="rows"
          :loading="loadingOnline"
          :row-key="rowKey"
          :checked-row-keys="checkedNames"
          :scroll-x="520"
          :pagination="rows.length > 10 ? {pageSize: 10} : false"
          size="small"
          :bordered="false"
          @update:checked-row-keys="onCheckedChange"
      >
        <template #empty>
          <n-empty
              v-if="loadingOnline"
              description="正在获取在线配置列表…"
              size="small"
          />
          <n-empty v-else description="在线仓库暂无配置" size="small"/>
        </template>
      </n-data-table>
    </n-card>
  </div>
</template>

<style scoped>
.configs-container {
  height: 100%;
  overflow-y: auto;
  box-sizing: border-box;
}

.card {
  margin-bottom: 16px;
}
</style>
