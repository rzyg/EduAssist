<script lang="ts" setup>
/**
 * PDF 编辑页面
 *
 * 双栏布局:
 *  左栏 — 页面列表（缩略图 + 旋转/删除/插入 + 拖拽排序）
 *  右栏 — 当前页预览 + 标注工具（矩形/椭圆/文字/图片）
 */
import {ref, computed, nextTick, onMounted, onBeforeUnmount} from 'vue'
import {type UploadFileInfo, useMessage} from 'naive-ui'
import * as pdfjsLib from 'pdfjs-dist'
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'

// ── pdfjs 初始化 ────────────────────────────────────────────────────────────
pdfjsLib.GlobalWorkerOptions.workerSrc = workerUrl

defineProps<{
  cardTitle?: string
}>()

const message = useMessage()

// =============================================================================
// 类型定义
// =============================================================================

interface PageData {
  index: number          // 原始页码（用于追踪）
  thumbnail: string      // dataURL 缩略图
  preview: string        // dataURL 预览图
  rotation: number       // 旋转角度 (0/90/180/270)
}

/** 标注元素 */
interface Annotation {
  id: string
  type: 'rect' | 'ellipse' | 'text' | 'image'
  x: number
  y: number
  width: number
  height: number
  content?: string       // 文字内容 / 图片 dataURL
  color?: string
}

// =============================================================================
// 状态
// =============================================================================

const pdfFile = ref<File | null>(null)
const pdfFileList = ref<UploadFileInfo[]>([])

// PDF 数据
const pdfDoc = ref<pdfjsLib.PDFDocumentProxy | null>(null)
const pages = ref<PageData[]>([])
const pageCount = ref(0)
const currentPage = ref(0)

// 标注
const annotations = ref<Annotation[]>([])
const activeTool = ref<string>('select')
const selectedAnnotId = ref<string | null>(null)
const drawing = ref(false)
const drawStart = ref<{ x: number; y: number }>({x: 0, y: 0})

// 预览 Canvas ref（用于渲染 PDF）
const previewCanvasRef = ref<HTMLCanvasElement | null>(null)
// 标注覆盖 Canvas ref
const overlayCanvasRef = ref<HTMLCanvasElement | null>(null)
// 拖拽状态
const dragIndex = ref<number | null>(null)
const dragOverIndex = ref<number | null>(null)
// 缩略图列表滚动容器
const thumbnailListRef = ref<HTMLElement | null>(null)

// PDF 原文件 ArrayBuffer（用于重新渲染）
const pdfBuffer = ref<ArrayBuffer | null>(null)

// 临时文字输入
const textInputPos = ref<{ x: number; y: number } | null>(null)
const textInputVisible = ref(false)
const textInputValue = ref('')

// =============================================================================
// 计算属性
// =============================================================================

const currentPageData = computed(() => pages.value[currentPage.value] || null)

const toolbarTools = [
  {key: 'select', icon: '↖️', label: '选择'},
  {key: 'rect', icon: '▭', label: '矩形'},
  {key: 'ellipse', icon: '⬭', label: '椭圆'},
  {key: 'text', icon: 'T', label: '文字'},
  {key: 'image', icon: '🖼️', label: '图片'},
]

// =============================================================================
// PDF 加载
// =============================================================================

function handlePdfChange({fileList}: { fileList: UploadFileInfo[] }) {
  pdfFileList.value = fileList
  if (fileList.length > 0 && fileList[0].file) {
    pdfFile.value = fileList[0].file
    loadPdf()
  }
}

function createCustomRequest(fileRef: { value: File | null }) {
  return ({file, onFinish}: { file: UploadFileInfo; onFinish: () => void }) => {
    if (file.file) fileRef.value = file.file
    onFinish()
  }
}

const pdfCustomRequest = createCustomRequest(pdfFile)

