<template>
  <div class="pdf-split-container">
    <n-card :title="cardTitle" style="height: 100vh; padding-top: 1rem">
      <!-- 未上传文件时显示拖拽区域 -->
      <div v-if="!pdfFile" class="upload-area">
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
              点击或者拖动 PDF 文件到该区域来上传
            </n-text>
            <n-p depth="3" style="margin: 8px 0 0 0">
              仅支持单个 .pdf 格式文件
            </n-p>
          </n-upload-dragger>
        </n-upload>
      </div>

      <!-- 已上传文件，显示三列布局 -->
      <div v-else class="split-layout">
        <!-- 左侧：缩略图列表 -->
        <div class="thumbnail-column">
          <div class="thumbnail-header">
            <n-text strong>页面列表</n-text>
            <n-text depth="3" style="font-size: 12px;">共 {{ pageCount }} 页</n-text>
          </div>
          <div class="thumbnail-list" ref="thumbnailListRef">
            <div
                v-for="(page, index) in pages"
                :key="index"
                class="thumbnail-item"
                :class="{ active: currentPage === index }"
                @click="selectPage(index)"
            >
              <img :src="page.thumbnail" :alt="`第 ${index + 1} 页`"/>
              <div class="page-number">第 {{ index + 1 }} 页</div>
            </div>
          </div>
        </div>

        <!-- 中间：大图预览 -->
        <div class="preview-column">
          <div class="preview-header">
            <n-text strong>预览</n-text>
            <n-text depth="3" style="font-size: 12px;">
              第 {{ currentPage + 1 }} / {{ pageCount }} 页
            </n-text>
          </div>
          <div class="preview-content">
            <img
                v-if="pages[currentPage]?.preview"
                :src="pages[currentPage].preview"
                alt="预览"
            />
            <n-empty v-else description="加载中..."/>
          </div>
          <div class="preview-controls">
            <n-button size="small" @click="prevPage" :disabled="currentPage === 0">
              <template #icon>
                <n-icon>
                  <ArrowBack/>
                </n-icon>
              </template>
              上一页
            </n-button>
            <n-text depth="3" style="font-size: 13px;">
              {{ currentPage + 1 }} / {{ pageCount }}
            </n-text>
            <n-button size="small" @click="nextPage" :disabled="currentPage === pageCount - 1">
              下一页
              <template #icon>
                <n-icon>
                  <ArrowForward/>
                </n-icon>
              </template>
            </n-button>
          </div>
        </div>

        <!-- 右侧：拆分范围设置 -->
        <div class="split-column">
          <div class="split-header">
            <n-text strong>拆分范围</n-text>
            <n-button size="small" type="primary" @click="addRange">
              <template #icon>
                <n-icon>
                  <Add/>
                </n-icon>
              </template>
              添加范围
            </n-button>
          </div>

          <div class="split-list">
            <div
                v-for="(range, index) in splitRanges"
                :key="index"
                class="split-item"
            >
              <div class="split-item-header">
                <n-text strong>范围 {{ index + 1 }}</n-text>
                <n-button
                    size="tiny"
                    quaternary
                    type="error"
                    @click="removeRange(index)"
                    :disabled="splitRanges.length <= 1"
                >
                  <template #icon>
                    <n-icon>
                      <Close/>
                    </n-icon>
                  </template>
                </n-button>
              </div>
              <div class="split-item-body">
                <n-form-item label="起始页" :label-width="60" label-placement="left">
                  <n-input-number
                      v-model:value="range.start"
                      :min="1"
                      :max="pageCount"
                      size="small"
                      style="width: 80px;"
                  />
                </n-form-item>
                <n-form-item label="结束页" :label-width="60" label-placement="left">
                  <n-input-number
                      v-model:value="range.end"
                      :min="1"
                      :max="pageCount"
                      size="small"
                      style="width: 80px;"
                  />
                </n-form-item>
              </div>
            </div>
          </div>

          <div class="split-actions">
            <n-button
                type="primary"
                block
                :loading="submitting"
                @click="handleSplit"
            >
              拆分 PDF
            </n-button>
            <n-button
                block
                quaternary
                size="small"
                @click="resetAll"
            >
              重新上传
            </n-button>
          </div>
        </div>
      </div>
    </n-card>
  </div>
</template>

<script lang="ts" setup>
import {ref, nextTick, watch} from 'vue'
import {type UploadFileInfo, useMessage} from 'naive-ui'
import {Add, Close, ArrowBack, ArrowForward} from '@vicons/ionicons5'
import * as pdfjsLib from 'pdfjs-dist'
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import {getToken} from '../../config'

// 配置 PDF.js worker
pdfjsLib.GlobalWorkerOptions.workerSrc = workerUrl
const props = withDefaults(defineProps<{
  cardTitle?: string
  apiEndpoint?: string
}>(), {
  cardTitle: 'PDF 拆分',
  apiEndpoint: '/api/v1/pdf/split'
})

const message = useMessage()

