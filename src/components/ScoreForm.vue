<script setup lang="ts">
import {ref, computed} from 'vue'
import {useMessage, type UploadFileInfo} from 'naive-ui'

const props = withDefaults(defineProps<{
  cardTitle: string
  apiEndpoint: string
  successMessage?: string
  buttonLabel?: string
}>(), {
  successMessage: '生成成功！',
  buttonLabel: '生成'
})

const message = useMessage()

const title = ref('')
const scoreSheetFileList = ref<UploadFileInfo[]>([])
const scoreSheetFile = ref<File | null>(null)
const lineMethod = ref<'table' | 'file'>('file')
const lineSheetFileList = ref<UploadFileInfo[]>([])
const lineSheetFile = ref<File | null>(null)
const loading = ref(false)
const showModal = ref(false)
const outputPath = ref('')
const isDifferentiated = ref(true)
const direction = ref<'物理' | '历史'>('物理')

const displaySubjects = computed(() => {
  if (!isDifferentiated.value) return subjects
  return subjects.filter(s => s !== (direction.value === '物理' ? '历史' : '物理'))
})

// 分数线表格数据：行是学科，列是分数线类型
const lineData = ref({
  '清北线': {
    '总分': '',
    '语文': '',
    '数学': '',
    '英语': '',
    '物理': '',
    '化学': '',
    '生物': '',
    '历史': '',
    '政治': '',
    '地理': ''
  },
  '985线': {
    '总分': '',
    '语文': '',
    '数学': '',
    '英语': '',
    '物理': '',
    '化学': '',
    '生物': '',
    '历史': '',
    '政治': '',
    '地理': ''
  },
  '211线': {
    '总分': '',
    '语文': '',
    '数学': '',
    '英语': '',
    '物理': '',
    '化学': '',
    '生物': '',
    '历史': '',
    '政治': '',
    '地理': ''
  },
  '特控线': {
    '总分': '',
    '语文': '',
    '数学': '',
    '英语': '',
    '物理': '',
    '化学': '',
    '生物': '',
    '历史': '',
    '政治': '',
    '地理': ''
  },
  '本科线': {
    '总分': '',
    '语文': '',
    '数学': '',
    '英语': '',
    '物理': '',
    '化学': '',
    '生物': '',
    '历史': '',
    '政治': '',
    '地理': ''
  },
})

const subjects = ['总分', '语文', '数学', '英语', '物理', '化学', '生物', '历史', '政治', '地理'] as const
const lineTypes = ['清北线', '985线', '211线', '特控线', '本科线'] as const


function handleScoreSheetChange({fileList}: { fileList: UploadFileInfo[] }) {
  scoreSheetFileList.value = fileList
}

function handleLineSheetChange({fileList}: { fileList: UploadFileInfo[] }) {
  lineSheetFileList.value = fileList
}

function createCustomRequest(targetRef: { value: File | null }) {
  return ({file, onFinish}: { file: UploadFileInfo; onFinish: () => void }) => {
    if (file.file) {
      targetRef.value = file.file
    }
    onFinish()
  }
}

const scoreSheetCustomRequest = createCustomRequest(scoreSheetFile)
const lineSheetCustomRequest = createCustomRequest(lineSheetFile)

async function handleSubmit() {
  if (!title.value.trim()) {
    message.warning('请输入考试名称')
    return
  }

  if (!scoreSheetFile.value) {
    message.warning('请上传原始成绩单文件')
    return
  }

  if (lineMethod.value === 'table') {
    // 验证表格数据是否填写
    let hasData = false
    for (const lineType of lineTypes) {
      for (const subject of displaySubjects.value) {
        const value = lineData.value[lineType][subject]
        if (value && parseFloat(value) > 0) {
          hasData = true
          break
        }
      }
      if (hasData) break
    }
    if (!hasData) {
      message.warning('请至少填写一个分数线数据')
      return
    }
  }

  if (lineMethod.value === 'file' && !lineSheetFile.value) {
    message.warning('请上传分数线表格文件')
    return
  }

  loading.value = true

  try {
    const formData = new FormData()
    formData.append('title', title.value)
    formData.append('scoreSheet', scoreSheetFile.value)

    if (lineMethod.value === 'table') {
      // 将表格数据转换为扁平 JSON
      const jsonData: Record<string, number> = {}
      for (const lineType of lineTypes) {
        for (const subject of displaySubjects.value) {
          const value = lineData.value[lineType][subject]
          if (value && parseFloat(value) > 0) {
            const prefix = isDifferentiated.value ? direction.value : ''
            jsonData[`${prefix}${subject}_${lineType}`] = parseFloat(value)
          }
        }
      }
      formData.append('lineJSON', JSON.stringify(jsonData))
    } else {
      formData.append('lineSheet', lineSheetFile.value!)
    }

    const response = await fetch(props.apiEndpoint, {
      method: 'POST',
      body: formData,
    })

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || '请求失败')
    }

    const result = await response.json()
    outputPath.value = result.output_path

    message.success(props.successMessage)

    // 清空表单
    title.value = ''
    scoreSheetFileList.value = []
    scoreSheetFile.value = null
    lineSheetFileList.value = []
    lineSheetFile.value = null
    // 重置表格数据
    for (const lineType of lineTypes) {
      for (const subject of displaySubjects.value) {
        lineData.value[lineType][subject] = ''
      }
    }

    // 显示成功模态框
    showModal.value = true
  } catch (error: any) {
    message.error(`生成失败：${error.message}`)
  } finally {
    loading.value = false
  }
}

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
</script>