async function loadPdf() {
  if (!pdfFile.value) return
  try {
    const arrayBuffer = await pdfFile.value.arrayBuffer()
    pdfBuffer.value = arrayBuffer
    const pdf = await pdfjsLib.getDocument({data: arrayBuffer.slice(0)}).promise
    pdfDoc.value = pdf
    pageCount.value = pdf.numPages

    pages.value = []
    for (let i = 1; i <= pdf.numPages; i++) {
      const page = await pdf.getPage(i)
      const thumbScale = 0.25
      const thumbVp = page.getViewport({scale: thumbScale})
      const thumbCanvas = document.createElement('canvas')
      thumbCanvas.width = thumbVp.width
      thumbCanvas.height = thumbVp.height
      await page.render({canvasContext: thumbCanvas.getContext('2d')!, viewport: thumbVp} as any).promise

      // 同时渲染预览图，避免之后再次调用 getPage()
      const prevScale = 1.2
      const prevVp = page.getViewport({scale: prevScale})
      const prevCanvas = document.createElement('canvas')
      prevCanvas.width = prevVp.width
      prevCanvas.height = prevVp.height
      await page.render({canvasContext: prevCanvas.getContext('2d')!, viewport: prevVp} as any).promise

      pages.value.push({
        index: i - 1,
        thumbnail: thumbCanvas.toDataURL('image/jpeg', 0.7),
        preview: prevCanvas.toDataURL('image/jpeg', 0.85),
        rotation: 0,
      })
    }

    currentPage.value = 0
    annotations.value = []
    // 释放 pdfDoc 引用，后续不再调用 getPage()
    pdfDoc.value = null
    message.success(`已加载 ${pageCount.value} 页`)
    await nextTick()
    renderCurrentPreview()
  } catch (e) {
    console.error('加载 PDF 失败:', e)
    message.error('加载 PDF 失败')
  }
}

// =============================================================================
// 当前页预览渲染
// =============================================================================

async function renderCurrentPreview() {
  const data = currentPageData.value
  if (!data || !data.preview) return

  const canvas = previewCanvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')!
  const rotation = data.rotation

  const img = new Image()
  await new Promise<void>((resolve, reject) => {
    img.onload = () => resolve()
    img.onerror = reject
    img.src = data.preview
  })

  // 确定画布尺寸（考虑旋转）
  const swap = rotation % 180 !== 0
  canvas.width = swap ? img.height : img.width
  canvas.height = swap ? img.width : img.height

  ctx.clearRect(0, 0, canvas.width, canvas.height)

  // 应用旋转后居中绘制
  ctx.save()
  ctx.translate(canvas.width / 2, canvas.height / 2)
  ctx.rotate((rotation * Math.PI) / 180)
  ctx.drawImage(img, -img.width / 2, -img.height / 2)
  ctx.restore()

  // 同步覆盖 Canvas 尺寸
  const overlay = overlayCanvasRef.value
  if (overlay) {
    overlay.width = canvas.width
    overlay.height = canvas.height
  }

  // 存储预览 dataURL
  pages.value[currentPage.value] = {
    ...pages.value[currentPage.value],
    preview: canvas.toDataURL('image/jpeg', 0.85),
  }

  renderAnnotations()
}

// =============================================================================
// 标注渲染
// =============================================================================

function renderAnnotations() {
  const overlay = overlayCanvasRef.value
  if (!overlay) return
  const ctx = overlay.getContext('2d')!
  ctx.clearRect(0, 0, overlay.width, overlay.height)

  for (const ann of annotations.value) {
    ctx.strokeStyle = ann.color || '#1890ff'
    ctx.lineWidth = 2
    ctx.fillStyle = ann.color ? ann.color + '33' : 'rgba(24,144,255,0.2)'

    if (ann.id === selectedAnnotId.value) {
      ctx.strokeStyle = '#ff4d4f'
      ctx.lineWidth = 3
    }

    switch (ann.type) {
      case 'rect':
        ctx.fillRect(ann.x, ann.y, ann.width, ann.height)
        ctx.strokeRect(ann.x, ann.y, ann.width, ann.height)
        break
      case 'ellipse':
        ctx.beginPath()
        ctx.ellipse(
            ann.x + ann.width / 2,
            ann.y + ann.height / 2,
            ann.width / 2,
            ann.height / 2,
            0, 0, Math.PI * 2,
        )
        ctx.fill()
        ctx.stroke()
        break
      case 'text':
        ctx.font = '16px sans-serif'
        ctx.fillStyle = ann.color || '#1890ff'
        ctx.fillText(ann.content || '', ann.x, ann.y + 16)
        break
      case 'image':
        if (ann.content) {
          const img = new Image()
          img.onload = () => {
            ctx.drawImage(img, ann.x, ann.y, ann.width, ann.height)
          }
          img.src = ann.content
        }
        break
    }
  }
}

