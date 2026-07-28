<script lang="ts" setup>
import {ref, computed, onMounted} from 'vue'
import {type UploadFileInfo, useMessage} from 'naive-ui'
import {api, getToken} from '../../config'

const props = withDefaults(defineProps<{
  cardTitle?: string
  apiEndpoint?: string
}>(), {
  cardTitle: 'PDF 压缩',
  apiEndpoint: ''
})

const actualApiEndpoint = ref(props.apiEndpoint)
onMounted(async () => {
  if (!props.apiEndpoint) {
    actualApiEndpoint.value = await api('/api/v1/pdf/compress')
  }
})

const message = useMessage()

// ── 预设定义 ────────────────────────────────────────────────────────────────

interface PresetDef {
  key: string
  icon: string
  label: string
  desc: string
  warning: string
}

const presets: PresetDef[] = [
  {
    key: 'mild',
    icon: '📄',
    label: '轻度',
    desc: '质量优先，略微减小体积',
    warning: '',
  },
  {
    key: 'moderate',
    icon: '⚖️',
    label: '中度',
    desc: '平衡质量和体积，适合日常使用',
    warning: '',
  },
  {
    key: 'aggressive',
    icon: '🗜️',
    label: '重度',
    desc: '大幅压缩，适合邮件发送',
    warning: '⚠️ 图像质量会有可见损失',
  },
  {
    key: 'extreme',
    icon: '⚡',
    label: '极度',
    desc: '极致压缩，适合存储空间极度紧张',
    warning: '⚠️⚠️ 图像质量明显下降，仅限空间紧张时使用',
  },
]

// ── 预设对应的默认高级选项 ─────────────────────────────────────────────────

const presetDefaults: Record<string, any> = {
  mild: {stream_level: 2, image_quality: null, convert_all_to_jpg: false, max_dimension: null, remove_metadata: false},
  moderate: {stream_level: 3, image_quality: 70, convert_all_to_jpg: false, max_dimension: null, remove_metadata: true},
  aggressive: {
    stream_level: 3,
    image_quality: 50,
    convert_all_to_jpg: true,
    max_dimension: 1600,
    remove_metadata: true
  },
  extreme: {stream_level: 3, image_quality: 30, convert_all_to_jpg: true, max_dimension: 800, remove_metadata: true},
}

// ── 状态 ────────────────────────────────────────────────────────────────────

const selectedPreset = ref('moderate')

const fileName = ref('')
const pdfFile = ref<File | null>(null)
const pdfFileList = ref<UploadFileInfo[]>([])
const loading = ref(false)
const showModal = ref(false)
const outputPath = ref('')
const expandedNames = ref<string[]>([])

// ── 高级选项覆写（仅当用户修改时非空） ─────────────────────────────────────

const advStreamLevel = ref<number | null>(null)
const advImageQuality = ref<number | null>(null)
const advConvertAll = ref<boolean | null>(null)
const advMaxDimension = ref<number | null>(null)
const advRemoveMeta = ref<boolean | null>(null)

// 当前预设的默认值（用于重置高级选项时的基准）
const currentPresetDefaults = computed(() => presetDefaults[selectedPreset.value])

const selectedWarning = computed(() => {
  return presets.find(p => p.key === selectedPreset.value)?.warning || ''
})

// ── 选择预设时重置高级选项 ─────────────────────────────────────────────────

function selectPreset(key: string) {
  selectedPreset.value = key
  expandedNames.value = []
  advStreamLevel.value = null
  advImageQuality.value = null
  advConvertAll.value = null
  advMaxDimension.value = null
  advRemoveMeta.value = null
}

// ── 构建发送给后端的高级选项 JSON ──────────────────────────────────────────

function buildAdvancedOptionsJson(): string | null {
  const overrides: Record<string, any> = {}
  const defs = currentPresetDefaults.value

  if (advStreamLevel.value !== null && advStreamLevel.value !== defs.stream_level) {
    overrides.stream_level = advStreamLevel.value
  }
  if (advImageQuality.value !== null && advImageQuality.value !== defs.image_quality) {
    overrides.image_quality = advImageQuality.value
  }
  if (advConvertAll.value !== null && advConvertAll.value !== defs.convert_all_to_jpg) {
    overrides.convert_all_to_jpg = advConvertAll.value
  }
  if (advMaxDimension.value !== null && advMaxDimension.value !== defs.max_dimension) {
    overrides.max_dimension = advMaxDimension.value
  }
  if (advRemoveMeta.value !== null && advRemoveMeta.value !== defs.remove_metadata) {
    overrides.remove_metadata = advRemoveMeta.value
  }

  return Object.keys(overrides).length > 0 ? JSON.stringify(overrides) : null
}

// ── 文件操作 ────────────────────────────────────────────────────────────────

function handlePdfChange({fileList}: { fileList: UploadFileInfo[] }) {
  pdfFileList.value = fileList
  if (fileList.length > 0 && fileList[0].file) {
    pdfFile.value = fileList[0].file
  } else {
    pdfFile.value = null
  }
}

