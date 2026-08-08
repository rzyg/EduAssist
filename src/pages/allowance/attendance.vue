<script lang="ts" setup>
import {ref} from 'vue'
import type {UploadFileInfo} from 'naive-ui'
import {useMessage} from 'naive-ui'
import {apiUpload} from '../../config'

const message = useMessage()

const attendanceFile = ref<File | null>(null)
const fileList = ref<UploadFileInfo[]>([])
const loading = ref(false)
const showConfirm = ref(false)
const showResult = ref(false)
const outputPaths = ref<string[]>([])

// 处理文件上传变化（仅保留单个文件）
function handleFileChange({fileList: list}: { fileList: UploadFileInfo[] }) {
  fileList.value = list
  const file = list[0]?.file
  attendanceFile.value = file ?? null
}

// 自定义上传请求（阻止默认上传行为，仅收集文件）
function createCustomRequest({onFinish}: { onFinish: () => void }) {
  onFinish()
}

// 点击提交 → 弹出二次确认
function handleSubmitClick() {
  if (!attendanceFile.value) {
    message.warning('请选择签到表文件')
    return
  }
  showConfirm.value = true
}

// 确认后上传
async function handleConfirm() {
  if (!attendanceFile.value) return
  showConfirm.value = false
  loading.value = true
  try {
    const formData = new FormData()
    formData.append('sheet', attendanceFile.value)
    const result = await apiUpload<{ output_path?: string[] }>(
        '/api/v1/allowance/attendance_statistics',
        formData
    )
    outputPaths.value = result.output_path || []
    message.success('坐班签到统计完成')
    showResult.value = true
  } catch (e: any) {
    message.error(`统计失败：${e.message || e}`)
  } finally {
    loading.value = false
  }
}

// 获取父目录
function getParentDir(path: string): string {
  const lastSep = Math.max(path.lastIndexOf('\\'), path.lastIndexOf('/'))
  return lastSep > -1 ? path.slice(0, lastSep) : path
}

// 打开文件夹
async function openFolder() {
  try {
    const {openPath} = await import('@tauri-apps/plugin-opener')
    await openPath(getParentDir(outputPaths.value[0] || ''))
  } catch (e: any) {
    message.error(`打开文件夹失败：${e.message || e}`)
  }
}

// 打开打卡统计文件
async function openFile() {
  try {
    const {openPath} = await import('@tauri-apps/plugin-opener')
    await openPath(outputPaths.value[0] || '')
  } catch (e: any) {
    message.error(`打开文件失败：${e.message || e}`)
  }
}

// 清空已选文件
function clearFiles() {
  fileList.value = []
  attendanceFile.value = null
}
</script>

<template>
  <div class="attendance-container">
    <!-- 提交二次确认弹窗 -->
    <n-modal
        v-model:show="showConfirm"
        preset="dialog"
        title="确认提交"
        content="请在校历页确认返校、离校日无误后提交"
        positive-text="确认提交"
        negative-text="取消"
        @positive-click="handleConfirm"
    />

    <!-- 成功弹窗 -->
    <n-modal
        v-model:show="showResult"
        :closeable="false"
        :mask-closable="false"
        negative-text=""
        positive-text=""
        preset="dialog"
        title="统计完成"
    >
      <template #default>
        <div style="text-align: center; padding: 8px 0;">
          <n-text depth="3" style="font-size: 13px; word-break: break-all;">
            {{ outputPaths.join('\n') }}
          </n-text>
        </div>
        <div style="display: flex; gap: 12px; justify-content: center; margin-top: 16px;">
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
          <n-button @click="showResult = false">关闭</n-button>
        </div>
      </template>
    </n-modal>

    <n-card title="签到统计" style="height: 100vh; padding-top: 1rem">
      <n-form label-placement="left" label-width="120">
        <!-- 签到表文件上传 -->
        <n-form-item label="原始签到表" required>
          <n-upload
              :custom-request="createCustomRequest"
              :file-list="fileList"
              accept=".xlsx"
              :max="1"
              dragger
              @change="handleFileChange"
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
                仅支持 .xlsx 格式
              </n-p>
              <n-p v-if="attendanceFile" depth="2" style="margin: 8px 0 0 0; color: #18a058;">
                已选择：{{ attendanceFile.name }}
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
                @click="handleSubmitClick"
            >
              生成统计
            </n-button>
            <n-button
                v-if="attendanceFile"
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
.attendance-container {
  margin: 0;
  padding: 0;
}

.submit-button {
  height: 2rem;
  font-size: 16px;
}
</style>
