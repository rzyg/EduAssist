<script lang="ts" setup>
import {ref, onMounted} from 'vue'
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

const fileName = ref('')
const compressionLevel = ref('medium')
const pdfFile = ref<File | null>(null)
const pdfFileList = ref<UploadFileInfo[]>([])
const loading = ref(false)
const showModal = ref(false)
const outputPath = ref('')

// 压缩等级选项
const levelOptions = [
  {label: '低压缩（速度快）', value: 'low'},
  {label: '中压缩（推荐）', value: 'medium'},
  {label: '高压缩（体积小）', value: 'high'},
]

// 处理文件上传变化
function handlePdfChange({fileList}: { fileList: UploadFileInfo[] }) {
  pdfFileList.value = fileList
  if (fileList.length > 0 && fileList[0].file) {
    pdfFile.value = fileList[0].file
  } else {
    pdfFile.value = null
  }
}

// 自定义上传请求（阻止默认上传行为）
const pdfCustomRequest = ({file, onFinish}: { file: UploadFileInfo; onFinish: () => void }) => {
  if (file.file) {
    pdfFile.value = file.file
  }
  onFinish()
}

// 提交表单
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
    formData.append('compression_level', compressionLevel.value)

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
    outputPath.value = result.output_path || result.message || '压缩成功'

    message.success('压缩成功！')

    // 清空表单
    fileName.value = ''
    pdfFile.value = null
    pdfFileList.value = []

    // 显示成功模态框
    showModal.value = true
  } catch (error: any) {
    message.error(`压缩失败：${error.message}`)
  } finally {
    loading.value = false
  }
}

// 获取父目录
function getParentDir(path: string): string {
  const lastSep = Math.max(path.lastIndexOf('\\'), path.lastIndexOf('/'))
  return lastSep > -1 ? path.slice(0, lastSep) : path
}

// 打开文件
async function openFile() {
  try {
    const {openPath} = await import('@tauri-apps/plugin-opener')
    await openPath(outputPath.value)
  } catch (e: any) {
    message.error(`打开文件失败：${e.message || e}`)
  }
}

// 打开文件夹
async function openFolder() {
  try {
    const {openPath} = await import('@tauri-apps/plugin-opener')
    await openPath(getParentDir(outputPath.value))
  } catch (e: any) {
    message.error(`打开文件夹失败：${e.message || e}`)
  }
}

// 关闭模态框
function closeModal() {
  showModal.value = false
}

// 清空已上传的文件
function clearFile() {
  pdfFile.value = null
  pdfFileList.value = []
}
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
      <n-form label-placement="left" label-width="120">
        <!-- 文件名输入框 -->
        <n-form-item label="文件名" required>
          <n-input
              v-model:value="fileName"
              placeholder="请输入压缩后的文件名（不含扩展名）"
              clearable
          />
        </n-form-item>

        <!-- 压缩等级选择 -->
        <n-form-item label="压缩等级" required>
          <n-radio-group v-model:value="compressionLevel" name="compressionLevel">
            <n-space>
              <n-radio
                  v-for="option in levelOptions"
                  :key="option.value"
                  :value="option.value"
              >
                {{ option.label }}
              </n-radio>
            </n-space>
          </n-radio-group>
        </n-form-item>

        <!-- PDF文件拖拽上传框 -->
        <n-form-item label="PDF文件" required>
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
              <n-text style="font-size: 16px">
                点击或者拖动文件到该区域来上传
              </n-text>
              <n-p depth="3" style="margin: 8px 0 0 0">
                仅支持单个 .pdf 格式文件
              </n-p>
              <n-p v-if="pdfFile" depth="2" style="margin: 8px 0 0 0; color: #18a058;">
                已选择：{{ pdfFile.name }}
              </n-p>
            </n-upload-dragger>
          </n-upload>
        </n-form-item>

        <!-- 提交按钮 -->
        <n-form-item>
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
</style>