// =============================================================================
// 标注工具 — 鼠标事件
// =============================================================================

function getCanvasPos(e: MouseEvent | Touch): { x: number; y: number } {
  const overlay = overlayCanvasRef.value
  if (!overlay) return {x: 0, y: 0}
  const rect = overlay.getBoundingClientRect()
  return {
    x: e.clientX - rect.left,
    y: e.clientY - rect.top,
  }
}

function onOverlayMouseDown(e: MouseEvent) {
  if (activeTool.value === 'select') {
    // 选择模式：检测点击的标注
    const pos = getCanvasPos(e)
    selectAnnotationAt(pos.x, pos.y)
    return
  }

  if (activeTool.value === 'text') {
    const pos = getCanvasPos(e)
    textInputPos.value = pos
    textInputVisible.value = true
    textInputValue.value = ''
    nextTick(() => {
      const input = document.querySelector('.text-input-overlay') as HTMLInputElement
      input?.focus()
    })
    return
  }

  if (activeTool.value === 'image') {
    // 触发文件选择
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = 'image/*'
    input.onchange = () => {
      const file = input.files?.[0]
      if (!file) return
      const reader = new FileReader()
      reader.onload = (ev) => {
        const dataUrl = ev.target?.result as string
        const pos = getCanvasPos(e)
        const img = new Image()
        img.onload = () => {
          const maxW = 300
          const maxH = 300
          let w = img.width
          let h = img.height
          if (w > maxW) {
            h = h * (maxW / w);
            w = maxW
          }
          if (h > maxH) {
            w = w * (maxH / h);
            h = maxH
          }
          annotations.value.push({
            id: genId(),
            type: 'image',
            x: pos.x,
            y: pos.y,
            width: w,
            height: h,
            content: dataUrl,
            color: '#1890ff',
          })
          renderAnnotations()
        }
        img.src = dataUrl
      }
      reader.readAsDataURL(file)
    }
    input.click()
    return
  }

  // rect / ellipse：开始绘制
  const pos = getCanvasPos(e)
  drawing.value = true
  drawStart.value = pos
  selectedAnnotId.value = null
}

function onOverlayMouseMove(e: MouseEvent) {
  if (!drawing.value) return
  const overlay = overlayCanvasRef.value
  if (!overlay) return

  const pos = getCanvasPos(e)
  const x = Math.min(drawStart.value.x, pos.x)
  const y = Math.min(drawStart.value.y, pos.y)
  const w = Math.abs(pos.x - drawStart.value.x)
  const h = Math.abs(pos.y - drawStart.value.y)

  // 实时预览绘制（擦除重绘）
  const ctx = overlay.getContext('2d')!
  ctx.clearRect(0, 0, overlay.width, overlay.height)
  renderAnnotations()

  // 绘制正在进行中的形状
  ctx.strokeStyle = '#1890ff'
  ctx.lineWidth = 2
  ctx.setLineDash([5, 5])
  ctx.fillStyle = 'rgba(24,144,255,0.1)'

  if (activeTool.value === 'rect') {
    ctx.fillRect(x, y, w, h)
    ctx.strokeRect(x, y, w, h)
  } else if (activeTool.value === 'ellipse') {
    ctx.beginPath()
    ctx.ellipse(x + w / 2, y + h / 2, w / 2, h / 2, 0, 0, Math.PI * 2)
    ctx.fill()
    ctx.stroke()
  }
  ctx.setLineDash([])
}

function onOverlayMouseUp(e: MouseEvent) {
  if (!drawing.value) return
  drawing.value = false

  const pos = getCanvasPos(e)
  const w = Math.abs(pos.x - drawStart.value.x)
  const h = Math.abs(pos.y - drawStart.value.y)
  if (w < 5 && h < 5) return // 太小的忽略

  const x = Math.min(drawStart.value.x, pos.x)
  const y = Math.min(drawStart.value.y, pos.y)

  const color = '#1890ff'
  const id = genId()

  if (activeTool.value === 'rect') {
    annotations.value.push({id, type: 'rect', x, y, width: w, height: h, color})
  } else if (activeTool.value === 'ellipse') {
    annotations.value.push({id, type: 'ellipse', x, y, width: w, height: h, color})
  }

  selectedAnnotId.value = id
  renderAnnotations()
}

