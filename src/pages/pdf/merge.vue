<script lang="ts" setup>
import {ref} from 'vue'
import {type UploadFileInfo, useMessage} from 'naive-ui'
import {apiUpload} from '../../config'

const props = withDefaults(defineProps<{
  cardTitle: string
  successMessage?: string
  buttonLabel?: string
}>(), {
  successMessage: '合并成功！',
  buttonLabel: '合并'
})

const message = useMessage()

const fileName = ref('')
const pdfFileList = ref<UploadFileInfo[]>([])
const pdfFiles = ref<File[]>([])
const loading = ref(false)
const showModal = ref(false)
const outputPath = ref('')

// 处理文件上传变化
function handlePdfChange({fileList}: { fileList: UploadFileInfo[] }) {
  pdfFileList.value = fileList
  // 提取实际的文件对象
  pdfFiles.value = fileList
      .map(item => item.file)
      .filter((file): file is File => file !== undefined && file !== null)
}

// 自定义上传请求（阻止默认上传行为）
function createCustomRequest(filesRef: { value: File[] }) {
  return ({file, onFinish}: { file: UploadFileInfo; onFinish: () => void }) => {
    if (file.file) {
      // 检查是否已经存在
      const exists = filesRef.value.some(f => f.name === file.file!.name && f.size === file.file!.size)
      if (!exists) {
        filesRef.value.push(file.file)
      }
    }
    onFinish()
  }
}

const pdfCustomRequest = createCustomRequest(pdfFiles)

// 提交表单
async function handleSubmit() {
  if (!fileName.value.trim()) {
    message.warning('请输入文件名')
    return
  }

  if (pdfFiles.value.length === 0) {
    message.warning('请上传PDF文件')
    return
  }

  loading.value = true

  try {
    const formData = new FormData()
    formData.append('file_name', fileName.value.trim())

    // 添加所有PDF文件
    pdfFiles.value.forEach(file => {
      formData.append('pdf_list', file)
    })

    const result = await apiUpload<{output_path?: string; message?: string}>('/api/v1/pdf/merge', formData)
    outputPath.value = result.output_path || result.message || '合并成功'

    message.success(props.successMessage)

    // 清空表单
    fileName.value = ''
    pdfFileList.value = []
    pdfFiles.value = []

    // 显示成功模态框
    showModal.value = true
  } catch (error: any) {
    message.error(`合并失败：${error.message}`)
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
function clearFiles() {
  pdfFileList.value = []
  pdfFiles.value = []
}
</script>

<template>
  <div class="pdf-merge-container">
    <!-- 成功模态框 -->
    <n-modal
        v-model:show="showModal"
        :closeable="false"
        :mask-closable="false"
        negative-text=""
        positive-text=""
        preset="dialog"
        title="合并成功"
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

    <n-card title="PDF合并" style="height: 100vh; padding-top: 1rem">
      <n-form label-placement="left" label-width="120">
        <!-- 文件名输入框 -->
        <n-form-item label="文件名" required>
          <n-input
              v-model:value="fileName"
              placeholder="请输入合并后的文件名（不含扩展名）"
              clearable
          />
        </n-form-item>

        <!-- PDF文件拖拽上传框 -->
        <n-form-item label="PDF文件" required>
          <n-upload
              :custom-request="pdfCustomRequest"
              :file-list="pdfFileList"
              accept=".pdf"
              multiple
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
                支持多个PDF文件，仅支持 .pdf 格式
              </n-p>
              <n-p v-if="pdfFiles.length > 0" depth="2" style="margin: 8px 0 0 0; color: #18a058;">
                已选择 {{ pdfFiles.length }} 个文件
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
              {{ buttonLabel }}
            </n-button>
            <n-button
                v-if="pdfFiles.length > 0"
                block
                quaternary
                size="small"
                @click="clearFiles"
            >
              清空已选文件
            </n-button>
          </n-space>
        </n-form-item>
      </n-form>
    </n-card>
  </div>
</template>

<style scoped>
.pdf-merge-container {
  margin: 0;
  padding: 0;
}

.submit-button {
  height: 2rem;
  font-size: 16px;
}
</style>