const pdfCustomRequest = ({file, onFinish}: { file: UploadFileInfo; onFinish: () => void }) => {
  if (file.file) {
    pdfFile.value = file.file
  }
  onFinish()
}

// ── 提交 ────────────────────────────────────────────────────────────────────

async function handleSubmit() {
  if (!fileName.value.trim()) {
    message.warning('请输入文件名')
    return
  }
  if (!pdfFile.value) {
    message.warning('请上传PDF文件')
    return
  }

  loading.value = true
  try {
    const formData = new FormData()
    formData.append('pdf_file', pdfFile.value)
    formData.append('file_name', fileName.value.trim())
    formData.append('preset', selectedPreset.value)

    const advancedJson = buildAdvancedOptionsJson()
    if (advancedJson) {
      formData.append('advanced_options', advancedJson)
    }

    const token = await getToken()
    const headers = new Headers()
    if (token) headers.set('Authorization', `Bearer ${token}`)

    const response = await fetch(actualApiEndpoint.value, {
      method: 'POST',
      headers,
      body: formData,
    })

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || '请求失败')
    }

    const result = await response.json()
    outputPath.value = result.output_path || '压缩成功'
    message.success('压缩成功！')

    // 清空表单
    fileName.value = ''
    pdfFile.value = null
    pdfFileList.value = []
    showModal.value = true
  } catch (error: any) {
    message.error(`压缩失败：${error.message}`)
  } finally {
    loading.value = false
  }
}

// ── 模态框操作 ──────────────────────────────────────────────────────────────

function getParentDir(path: string): string {
  const lastSep = Math.max(path.lastIndexOf('\\'), path.lastIndexOf('/'))
  return lastSep > -1 ? path.slice(0, lastSep) : path
}

async function openFile() {
  try {
    const {openPath} = await import('@tauri-apps/plugin-opener')
    await openPath(outputPath.value)
  } catch (e: any) {
    message.error(`打开文件失败：${e.message || e}`)
  }
}

async function openFolder() {
  try {
    const {openPath} = await import('@tauri-apps/plugin-opener')
    await openPath(getParentDir(outputPath.value))
  } catch (e: any) {
    message.error(`打开文件夹失败：${e.message || e}`)
  }
}

function closeModal() {
  showModal.value = false
}

function clearFile() {
  pdfFile.value = null
  pdfFileList.value = []
}

// ── 流压缩级别文案 ──────────────────────────────────────────────────────────

const streamLevelOptions = [
  {label: '关闭 (0)', value: 0},
  {label: '基本 (1)', value: 1},
  {label: '中等 (2)', value: 2},
  {label: '最高 (3)', value: 3},
]
</script>