// 状态
const pdfFile = ref<File | null>(null)
const pdfFileList = ref<UploadFileInfo[]>([])
const pages = ref<Array<{ thumbnail: string; preview: string }>>([])
const pageCount = ref(0)
const currentPage = ref(0)
const submitting = ref(false)
const thumbnailListRef = ref<HTMLElement | null>(null)

// 拆分范围
interface SplitRange {
  start: number
  end: number
}

const splitRanges = ref<SplitRange[]>([
  {start: 1, end: 1}
])

// 自定义上传
function createCustomRequest(fileRef: { value: File | null }) {
  return ({file, onFinish}: { file: UploadFileInfo; onFinish: () => void }) => {
    if (file.file) {
      fileRef.value = file.file
    }
    onFinish()
  }
}

const pdfCustomRequest = createCustomRequest(pdfFile)

// 处理文件上传
function handlePdfChange({fileList}: { fileList: UploadFileInfo[] }) {
  pdfFileList.value = fileList
  if (fileList.length > 0 && fileList[0].file) {
    pdfFile.value = fileList[0].file
    loadPdf()
  }
}

// 加载 PDF
async function loadPdf() {
  if (!pdfFile.value) return

  try {
    const arrayBuffer = await pdfFile.value.arrayBuffer()
    const pdf = await pdfjsLib.getDocument({data: arrayBuffer}).promise
    pageCount.value = pdf.numPages

    pages.value = []
    for (let i = 1; i <= pdf.numPages; i++) {
      const page = await pdf.getPage(i)

      // 缩略图
      const thumbnailScale = 0.3
      const thumbnailViewport = page.getViewport({scale: thumbnailScale})
      const thumbnailCanvas = document.createElement('canvas')
      const thumbnailContext = thumbnailCanvas.getContext('2d')!
      thumbnailCanvas.width = thumbnailViewport.width
      thumbnailCanvas.height = thumbnailViewport.height
      await page.render({
        canvasContext: thumbnailContext,
        viewport: thumbnailViewport
      } as any).promise  // 添加 as any

      // 预览图
      const previewScale = 1.0
      const previewViewport = page.getViewport({scale: previewScale})
      const previewCanvas = document.createElement('canvas')
      const previewContext = previewCanvas.getContext('2d')!
      previewCanvas.width = previewViewport.width
      previewCanvas.height = previewViewport.height
      await page.render({
        canvasContext: previewContext,
        viewport: previewViewport
      } as any).promise  // 添加 as any

      pages.value.push({
        thumbnail: thumbnailCanvas.toDataURL('image/jpeg', 0.8),
        preview: previewCanvas.toDataURL('image/jpeg', 0.9)
      })
    }

    currentPage.value = 0
    splitRanges.value.forEach(range => {
      if (range.end > pageCount.value) range.end = pageCount.value
      if (range.start > pageCount.value) range.start = pageCount.value
    })

    message.success(`成功加载 PDF，共 ${pageCount.value} 页`)
  } catch (error) {
    console.error('加载 PDF 失败:', error)
    message.error('加载 PDF 失败，请检查文件是否损坏')
  }
}

// 选择页面
function selectPage(index: number) {
  currentPage.value = index
  nextTick(() => {
    const items = thumbnailListRef.value?.querySelectorAll('.thumbnail-item')
    if (items && items[index]) {
      items[index].scrollIntoView({block: 'nearest', behavior: 'smooth'})
    }
  })
}

function prevPage() {
  if (currentPage.value > 0) currentPage.value--
}

function nextPage() {
  if (currentPage.value < pageCount.value - 1) currentPage.value++
}

function addRange() {
  const lastRange = splitRanges.value[splitRanges.value.length - 1]
  splitRanges.value.push({
    start: lastRange.end + 1,
    end: Math.min(lastRange.end + 1, pageCount.value),
  })
}

function removeRange(index: number) {
  if (splitRanges.value.length > 1) {
    splitRanges.value.splice(index, 1)
  }
}

function resetAll() {
  pdfFile.value = null
  pdfFileList.value = []
  pages.value = []
  pageCount.value = 0
  currentPage.value = 0
  splitRanges.value = [{start: 1, end: 1}]
}

async function handleSplit() {
  for (const range of splitRanges.value) {
    if (range.start > range.end) {
      message.warning(`范围 ${splitRanges.value.indexOf(range) + 1} 的起始页不能大于结束页`)
      return
    }
    if (range.start < 1 || range.end > pageCount.value) {
      message.warning(`范围 ${splitRanges.value.indexOf(range) + 1} 的页码超出范围`)
      return
    }
  }

  submitting.value = true

  try {
    const formData = new FormData()
    formData.append('pdf_file', pdfFile.value!)

    const rangesData = splitRanges.value.map(range => ({
      start: range.start,
      end: range.end,
    }))
    formData.append('split_ranges', JSON.stringify(rangesData))

    const token = await getToken()
    const headers = new Headers()
    if (token) headers.set('Authorization', `Bearer ${token}`)

    const response = await fetch(props.apiEndpoint, {
      method: 'POST',
      headers,
      body: formData
    })

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || '拆分失败')
    }

    const result = await response.json()
    message.success(`拆分成功！共生成 ${result.file_count || splitRanges.value.length} 个文件`)
  } catch (error: any) {
    message.error(`拆分失败：${error.message}`)
  } finally {
    submitting.value = false
  }
}