function selectAnnotationAt(x: number, y: number) {
  for (let i = annotations.value.length - 1; i >= 0; i--) {
    const a = annotations.value[i]
    if (a.type === 'text') {
      // 粗略检测文字区域
      if (x >= a.x && x <= a.x + 200 && y >= a.y - 16 && y <= a.y + 8) {
        selectedAnnotId.value = a.id
        renderAnnotations()
        return
      }
    } else {
      if (x >= a.x && x <= a.x + a.width && y >= a.y && y <= a.y + a.height) {
        selectedAnnotId.value = a.id
        renderAnnotations()
        return
      }
    }
  }
  selectedAnnotId.value = null
  renderAnnotations()
}

function genId(): string {
  return `ann_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
}

// =============================================================================
// 键盘删除
// =============================================================================

function onKeyDown(e: KeyboardEvent) {
  if (e.key === 'Delete' || e.key === 'Backspace') {
    if (selectedAnnotId.value) {
      const el = document.activeElement
      if (el?.tagName === 'INPUT' || el?.tagName === 'TEXTAREA') return
      annotations.value = annotations.value.filter(a => a.id !== selectedAnnotId.value)
      selectedAnnotId.value = null
      renderAnnotations()
    }
  }
  if (e.key === 'Escape') {
    activeTool.value = 'select'
    selectedAnnotId.value = null
    renderAnnotations()
  }
}

onMounted(() => {
  window.addEventListener('keydown', onKeyDown)
})
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeyDown)
})

// =============================================================================
// 文字确认
// =============================================================================

function confirmText() {
  if (!textInputValue.value.trim() || !textInputPos.value) {
    textInputVisible.value = false
    return
  }
  annotations.value.push({
    id: genId(),
    type: 'text',
    x: textInputPos.value.x,
    y: textInputPos.value.y,
    width: 200,
    height: 30,
    content: textInputValue.value.trim(),
    color: '#1890ff',
  })
  textInputVisible.value = false
  textInputValue.value = ''
  renderAnnotations()
}

// =============================================================================
// 页面操作
// =============================================================================

/** 旋转页面（顺时针 90°） */
function rotatePage(index: number) {
  const p = pages.value[index]
  p.rotation = (p.rotation + 90) % 360
  // 重新渲染当前页
  if (index === currentPage.value) {
    nextTick(() => renderCurrentPreview())
  }
}

/** 删除页面 */
function deletePage(index: number) {
  if (pages.value.length <= 1) {
    message.warning('至少保留一页')
    return
  }
  pages.value.splice(index, 1)
  pageCount.value--
  if (currentPage.value >= pageCount.value) {
    currentPage.value = pageCount.value - 1
  }
  message.success(`已删除第 ${index + 1} 页`)
  if (currentPage.value === index || currentPage.value > index) {
    nextTick(() => renderCurrentPreview())
  }
}

/** 在当前页下方插入新页（空白页） */
function insertPageAfter(index: number) {
  const canvas = document.createElement('canvas')
  canvas.width = 612
  canvas.height = 792
  const ctx = canvas.getContext('2d')!
  ctx.fillStyle = 'white'
  ctx.fillRect(0, 0, 612, 792)
  ctx.strokeStyle = '#ccc'
  ctx.strokeRect(20, 20, 572, 752)

  const newPage: PageData = {
    index: -1, // 标记为新增页
    thumbnail: canvas.toDataURL('image/jpeg', 0.7),
    preview: '',
    rotation: 0,
  }
  pages.value.splice(index + 1, 0, newPage)
  pageCount.value++
  message.success(`已插入新页`)
}

// =============================================================================
// 拖拽排序
// =============================================================================

function onDragStart(e: DragEvent, index: number) {
  dragIndex.value = index
  if (e.dataTransfer) {
    e.dataTransfer.effectAllowed = 'move'
    e.dataTransfer.setData('text/plain', String(index))
  }
}

function onDragOver(e: DragEvent, index: number) {
  e.preventDefault()
  if (e.dataTransfer) e.dataTransfer.dropEffect = 'move'
  dragOverIndex.value = index
}

function onDragLeave() {
  dragOverIndex.value = null
}

function onDrop(e: DragEvent, index: number) {
  e.preventDefault()
  const from = dragIndex.value
  if (from === null || from === index) {
    dragIndex.value = null
    dragOverIndex.value = null
    return
  }

  const item = pages.value.splice(from, 1)[0]
  pages.value.splice(index, 0, item)

  // 更新 currentPage
  if (currentPage.value === from) {
    currentPage.value = index
  } else if (from < currentPage.value && index >= currentPage.value) {
    currentPage.value--
  } else if (from > currentPage.value && index <= currentPage.value) {
    currentPage.value++
  }

  dragIndex.value = null
  dragOverIndex.value = null
  nextTick(() => renderCurrentPreview())
}

function onDragEnd() {
  dragIndex.value = null
  dragOverIndex.value = null
}

// =============================================================================
// 页面选择
// =============================================================================

function selectPage(index: number) {
  currentPage.value = index
  selectedAnnotId.value = null
  nextTick(() => {
    renderCurrentPreview()
    const items = thumbnailListRef.value?.querySelectorAll('.thumbnail-item')
    if (items && items[index]) {
      items[index].scrollIntoView({block: 'nearest', behavior: 'smooth'})
    }
  })
}

// =============================================================================
// 重置
// =============================================================================

function resetAll() {
  pdfFile.value = null
  pdfFileList.value = []
  pdfDoc.value = null
  pages.value = []
  pageCount.value = 0
  currentPage.value = 0
  annotations.value = []
  activeTool.value = 'select'
  selectedAnnotId.value = null
  pdfBuffer.value = null
}

// 标注颜色选项
const colorOptions = ['#1890ff', '#52c41a', '#fa8c16', '#f5222d', '#722ed1', '#000000']

function changeAnnotColor(color: string) {
  if (!selectedAnnotId.value) return
  const ann = annotations.value.find(a => a.id === selectedAnnotId.value)
  if (ann) {
    ann.color = color
    renderAnnotations()
  }
}
</script>

<template>
  <div class="pdf-edit-container">
    <!-- 未上传文件：显示拖拽上传 -->
    <n-card title="PDF编辑" style="height: 100vh; padding-top: 1rem">
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
            <n-text style="font-size: 16px">点击或者拖动 PDF 文件到该区域来上传</n-text>
            <n-p depth="3" style="margin: 8px 0 0 0">仅支持单个 .pdf 格式文件</n-p>
          </n-upload-dragger>
        </n-upload>
      </div>

      <!-- 已加载 PDF：双栏布局 -->
      <div v-else class="edit-layout">
        <!-- ====== 左栏：页面列表 ====== -->
        <div class="page-list-column">
          <div class="column-header">
            <n-text strong>页面列表</n-text>
            <n-text depth="3" style="font-size: 12px">共 {{ pageCount }} 页</n-text>
          </div>

          <!-- 顶部添加按钮 -->
          <n-button
              block dashed size="tiny"
              style="margin: 4px 0"
              @click="insertPageAfter(-1)"
          >
            ＋ 添加页面
          </n-button>

          <div class="thumbnail-list" ref="thumbnailListRef">
            <div
                v-for="(page, index) in pages"
                :key="page.index + '-' + index"
                class="thumbnail-item"
                :class="{
                active: currentPage === index,
                'drag-over': dragOverIndex === index,
                'dragging': dragIndex === index,
              }"
                :draggable="true"
                @click="selectPage(index)"
                @dragstart="onDragStart($event, index)"
                @dragover="onDragOver($event, index)"
                @dragleave="onDragLeave"
                @drop="onDrop($event, index)"
                @dragend="onDragEnd"
            >
              <!-- 拖拽把手 -->
              <div class="drag-handle">⠿</div>

              <img :src="page.thumbnail" :alt="`第 ${index + 1} 页`"/>
              <div class="page-number">第 {{ index + 1 }} 页</div>

              <!-- 操作按钮行 -->
              <div class="page-actions">
                <n-button
                    size="tiny" quaternary
                    title="顺时针旋转 90°"
                    @click.stop="rotatePage(index)"
                >
                  ↻
                </n-button>
                <n-button
                    size="tiny" quaternary type="error"
                    title="删除此页"
                    @click.stop="deletePage(index)"
                >
                  ✕
                </n-button>
              </div>

              <!-- 插入按钮（每页下方） -->
              <n-button
                  size="tiny" dashed block
                  style="margin-top: 2px; font-size: 11px;"
                  @click.stop="insertPageAfter(index)"
              >
                ＋ 插入
              </n-button>
            </div>
          </div>
        </div>

        <!-- ====== 右栏：预览 + 标注工具 ====== -->
        <div class="preview-column">
          <!-- 顶部工具栏 -->
          <div class="toolbar">
            <div class="toolbar-group">
              <button
                  v-for="tool in toolbarTools"
                  :key="tool.key"
                  class="tool-btn"
                  :class="{ active: activeTool === tool.key }"
                  :title="tool.label"
                  @click="activeTool = tool.key"
              >
                <span v-if="tool.key === 'text'" class="tool-text-icon">{{ tool.icon }}</span>
                <span v-else>{{ tool.icon }}</span>
                <span class="tool-label">{{ tool.label }}</span>
              </button>
            </div>

            <!-- 选中标注时的颜色选择 -->
            <div v-if="selectedAnnotId" class="toolbar-group">
              <span class="color-label">颜色:</span>
              <button
                  v-for="c in colorOptions"
                  :key="c"
                  class="color-btn"
                  :style="{ backgroundColor: c }"
                  :class="{ active: annotations.find(a => a.id === selectedAnnotId)?.color === c }"
                  @click="changeAnnotColor(c)"
              />
              <span class="hint-text">按 Delete 删除</span>
            </div>

            <!-- 页面导航 -->
            <div class="toolbar-group" style="margin-left: auto;">
              <n-button size="tiny" @click="currentPage > 0 && selectPage(currentPage - 1)"
                        :disabled="currentPage === 0">‹
              </n-button>
              <span class="page-indicator">{{ currentPage + 1 }} / {{ pageCount }}</span>
              <n-button size="tiny"
                        @click="currentPage < pageCount - 1 && selectPage(currentPage + 1)"
                        :disabled="currentPage >= pageCount - 1">›
              </n-button>
            </div>
          </div>

          <!-- 预览画布区 -->
          <div class="preview-area">
            <div class="canvas-wrapper">
              <!-- PDF 渲染层 -->
              <canvas ref="previewCanvasRef" class="pdf-canvas"></canvas>
              <!-- 标注叠加层 -->
              <canvas
                  ref="overlayCanvasRef"
                  class="overlay-canvas"
                  :class="{ crosshair: activeTool !== 'select' }"
                  @mousedown="onOverlayMouseDown"
                  @mousemove="onOverlayMouseMove"
                  @mouseup="onOverlayMouseUp"
                  @mouseleave="drawing = false"
              ></canvas>
            </div>
          </div>

          <!-- 底部操作 -->
          <div class="preview-footer">
            <n-button quaternary size="small" @click="resetAll">重新上传</n-button>
            <n-button type="primary" size="small" disabled title="后端 API 开发中">
              💾 保存
            </n-button>
          </div>
        </div>
      </div>

      <!-- 文字输入浮层 -->
      <div v-if="textInputVisible" class="text-input-overlay-bg" @click="textInputVisible = false">
        <div class="text-input-box" :style="{ left: textInputPos?.x + 'px', top: textInputPos?.y + 'px' }" @click.stop>
          <n-input
              v-model:value="textInputValue"
              type="textarea"
              :rows="2"
              placeholder="输入文字"
              autosize
              style="width: 200px;"
          />
          <div style="display: flex; gap: 4px; margin-top: 4px;">
            <n-button size="tiny" type="primary" @click="confirmText">确定</n-button>
            <n-button size="tiny" @click="textInputVisible = false">取消</n-button>
          </div>
        </div>
      </div>
    </n-card>
  </div>
</template>

<style scoped>
.pdf-edit-container {
  margin: 0;
  padding: 0;
  height: 100%;
}

/* ── 上传区域 ──────────────────────────────────────────────────────── */
.upload-area {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 60vh;
}

/* ── 双栏布局 ──────────────────────────────────────────────────────── */
.edit-layout {
  display: flex;
  gap: 12px;
  height: calc(100vh - 80px);
  overflow: hidden;
}

/* ── 左栏 ──────────────────────────────────────────────────────────── */
.page-list-column {
  width: 200px;
  min-width: 200px;
  display: flex;
  flex-direction: column;
  border-right: 1px solid #eee;
  padding-right: 12px;
}

.column-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  padding: 0 4px;
}

.thumbnail-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 4px 0;
}

.thumbnail-item {
  border: 2px solid #e8e8e8;
  border-radius: 6px;
  padding: 6px;
  cursor: pointer;
  text-align: center;
  transition: all 0.15s;
  background: #fafafa;
  user-select: none;
}

.thumbnail-item:hover {
  border-color: #d9d9d9;
  background: #f5f5f5;
}

.thumbnail-item.active {
  border-color: #1890ff;
  background: #f0f7ff;
}

.thumbnail-item.drag-over {
  border-color: #52c41a;
  background: #f6ffed;
}

.thumbnail-item.dragging {
  opacity: 0.4;
}

.drag-handle {
  font-size: 14px;
  color: #bbb;
  cursor: grab;
  user-select: none;
  line-height: 1;
  margin-bottom: 2px;
}

.thumbnail-item img {
  width: 100%;
  height: auto;
  border-radius: 3px;
  display: block;
}

.page-number {
  font-size: 11px;
  color: #888;
  margin: 2px 0;
}

.page-actions {
  display: flex;
  justify-content: center;
  gap: 4px;
  margin: 2px 0;
}

/* ── 右栏 ──────────────────────────────────────────────────────────── */
.preview-column {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  border-bottom: 1px solid #eee;
  margin-bottom: 8px;
  flex-wrap: wrap;
}

.toolbar-group {
  display: flex;
  align-items: center;
  gap: 4px;
}

.tool-btn {
  display: flex;
  align-items: center;
  gap: 3px;
  padding: 4px 8px;
  border: 1px solid #e8e8e8;
  border-radius: 4px;
  background: #fff;
  cursor: pointer;
  font-size: 13px;
  transition: all 0.15s;
}

.tool-btn:hover {
  border-color: #1890ff;
  color: #1890ff;
}

.tool-btn.active {
  border-color: #1890ff;
  background: #e6f7ff;
  color: #1890ff;
}

.tool-text-icon {
  font-weight: 700;
  font-family: serif;
}

.tool-label {
  font-size: 12px;
}

.color-label {
  font-size: 12px;
  color: #888;
}

.color-btn {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  border: 2px solid transparent;
  cursor: pointer;
  padding: 0;
  transition: border-color 0.15s;
}

.color-btn.active,
.color-btn:hover {
  border-color: #333;
}

.hint-text {
  font-size: 11px;
  color: #aaa;
  margin-left: 4px;
}

.page-indicator {
  font-size: 13px;
  padding: 0 8px;
  color: #666;
  white-space: nowrap;
}

/* ── 预览画布 ──────────────────────────────────────────────────────── */
.preview-area {
  flex: 1;
  display: flex;
  justify-content: center;
  align-items: flex-start;
  overflow: auto;
  background: #f5f5f5;
  border-radius: 4px;
  padding: 16px;
}

.canvas-wrapper {
  position: relative;
  display: inline-block;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.12);
}

.pdf-canvas {
  display: block;
}

.overlay-canvas {
  position: absolute;
  top: 0;
  left: 0;
  cursor: default;
}

.overlay-canvas.crosshair {
  cursor: crosshair;
}

.preview-footer {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  margin-top: 8px;
  border-top: 1px solid #eee;
}

/* ── 文字输入浮层 ──────────────────────────────────────────────────── */
.text-input-overlay-bg {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 1000;
}

.text-input-box {
  position: absolute;
  z-index: 1001;
}
</style>