<template>
  <div class="pdf-compress-container">
    <!-- 成功模态框 -->
    <n-modal
        v-model:show="showModal"
        :closeable="false"
        :mask-closable="false"
        negative-text=""
        positive-text=""
        preset="dialog"
        title="压缩成功"
    >
      <template #default>
        <div style="text-align: center; padding: 8px 0;">
          <n-text depth="3" style="font-size: 13px; word-break: break-all;">
            {{ outputPath }}
          </n-text>
        </div>
        <div style="display: flex; gap: 12px; justify-content: center; margin-top: 16px;">
          <n-button type="primary" @click="openFolder">
            <template #icon>
              <n-icon>
                <svg fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                  <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
                </svg>
              </n-icon>
            </template>
            打开文件夹
          </n-button>
          <n-button type="success" @click="openFile">
            <template #icon>
              <n-icon>
                <svg fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                  <polyline points="14 2 14 8 20 8"/>
                  <line x1="12" x2="12" y1="18" y2="12"/>
                  <line x1="9" x2="15" y1="15" y2="15"/>
                </svg>
              </n-icon>
            </template>
            打开文件
          </n-button>
          <n-button @click="closeModal">关闭</n-button>
        </div>
      </template>
    </n-modal>

    <n-card :title="cardTitle" style="height: 100vh; padding-top: 1rem">
      <n-form label-placement="top">
        <!-- 文件名 -->
        <n-form-item label="输出文件名" required>
          <n-input
              v-model:value="fileName"
              placeholder="请输入压缩后的文件名（不含扩展名）"
              clearable
          />
        </n-form-item>

        <!-- PDF 上传 -->
        <n-form-item label="PDF 文件" required>
          <n-upload
              :custom-request="pdfCustomRequest"
              :file-list="pdfFileList"
              :max="1"
              accept=".pdf"
              dragger
              @change="handlePdfChange"
          >
            <n-upload-dragger>
              <div style="margin-bottom: 12px">
                <n-icon :depth="3" size="48">
                  <svg fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                    <polyline points="14 2 14 8 20 8"/>
                    <line x1="12" x2="12" y1="18" y2="12"/>
                    <line x1="9" x2="15" y1="15" y2="15"/>
                  </svg>
                </n-icon>
              </div>
              <n-text style="font-size: 16px">点击或者拖动文件到该区域来上传</n-text>
              <n-p depth="3" style="margin: 8px 0 0 0">仅支持单个 .pdf 格式文件</n-p>
              <n-p v-if="pdfFile" depth="2" style="margin: 8px 0 0 0; color: #18a058;">
                已选择：{{ pdfFile.name }}
              </n-p>
            </n-upload-dragger>
          </n-upload>
        </n-form-item>

        <!-- 预设方案 -->
        <n-form-item label="压缩方案">
          <div class="preset-grid">
            <div
                v-for="p in presets"
                :key="p.key"
                class="preset-card"
                :class="{ active: selectedPreset === p.key }"
                @click="selectPreset(p.key)"
            >
              <div class="preset-icon">{{ p.icon }}</div>
              <div class="preset-label">{{ p.label }}</div>
              <div class="preset-desc">{{ p.desc }}</div>
              <div v-if="p.warning && selectedPreset === p.key" class="preset-warning">
                {{ p.warning }}
              </div>
            </div>
          </div>
        </n-form-item>

        <!-- 预设警告 -->
        <n-alert v-if="selectedWarning" type="warning" :bordered="false" style="margin-bottom: 16px;">
          {{ selectedWarning }}
        </n-alert>

        <!-- 高级选项 -->
        <n-collapse v-model:expanded-names="expandedNames">
          <n-collapse-item title="高级选项" name="advanced">
            <n-space vertical>
              <n-form-item label="流压缩级别">
                <n-radio-group v-model:value="advStreamLevel" :default-value="null">
                  <n-radio-button
                      v-for="opt in streamLevelOptions"
                      :key="opt.value"
                      :value="opt.value"
                      :label="opt.label"
                  />
                </n-radio-group>
                <n-text v-if="advStreamLevel === null" depth="3" style="font-size: 12px; margin-left: 8px;">
                  （使用预设值）
                </n-text>
              </n-form-item>

              <n-form-item label="图像质量 (JPEG)">
                <n-slider
                    v-model:value="advImageQuality"
                    :min="10"
                    :max="100"
                    :step="5"
                    style="width: 300px;"
                />
                <n-text style="margin-left: 12px; min-width: 60px;">
                  {{ advImageQuality !== null ? advImageQuality : '预设' }}
                </n-text>
              </n-form-item>

              <n-checkbox v-model:checked="advConvertAll" :checked-value="true" :unchecked-value="null">
                全转 JPG（透明背景可能变白）
              </n-checkbox>

              <n-form-item label="限制图片分辨率">
                <n-input-number
                    v-model:value="advMaxDimension"
                    :min="200"
                    :max="5000"
                    :step="100"
                    placeholder="不限"
                    clearable
                    style="width: 160px;"
                />
                <n-text depth="3" style="margin-left: 8px; font-size: 12px;">像素（最长边）</n-text>
              </n-form-item>

              <n-checkbox v-model:checked="advRemoveMeta" :checked-value="true" :unchecked-value="null">
                移除文档信息（作者、标题等元数据）
              </n-checkbox>
            </n-space>
          </n-collapse-item>
        </n-collapse>

        <!-- 提交按钮 -->
        <n-form-item style="margin-top: 16px;">
          <n-space style="width: 100%;" vertical>
            <n-button
                :loading="loading"
                block
                class="submit-button"
                type="info"
                @click="handleSubmit"
            >
              压缩
            </n-button>
            <n-button
                v-if="pdfFile"
                block
                quaternary
                size="small"
                @click="clearFile"
            >
              重新选择文件
            </n-button>
          </n-space>
        </n-form-item>
      </n-form>
    </n-card>
  </div>
</template>

<style scoped>
.pdf-compress-container {
  margin: 0;
  padding: 0;
}

.submit-button {
  height: 2rem;
  font-size: 16px;
}

.preset-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  width: 100%;
}

.preset-card {
  border: 2px solid #e8e8e8;
  border-radius: 8px;
  padding: 12px;
  cursor: pointer;
  text-align: center;
  transition: all 0.2s;
  background: #fafafa;
  user-select: none;
}

.preset-card:hover {
  border-color: #d9d9d9;
  background: #f5f5f5;
}

.preset-card.active {
  border-color: #1890ff;
  background: #f0f7ff;
}

.preset-icon {
  font-size: 28px;
  margin-bottom: 4px;
}

.preset-label {
  font-weight: 600;
  font-size: 15px;
  margin-bottom: 4px;
}

.preset-desc {
  font-size: 12px;
  color: #666;
  line-height: 1.4;
}

.preset-warning {
  margin-top: 6px;
  font-size: 11px;
  color: #fa8c16;
  line-height: 1.3;
}

@media (max-width: 768px) {
  .preset-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