watch(pageCount, (newCount) => {
  if (newCount > 0) {
    splitRanges.value.forEach(range => {
      if (range.end > newCount) range.end = newCount
      if (range.start > newCount) range.start = newCount
    })
  }
})
</script>

<style scoped>
.pdf-split-container {
  overflow: hidden;
  height: 100vh;
  padding: 0;
  margin: 0;
}

.upload-area {
  display: flex;
  justify-content: center;
  height: 80vh;
}

.split-layout {
  display: grid;
  grid-template-columns: 200px 1fr 320px;
  gap: 16px;
  height: calc(100vh - 120px);
  padding: 8px 0;
}

.thumbnail-column {
  display: flex;
  flex-direction: column;
  border-right: 1px solid #e8e8e8;
  padding-right: 12px;
  overflow-y: auto;
}

.thumbnail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 4px;
  border-bottom: 1px solid #f0f0f0;
  margin-bottom: 8px;
}

.thumbnail-list {
  flex: 1;
  overflow-y: auto;
  padding: 4px;
}

.thumbnail-list::-webkit-scrollbar {
  width: 4px;
}

.thumbnail-list::-webkit-scrollbar-thumb {
  background: #d9d9d9;
  border-radius: 2px;
}

.thumbnail-item {
  cursor: pointer;
  padding: 4px;
  margin-bottom: 8px;
  border: 2px solid transparent;
  border-radius: 4px;
  transition: all 0.2s;
}

.thumbnail-item:hover {
  border-color: #d9d9d9;
}

.thumbnail-item.active {
  border-color: #1890ff;
  background: #f0f7ff;
}

.thumbnail-item img {
  width: 100%;
  height: auto;
  display: block;
  border-radius: 2px;
}

.page-number {
  text-align: center;
  font-size: 12px;
  color: #666;
  padding: 4px 0;
}

.preview-column {
  display: flex;
  flex-direction: column;
  padding: 0 8px;
  height: 100%; /* 继承父容器高度 */
  overflow: hidden; /* 防止内容溢出 */
}

.preview-header {
  flex-shrink: 0; /* 头部不被压缩 */
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 4px;
  border-bottom: 1px solid #f0f0f0;
  margin-bottom: 8px;
}

.preview-content {
  flex: 1; /* 占据剩余高度 */
  min-height: 0; /* 允许 flex 收缩，防止溢出 */
  display: flex;
  justify-content: center;
  align-items: center;
  background: #fafafa;
  border-radius: 4px;
  overflow: hidden; /* 防止图片溢出容器 */
}

.preview-content img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain; /* 等比例缩放，不裁剪 */
}

.preview-controls {
  flex-shrink: 0; /* 底部按钮不被压缩 */
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 16px;
  padding: 12px 0;
  border-top: 1px solid #f0f0f0;
  margin-top: 8px;
}

.split-column {
  display: flex;
  flex-direction: column;
  border-left: 1px solid #e8e8e8;
  padding-left: 12px;
  overflow-y: auto;
}

.split-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 4px;
  border-bottom: 1px solid #f0f0f0;
  margin-bottom: 8px;
}

.split-list {
  flex: 1;
  overflow-y: auto;
  padding: 4px;
}

.split-list::-webkit-scrollbar {
  width: 4px;
}

.split-list::-webkit-scrollbar-thumb {
  background: #d9d9d9;
  border-radius: 2px;
}

.split-item {
  background: #fafafa;
  border-radius: 4px;
  padding: 12px;
  margin-bottom: 12px;
  border: 1px solid #f0f0f0;
}

.split-item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.split-item-body {
  display: flex;
  flex-direction: column;
  gap: 4px;
}


.split-actions {
  padding-top: 12px;
  border-top: 1px solid #f0f0f0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

@media (max-width: 1024px) {
  .split-layout {
    grid-template-columns: 150px 1fr 280px;
  }
}

@media (max-width: 768px) {
  .split-layout {
    grid-template-columns: 1fr;
    grid-template-rows: auto 1fr auto;
    height: auto;
  }

  .thumbnail-column {
    border-right: none;
    border-bottom: 1px solid #e8e8e8;
    padding-right: 0;
    max-height: 200px;
  }

  .thumbnail-list {
    display: flex;
    gap: 8px;
    overflow-x: auto;
    flex: none;
    padding: 8px 0;
  }

  .thumbnail-item {
    min-width: 80px;
    flex-shrink: 0;
  }

  .split-column {
    border-left: none;
    border-top: 1px solid #e8e8e8;
    padding-left: 0;
    padding-top: 12px;
  }
}
</style>