<template>
  <div class="score-form-container">
    <n-modal
        v-model:show="showModal"
        :mask-closable="false"
        :closeable="false"
        preset="dialog"
        title="生成成功"
        positive-text=""
        negative-text=""
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
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
                </svg>
              </n-icon>
            </template>
            打开文件夹
          </n-button>
          <n-button type="success" @click="openFile">
            <template #icon>
              <n-icon>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                  <polyline points="14 2 14 8 20 8"/>
                  <line x1="12" y1="18" x2="12" y2="12"/>
                  <line x1="9" y1="15" x2="15" y2="15"/>
                </svg>
              </n-icon>
            </template>
            打开文件
          </n-button>
          <n-button @click="closeModal">关闭</n-button>
        </div>
      </template>
    </n-modal>

    <n-card :title="cardTitle">
      <n-form label-placement="left" label-width="120">
        <n-form-item label="考试名称" required>
          <n-input v-model:value="title" placeholder="请输入考试名称"/>
        </n-form-item>

        <n-form-item label="原始成绩单" required>
          <n-upload
              :max="1"
              :file-list="scoreSheetFileList"
              @change="handleScoreSheetChange"
              :custom-request="scoreSheetCustomRequest"
              accept=".xlsx"
              dragger
          >
            <n-upload-dragger>
              <div style="margin-bottom: 12px">
                <n-icon size="48" :depth="3">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                    <polyline points="14 2 14 8 20 8"/>
                    <line x1="12" y1="18" x2="12" y2="12"/>
                    <line x1="9" y1="15" x2="15" y2="15"/>
                  </svg>
                </n-icon>
              </div>
              <n-text style="font-size: 16px">
                点击或者拖动文件到该区域来上传
              </n-text>
              <n-p depth="3" style="margin: 8px 0 0 0">
                仅支持 .xlsx 格式
              </n-p>
            </n-upload-dragger>
          </n-upload>
        </n-form-item>

        <n-form-item label="分数线输入方式">
          <n-radio-group v-model:value="lineMethod">
            <n-space>
              <n-radio value="file">表格文件</n-radio>
              <n-tooltip trigger="hover">
                <template #trigger>
                  <n-radio value="table">手动输入</n-radio>
                </template>
                输入时按 Tab 键可快速切换单元格
              </n-tooltip>
            </n-space>
          </n-radio-group>
        </n-form-item>


        <template v-if="lineMethod === 'table'">
          <n-form-item label="选科分科">
            <n-space align="center">
              <n-switch v-model:value="isDifferentiated"/>
              <n-text depth="2" style="font-size: 14px;">
                {{ isDifferentiated ? '已分科' : '未分科' }}
              </n-text>
              <template v-if="isDifferentiated">
                <n-text depth="3" style="margin: 0 4px 0 12px; font-size: 14px;">方向</n-text>
                <n-radio-group v-model:value="direction" size="small">
                  <n-radio value="物理">物理</n-radio>
                  <n-radio value="历史">历史</n-radio>
                </n-radio-group>
              </template>
            </n-space>
          </n-form-item>

          <n-form-item label="分数线数据">
            <n-table :bordered="true" :single-line="false" size="small">
              <thead>
              <tr>
                <th>学科</th>
                <th v-for="lineType in lineTypes" :key="lineType">{{ lineType }}</th>
              </tr>
              </thead>
              <tbody>
              <tr v-for="subject in displaySubjects" :key="subject">
                <td>{{ subject }}</td>
                <td v-for="lineType in lineTypes" :key="lineType">
                  <n-input
                      v-model:value="lineData[lineType][subject]"
                      placeholder="0"
                      size="tiny"
                      style="width: 60px"
                  />
                </td>
              </tr>
              </tbody>
            </n-table>
          </n-form-item>
        </template>


        <n-form-item v-else label="分数线表格" required>
          <n-upload
              :max="1"
              :file-list="lineSheetFileList"
              @change="handleLineSheetChange"
              :custom-request="lineSheetCustomRequest"
              accept=".xlsx"
              dragger
          >
            <n-upload-dragger>
              <div style="margin-bottom: 12px">
                <n-icon size="48" :depth="3">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                    <polyline points="14 2 14 8 20 8"/>
                    <line x1="12" y1="18" x2="12" y2="12"/>
                    <line x1="9" y1="15" x2="15" y2="15"/>
                  </svg>
                </n-icon>
              </div>
              <n-text style="font-size: 16px">
                点击或者拖动文件到该区域来上传
              </n-text>
              <n-p depth="3" style="margin: 8px 0 0 0">
                仅支持 .xlsx 格式
              </n-p>
            </n-upload-dragger>
          </n-upload>
        </n-form-item>

        <n-form-item>
          <n-button class="submit-button" type="info" @click="handleSubmit" :loading="loading" block>
            {{ buttonLabel }}
          </n-button>
        </n-form-item>
      </n-form>
    </n-card>
  </div>
</template>

<style scoped>
.score-form-container {
  margin: 0;
  padding: 0;
}
</style>
