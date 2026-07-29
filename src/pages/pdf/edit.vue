<script lang="ts" setup>
/**
 * PDF 编辑页面
 * 双栏布局: 左栏—页面列表, 右栏—当前页预览+标注工具
 * 纯前端保存: 使用 pdf-lib
 */
import {ref, computed, nextTick, watch, onMounted, onBeforeUnmount} from 'vue'
import {type UploadFileInfo, useMessage} from 'naive-ui'
import {onBeforeRouteLeave} from 'vue-router'
import * as pdfjsLib from 'pdfjs-dist'
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import {PDFDocument, rgb} from 'pdf-lib'

pdfjsLib.GlobalWorkerOptions.workerSrc = workerUrl
defineProps<{ cardTitle?: string }>()
const message = useMessage()

// =============================================================================
// 类型
// =============================================================================

interface PageData {
  index: number
  thumbnail: string
  preview: string
  rotation: number       // 0/90/180/270
}

interface Annotation {
  id: string
  type: 'rect' | 'ellipse' | 'text' | 'image'
  x: number;
  y: number;
  width: number;
  height: number
  content?: string
  strokeColor: string;
  fillColor: string;
  strokeWidth: number
}

// =============================================================================
// 状态
// =============================================================================

const pdfFile = ref<File | null>(null)
const pdfFileList = ref<UploadFileInfo[]>([])
const pdfBuffer = ref<ArrayBuffer | null>(null)
const pages = ref<PageData[]>([])
const pageCount = ref(0)
const currentPage = ref(0)
const loading = ref(false)

// 标注按页存储
const annotationsMap = ref<Record<number, Annotation[]>>({})

function getAnnotations(p: number): Annotation[] {
  return annotationsMap.value[p] || []
}

function setAnnotations(p: number, list: Annotation[]) {
  annotationsMap.value[p] = list
}

function getCurrent(): Annotation[] {
  return getAnnotations(currentPage.value)
}

function setCurrent(list: Annotation[]) {
  setAnnotations(currentPage.value, list)
}

const activeTool = ref<string>('select')
const selectedAnnotId = ref<string | null>(null)
const drawing = ref(false)
const drawStart = ref({x: 0, y: 0})
const draggingAnnot = ref<string | null>(null)
const dragOffset = ref({x: 0, y: 0})

// 覆盖层 canvas
const overlayCanvasRef = ref<HTMLCanvasElement | null>(null)
const previewAreaRef = ref<HTMLDivElement | null>(null)
// 显示的预览图（替代 canvas 渲染，用 img 解决缩放问题）
const previewImgRef = ref<HTMLImageElement | null>(null)
// 预览图自然尺寸（固定坐标系参考）
const imgNaturalSize = ref({w: 0, h: 0})

// 拖拽页面
const dragIndex = ref<number | null>(null)
const dragOverIndex = ref<number | null>(null)
const thumbnailListRef = ref<HTMLElement | null>(null)

// 样式
const stylePrefs = ref({strokeColor: '#1890ff', fillColor: '#1890ff', strokeWidth: 2})
const fillOpacity = ref(0.15)
const showStylePanel = ref(false)

// 未保存风险追踪
const dirty = ref(false)

function markDirty() {
  dirty.value = true
}

// =============================================================================
// 计算
// =============================================================================

const currentPageData = computed(() => pages.value[currentPage.value] || null)

const toolbarTools = [
  {key: 'select', icon: '↖️', label: '选择'},
  {key: 'rect', icon: '▭', label: '矩形'},
  {key: 'ellipse', icon: '⬭', label: '椭圆'},
]

const colorOptions = ['#1890ff', '#52c41a', '#fa8c16', '#f5222d', '#722ed1', '#000000', '#ffffff', '#8c8c8c']

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
  loading.value = true
  dirty.value = false
  try {
    const ab = await pdfFile.value.arrayBuffer()
    pdfBuffer.value = ab
    const pdf = await pdfjsLib.getDocument({data: ab.slice(0)}).promise
    pageCount.value = pdf.numPages
    pages.value = []
    for (let i = 1; i <= pdf.numPages; i++) {
      const page = await pdf.getPage(i)
      const tScale = 0.25, pScale = 1.2
      const tv = page.getViewport({scale: tScale})
      const tc = document.createElement('canvas')
      tc.width = tv.width;
      tc.height = tv.height
      await (page.render({canvasContext: tc.getContext('2d')!, viewport: tv} as any)).promise

      const pv = page.getViewport({scale: pScale})
      const pc = document.createElement('canvas')
      pc.width = pv.width;
      pc.height = pv.height
      await (page.render({canvasContext: pc.getContext('2d')!, viewport: pv} as any)).promise

      pages.value.push({
        index: i - 1,
        thumbnail: tc.toDataURL('image/jpeg', 0.7),
        preview: pc.toDataURL('image/jpeg', 0.85),
        rotation: 0,
      })
    }
    annotationsMap.value = {}
    currentPage.value = 0
    message.success(`已加载 ${pageCount.value} 页`)
  } catch (e) {
    console.error(e)
    message.error('加载 PDF 失败')
  } finally {
    loading.value = false
  }
}

// =============================================================================
// 预览渲染 — 使用 <img> + 覆盖 canvas
// =============================================================================

// 当 img 加载完成或页面切换时，重新计算覆盖层尺寸并重绘标注
watch([currentPageData, previewImgRef], () => {
  if (previewImgRef.value) {
    previewImgRef.value.onload = () => syncOverlay()
  }
  nextTick(() => syncOverlay())
})

function syncOverlay() {
  const img = previewImgRef.value
  const overlay = overlayCanvasRef.value
  if (!img || !overlay || !img.complete || img.naturalWidth === 0) return
  // 记录自然尺寸（固定坐标系基准）
  imgNaturalSize.value = {w: img.naturalWidth, h: img.naturalHeight}
  // 匹配 overlay canvas 到 img 的显示尺寸
  const rect = img.getBoundingClientRect()
  overlay.width = Math.round(rect.width)
  overlay.height = Math.round(rect.height)
  renderAnnotations()
}

// 窗口缩放时同步 overlay
const _resizeHandler = () => syncOverlay()
// (resize listener 注册在 onMounted 中)

// 从鼠标事件获取 overlay canvas 坐标
function getCanvasPos(e: MouseEvent): { x: number; y: number } {
  const overlay = overlayCanvasRef.value
  if (!overlay) return {x: 0, y: 0}
  const r = overlay.getBoundingClientRect()
  return {x: e.clientX - r.left, y: e.clientY - r.top}
}

// ── 自然坐标 ↔ 显示坐标 转换 ──────────────────────────────────────────
// 标注以自然图像像素存储（固定），渲染时缩放到当前显示尺寸
function _natToDisplay(nat: { x: number; y: number; w?: number; h?: number; width?: number; height?: number }) {
  const ov = overlayCanvasRef.value
  const ns = imgNaturalSize.value
  if (!ov || !ns.w || !ns.h) return {x: nat.x, y: nat.y, w: (nat.w ?? nat.width ?? 0), h: (nat.h ?? nat.height ?? 0)}
  const sx = ov.width / ns.w, sy = ov.height / ns.h
  const w = nat.w ?? nat.width ?? 0
  const h = nat.h ?? nat.height ?? 0
  return {x: nat.x * sx, y: nat.y * sy, w: w * sx, h: h * sy}
}

function _displayToNat(display: { x: number; y: number }) {
  const ov = overlayCanvasRef.value
  const ns = imgNaturalSize.value
  if (!ov || !ns.w || !ns.h) return display
  return {
    x: display.x * (ns.w / ov.width),
    y: display.y * (ns.h / ov.height),
  }
}

// =============================================================================
// 标注渲染
// =============================================================================

function renderAnnotations() {
  const overlay = overlayCanvasRef.value
  if (!overlay) return
  const ctx = overlay.getContext('2d')!
  ctx.clearRect(0, 0, overlay.width, overlay.height)

  const anns = getCurrent()
  for (const a of anns) {
    const d = _natToDisplay(a)
    ctx.strokeStyle = a.id === selectedAnnotId.value ? '#ff4d4f' : (a.strokeColor || '#1890ff')
    ctx.lineWidth = a.id === selectedAnnotId.value ? (a.strokeWidth || 2) + 2 : (a.strokeWidth || 2)
    ctx.fillStyle = _hexToRgba(a.fillColor || a.strokeColor || '#1890ff', fillOpacity.value)

    switch (a.type) {
      case 'rect':
        ctx.fillRect(d.x, d.y, d.w!, d.h!)
        ctx.strokeRect(d.x, d.y, d.w!, d.h!)
        break
      case 'ellipse':
        ctx.beginPath()
        ctx.ellipse(d.x + d.w! / 2, d.y + d.h! / 2, d.w! / 2, d.h! / 2, 0, 0, Math.PI * 2)
        ctx.fill()
        ctx.stroke()
        break
      case 'text':
        ctx.font = `${Math.max(14, (a.strokeWidth || 2) * 8)}px sans-serif`
        ctx.fillStyle = a.strokeColor || '#1890ff'
        ctx.fillText(a.content || '', d.x, d.y + 16)
        break
      case 'image':
        if (a.content) {
          const img = new Image()
          img.onload = () => ctx.drawImage(img, d.x, d.y, d.w!, d.h!)
          img.src = a.content
        }
        break
    }

    // 选中控制框
    if (a.id === selectedAnnotId.value) {
      ctx.strokeStyle = '#ff4d4f'
      ctx.lineWidth = 1
      ctx.setLineDash([4, 4])
      ctx.strokeRect(d.x, d.y, d.w!, d.h!)
      ctx.setLineDash([])
    }
  }
}

// =============================================================================
// 鼠标事件
// =============================================================================

function onOverlayMouseDown(e: MouseEvent) {
  const pos = getCanvasPos(e)
  if (activeTool.value === 'select') {
    for (let i = getCurrent().length - 1; i >= 0; i--) {
      const a = getCurrent()[i]
      if (_hitTest(a, _displayToNat(pos).x, _displayToNat(pos).y)) {
        selectedAnnotId.value = a.id
        draggingAnnot.value = a.id
        const clickNat = _displayToNat(pos)
        dragOffset.value = {x: clickNat.x - a.x, y: clickNat.y - a.y}
        renderAnnotations()
        return
      }
    }
    selectedAnnotId.value = null;
    renderAnnotations()
    return
  }
  drawing.value = true;
  drawStart.value = pos;
  selectedAnnotId.value = null
}

function onOverlayMouseMove(e: MouseEvent) {
  const pos = getCanvasPos(e)
  if (draggingAnnot.value) {
    const a = getCurrent().find(a => a.id === draggingAnnot.value)
    if (a) {
      const nat = _displayToNat({x: pos.x, y: pos.y})
      a.x = nat.x - dragOffset.value.x
      a.y = nat.y - dragOffset.value.y
      renderAnnotations()
    }
    return
  }
  if (!drawing.value) return
  const overlay = overlayCanvasRef.value
  if (!overlay) return
  const ctx = overlay.getContext('2d')!
  const x = Math.min(drawStart.value.x, pos.x);
  const y = Math.min(drawStart.value.y, pos.y)
  const w = Math.abs(pos.x - drawStart.value.x);
  const h = Math.abs(pos.y - drawStart.value.y)
  ctx.clearRect(0, 0, overlay.width, overlay.height)
  renderAnnotations()
  ctx.strokeStyle = stylePrefs.value.strokeColor
  ctx.lineWidth = stylePrefs.value.strokeWidth;
  ctx.setLineDash([5, 5])
  ctx.fillStyle = _hexToRgba(stylePrefs.value.fillColor, fillOpacity.value)
  if (activeTool.value === 'rect') {
    ctx.fillRect(x, y, w, h);
    ctx.strokeRect(x, y, w, h)
  } else if (activeTool.value === 'ellipse') {
    ctx.beginPath();
    ctx.ellipse(x + w / 2, y + h / 2, w / 2, h / 2, 0, 0, Math.PI * 2)
    ctx.fill();
    ctx.stroke()
  }
  ctx.setLineDash([])
}

function onOverlayMouseUp() {
  if (draggingAnnot.value) {
    draggingAnnot.value = null;
    return
  }
  if (!drawing.value) return;
  drawing.value = false
  if (!_lastPos) return
  const w = Math.abs(_lastPos.x - drawStart.value.x);
  const h = Math.abs(_lastPos.y - drawStart.value.y)
  if (w < 5 && h < 5) return
  // 转换为自然坐标存储
  const rawX = Math.min(drawStart.value.x, _lastPos.x);
  const rawY = Math.min(drawStart.value.y, _lastPos.y)
  const nat = _displayToNat({x: rawX, y: rawY})
  const natSize = _displayToNat({x: rawX + w, y: rawY + h})
  const natW = natSize.x - nat.x;
  const natH = natSize.y - nat.y
  const id = genId();
  const {strokeColor, fillColor, strokeWidth} = stylePrefs.value
  const anns = [...getCurrent()]
  anns.push({
    id,
    type: activeTool.value as 'rect' | 'ellipse',
    x: nat.x,
    y: nat.y,
    width: natW,
    height: natH,
    strokeColor,
    fillColor,
    strokeWidth
  })
  setCurrent(anns)
  selectedAnnotId.value = id;
  markDirty();
  renderAnnotations()
}

let _lastPos = {x: 0, y: 0}

function onOverlayMouseMoveWithLast(e: MouseEvent) {
  _lastPos = getCanvasPos(e);
  onOverlayMouseMove(e)
}

function _hitTest(a: Annotation, x: number, y: number): boolean {
  if (a.type === 'text') return x >= a.x && x <= a.x + 200 && y >= a.y - 16 && y <= a.y + 8
  return x >= a.x && x <= a.x + a.width && y >= a.y && y <= a.y + a.height
}

function _hexToRgba(hex: string, alpha: number): string {
  const c = hex.replace('#', '');
  const r = parseInt(c.slice(0, 2), 16)
  const g = parseInt(c.slice(2, 4), 16);
  const b = parseInt(c.slice(4, 6), 16)
  return `rgba(${r},${g},${b},${alpha})`
}

function genId(): string {
  return `ann_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
}

// =============================================================================
// 键盘操作
// =============================================================================

function onKeyDown(e: KeyboardEvent) {
  if ((e.key === 'Delete' || e.key === 'Backspace') && selectedAnnotId.value) {
    if (['INPUT', 'TEXTAREA'].includes(document.activeElement?.tagName || '')) return
    setCurrent(getCurrent().filter(a => a.id !== selectedAnnotId.value))
    selectedAnnotId.value = null;
    markDirty();
    renderAnnotations()
  }
  if (e.key === 'Escape') {
    activeTool.value = 'select';
    selectedAnnotId.value = null;
    renderAnnotations()
  }
}

onMounted(() => {
  window.addEventListener('keydown', onKeyDown)
  window.addEventListener('resize', _resizeHandler)
})
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeyDown)
  window.removeEventListener('resize', _resizeHandler)
})

// =============================================================================
// 文字确认
// =============================================================================


// =============================================================================
// 页面操作
// =============================================================================

function rotatePage(index: number) {
  pages.value[index].rotation = (pages.value[index].rotation + 90) % 360
  markDirty()
  if (index === currentPage.value) nextTick(() => syncOverlay())
}

function deletePage(index: number) {
  if (pages.value.length <= 1) {
    message.warning('至少保留一页');
    return
  }
  pages.value.splice(index, 1);
  pageCount.value--
  const newMap: Record<number, Annotation[]> = {}
  for (const k of Object.keys(annotationsMap.value)) {
    const ki = Number(k)
    newMap[ki > index ? ki - 1 : ki] = annotationsMap.value[ki]
  }
  annotationsMap.value = newMap
  if (currentPage.value >= pageCount.value) currentPage.value = pageCount.value - 1
  markDirty();
  message.success(`已删除第 ${index + 1} 页`)
}


function selectPage(index: number) {
  currentPage.value = index;
  selectedAnnotId.value = null
  nextTick(() => {
    syncOverlay()
    const items = thumbnailListRef.value?.querySelectorAll('.thumbnail-item')
    if (items?.[index]) items[index].scrollIntoView({block: 'nearest', behavior: 'smooth'})
  })
}

// =============================================================================
// 拖拽排序
// =============================================================================

function onDragStart(e: DragEvent, index: number) {
  dragIndex.value = index;
  e.dataTransfer!.effectAllowed = 'move';
  e.dataTransfer!.setData('text/plain', String(index))
}

function onDragOver(e: DragEvent, index: number) {
  e.preventDefault();
  dragOverIndex.value = index
}

function onDragLeave() {
  dragOverIndex.value = null
}

function onDrop(e: DragEvent, index: number) {
  e.preventDefault();
  const from = dragIndex.value
  if (from === null || from === index) {
    dragIndex.value = dragOverIndex.value = null;
    return
  }
  const item = pages.value.splice(from, 1)[0];
  pages.value.splice(index, 0, item)
  const newMap: Record<number, Annotation[]> = {}
  for (const k of Object.keys(annotationsMap.value).map(Number)) {
    let nk = k;
    if (k === from) nk = index; else if (from < k && k <= index) nk = k - 1; else if (from > k && k >= index) nk = k + 1
    newMap[nk] = annotationsMap.value[k]
  }
  annotationsMap.value = newMap
  if (currentPage.value === from) currentPage.value = index
  else if (from < currentPage.value && index >= currentPage.value) currentPage.value--
  else if (from > currentPage.value && index <= currentPage.value) currentPage.value++
  dragIndex.value = dragOverIndex.value = null;
  markDirty();
  nextTick(() => syncOverlay())
}

function onDragEnd() {
  dragIndex.value = dragOverIndex.value = null
}

// =============================================================================
// 样式
// =============================================================================

function applyStyleToSelected() {
  if (!selectedAnnotId.value) return
  const a = getCurrent().find(a => a.id === selectedAnnotId.value)
  if (a) {
    a.strokeColor = stylePrefs.value.strokeColor;
    a.fillColor = stylePrefs.value.fillColor;
    a.strokeWidth = stylePrefs.value.strokeWidth;
    markDirty();
    renderAnnotations()
  }
}

watch(selectedAnnotId, (id) => {
  if (!id) return
  const a = getCurrent().find(a => a.id === id)
  if (a) {
    stylePrefs.value.strokeColor = a.strokeColor;
    stylePrefs.value.fillColor = a.fillColor;
    stylePrefs.value.strokeWidth = a.strokeWidth
  }
})

// =============================================================================
// 保存 — 使用 showSaveFilePicker 原生对话框
// =============================================================================

async function handleSave() {
  if (!pdfBuffer.value) {
    message.error('无 PDF 数据');
    return
  }

  try {
    const pdfDoc = await PDFDocument.load(pdfBuffer.value!)
    const totalOrig = pdfDoc.getPageCount()
    const pageIndices: number[] = []
    for (const p of pages.value) {
      if (p.index >= 0 && p.index < totalOrig) pageIndices.push(p.index)
    }
    const outPdf = await PDFDocument.create()
    const allPages = await outPdf.copyPages(pdfDoc, pageIndices)
    for (let i = 0; i < allPages.length; i++) {
      const p = allPages[i];
      const origIdx = pageIndices[i];
      const pd = pages.value.find(x => x.index === origIdx)
      if (pd?.rotation) p.setRotation({type: 'degrees', angle: pd.rotation} as any)
      for (const ann of (annotationsMap.value[i] || [])) await _embedAnnotation(outPdf, p, ann)
      outPdf.addPage(p)
    }
    const pdfBytes = await outPdf.save()

    // 使用原生保存对话框
    const suggestedName = pdfFile.value?.name?.replace('.pdf', '_edited.pdf') || 'edited.pdf'

    if ('showSaveFilePicker' in window) {
      const handle = await (window as any).showSaveFilePicker({
        suggestedName,
        types: [{description: 'PDF 文件', accept: {'application/pdf': ['.pdf']}}],
      })
      const writable = await handle.createWritable()
      await writable.write(pdfBytes)
      await writable.close()
    } else {
      // 回退：浏览器下载
      const blob = new Blob([pdfBytes], {type: 'application/pdf'})
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a');
      a.href = url;
      a.download = suggestedName;
      a.click()
      URL.revokeObjectURL(url)
    }
    dirty.value = false
    message.success('保存成功')
  } catch (err: any) {
    if (err?.name === 'AbortError' || err?.message?.includes('abort')) return
    console.error(err)
    message.error('保存失败: ' + (err.message || String(err)))
  }
}

async function _embedAnnotation(pdfDoc: PDFDocument, page: any, ann: Annotation) {
  const height = page.getSize().height
  // 自然图像像素 → PDF 点: 预览图以 scale=1.2 渲染，故 1px = 1/1.2 pt
  const s = 1 / 1.2
  const x = ann.x * s;
  const y = height - (ann.y + ann.height) * s
  const w = ann.width * s;
  const h = ann.height * s
  const sC = _ph(ann.strokeColor || '#1890ff');
  const fC = _ph(ann.fillColor || ann.strokeColor || '#1890ff')
  switch (ann.type) {
    case 'rect':
      page.drawRectangle({
        x,
        y,
        width: w,
        height: h,
        borderColor: rgb(sC[0], sC[1], sC[2]),
        borderWidth: Math.max(1, ann.strokeWidth || 2),
        color: rgb(fC[0], fC[1], fC[2]),
        opacity: fillOpacity.value
      })
      break
    case 'ellipse':
      page.drawEllipse({
        x: x + w / 2,
        y: y + h / 2,
        xScale: w / 2,
        yScale: h / 2,
        borderColor: rgb(sC[0], sC[1], sC[2]),
        borderWidth: Math.max(1, ann.strokeWidth || 2),
        color: rgb(fC[0], fC[1], fC[2]),
        opacity: fillOpacity.value
      })
      break
    case 'text':
      // 用 canvas 渲染文字为图片嵌入，避免中文字符编码问题
      try {
        const fontSize = Math.max(14, (ann.strokeWidth || 2) * 8)
        const c = document.createElement('canvas')
        const ctx = c.getContext('2d')!
        ctx.font = `${fontSize}px sans-serif`
        const metrics = ctx.measureText(ann.content || '')
        c.width = Math.ceil(metrics.width) + 8
        c.height = Math.ceil(fontSize * 1.4)
        ctx.font = `${fontSize}px sans-serif`
        ctx.fillStyle = ann.strokeColor || '#1890ff'
        ctx.textBaseline = 'top'
        ctx.fillText(ann.content || '', 4, 4)
        const pngData = c.toDataURL('image/png').split(',')[1]
        const img = pdfDoc.embedPng(pngData)
        // 图片左上角对齐标注区左上角（PDF y 从底算）
        const imgW = c.width * s
        const imgH = c.height * s
        const topY = height - ann.y * s
        page.drawImage(img, {x, y: topY - imgH, width: imgW, height: imgH})
      } catch { /* 文字渲染失败则忽略 */
      }
      break
  }
}

function _ph(hex: string): [number, number, number] {
  const c = hex.replace('#', '');
  return [parseInt(c.slice(0, 2), 16) / 255, parseInt(c.slice(2, 4), 16) / 255, parseInt(c.slice(4, 6), 16) / 255]
}

// =============================================================================
// 重置
// =============================================================================

function resetAll() {
  if (dirty.value && !window.confirm('当前有未保存的修改，确定重新上传？')) return
  pdfFile.value = null;
  pdfFileList.value = [];
  pdfBuffer.value = null;
  pages.value = []
  pageCount.value = 0;
  currentPage.value = 0;
  annotationsMap.value = {}
  activeTool.value = 'select';
  selectedAnnotId.value = null;
  dirty.value = false
}

// 离开当前工具箱页面时提示未保存
onBeforeRouteLeave((_to, _from, next) => {
  if (dirty.value && !window.confirm('当前有未保存的修改，确定离开？')) {
    next(false)
  } else {
    next()
  }
})
</script>

<template>
  <div class="pdf-edit-container">
    <n-card title="PDF编辑" style="height: 100vh; padding-top: 1rem">
      <!-- 未上传 -->
      <div v-if="!pdfFile" class="upload-area">
        <n-upload :custom-request="pdfCustomRequest" :file-list="pdfFileList" :max="1" accept=".pdf" dragger
                  @change="handlePdfChange">
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

      <!-- 已加载 -->
      <div v-else class="edit-layout">
        <!-- ====== 左栏 ====== -->
        <div class="page-list-column">
          <div class="column-header">
            <n-text strong>页面列表</n-text>
            <n-text depth="3" style="font-size: 12px">共 {{ pageCount }} 页</n-text>
            <n-text v-if="dirty" type="warning" style="font-size: 11px">● 未保存</n-text>
          </div>
          <div class="thumbnail-list" ref="thumbnailListRef">
            <div v-for="(page, index) in pages" :key="'p'+index"
                 class="thumbnail-item"
                 :class="{active: currentPage===index, 'drag-over': dragOverIndex===index, dragging: dragIndex===index}"
                 :draggable="true" @click="selectPage(index)"
                 @dragstart="onDragStart($event, index)" @dragover="onDragOver($event, index)" @dragleave="onDragLeave"
                 @drop="onDrop($event, index)" @dragend="onDragEnd">
              <div class="drag-handle">⠿</div>
              <img :src="page.thumbnail" :alt="`第 ${index+1} 页`"/>
              <div class="page-number">第 {{ index + 1 }} 页</div>
              <div class="page-actions">
                <n-button size="tiny" quaternary title="顺时针旋转 90°" @click.stop="rotatePage(index)">↻</n-button>
                <n-button size="tiny" quaternary type="error" title="删除此页" @click.stop="deletePage(index)">✕
                </n-button>
              </div>
            </div>
          </div>
        </div>

        <!-- ====== 右栏 ====== -->
        <div class="preview-column">
          <!-- 工具栏 -->
          <div class="toolbar">
            <div class="toolbar-group">
              <button v-for="t in toolbarTools" :key="t.key" class="tool-btn" :class="{active: activeTool===t.key}"
                      :title="t.label" @click="activeTool=t.key">
                <span :class="t.key==='text'?'tool-text-icon':''">{{ t.icon }}</span>
                <span class="tool-label">{{ t.label }}</span>
              </button>
            </div>
            <div class="toolbar-group">
              <n-button size="tiny" quaternary @click="showStylePanel = !showStylePanel">🎨 样式</n-button>
            </div>
            <div v-if="selectedAnnotId" class="toolbar-group">
              <span class="hint-text">Del 删除</span>
            </div>
            <div class="toolbar-group" style="margin-left:auto">
              <n-button size="tiny" :disabled="currentPage===0" @click="selectPage(currentPage-1)">‹</n-button>
              <span class="page-indicator">{{ currentPage + 1 }}/{{ pageCount }}</span>
              <n-button size="tiny" :disabled="currentPage>=pageCount-1" @click="selectPage(currentPage+1)">›</n-button>
            </div>
          </div>

          <!-- 样式面板 -->
          <div v-if="showStylePanel" class="style-panel">
            <div class="style-row"><span class="style-label">描边</span>
              <div class="color-dots">
                <button v-for="c in colorOptions" :key="c" class="color-btn" :style="{backgroundColor:c}"
                        :class="{active: stylePrefs.strokeColor===c}"
                        @click="stylePrefs.strokeColor=c; selectedAnnotId&&applyStyleToSelected()"/>
              </div>
            </div>
            <div class="style-row"><span class="style-label">填充</span>
              <div class="color-dots">
                <button v-for="c in colorOptions" :key="c" class="color-btn" :style="{backgroundColor:c}"
                        :class="{active: stylePrefs.fillColor===c}"
                        @click="stylePrefs.fillColor=c; selectedAnnotId&&applyStyleToSelected()"/>
              </div>
            </div>
            <div class="style-row"><span class="style-label">透明度</span>
              <n-slider v-model:value="fillOpacity" :min="0" :max="0.6" :step="0.05" style="width:120px"/>
              <span style="font-size:12px;margin-left:4px;color:#888">{{ Math.round(fillOpacity * 100) }}%</span>
            </div>
            <div class="style-row"><span class="style-label">线宽</span>
              <n-input-number v-model:value="stylePrefs.strokeWidth" :min="0.5" :max="10" :step="0.5" size="tiny"
                              style="width:70px"/>
              <n-button size="tiny" quaternary style="margin-left:4px" @click="selectedAnnotId&&applyStyleToSelected()">
                应用
              </n-button>
            </div>
          </div>

          <!-- 预览区 -->
          <div class="preview-area" ref="previewAreaRef">
            <!-- 加载中 -->
            <div v-if="loading" class="loading-overlay">
              <n-spin size="large"/>
              <n-text style="margin-top:8px;color:#888">正在加载 PDF…</n-text>
            </div>
            <!-- 空页提示 -->
            <div v-else-if="currentPageData && !currentPageData.preview" class="loading-overlay">
              <n-text style="color:#888">空白页</n-text>
            </div>
            <!-- 预览图 + 覆盖层 -->
            <div v-else-if="currentPageData" class="canvas-wrapper">
              <img ref="previewImgRef" :src="currentPageData.preview" class="pdf-preview-img"
                   :style="{transform: `rotate(${currentPageData.rotation}deg)`}"
                   alt="预览"/>
              <canvas ref="overlayCanvasRef" class="overlay-canvas"
                      :style="{transform: `rotate(${currentPageData.rotation}deg)`}"
                      :class="{crosshair: activeTool!=='select'}"
                      @mousedown="onOverlayMouseDown"
                      @mousemove="onOverlayMouseMoveWithLast"
                      @mouseup="onOverlayMouseUp"
                      @mouseleave="drawing=false;draggingAnnot=null"/>
            </div>
          </div>

          <!-- 底部 -->
          <div class="preview-footer">
            <n-button quaternary size="small" @click="resetAll">重新上传</n-button>
            <n-button type="primary" size="small" @click="handleSave">💾 保存</n-button>
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

.upload-area {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 60vh;
}

.edit-layout {
  display: flex;
  height: calc(100vh - 7rem);
  gap: 12px;
  overflow: hidden;
  padding-bottom: 0;
}

/* 左栏 */
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
  transition: all .15s;
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
  opacity: .4;
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

/* 右栏 */
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
  transition: all .15s;
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

/* 样式面板 */
.style-panel {
  padding: 8px 12px;
  background: #fafafa;
  border: 1px solid #eee;
  border-radius: 4px;
  margin-bottom: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.style-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.style-label {
  font-size: 12px;
  color: #888;
  min-width: 40px;
}

.color-dots {
  display: flex;
  gap: 3px;
  flex-wrap: wrap;
}

.color-btn {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  border: 2px solid transparent;
  cursor: pointer;
  padding: 0;
  transition: border-color .15s;
}

.color-btn.active, .color-btn:hover {
  border-color: #333;
}

/* 预览区 */
.preview-area {
  flex: 1;
  display: flex;
  justify-content: center;
  align-items: center;
  overflow: auto;
  background: #f5f5f5;
  border-radius: 4px;
  padding: 16px;
  position: relative;
  min-height: 200px;
}

.loading-overlay {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
}

.canvas-wrapper {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 12px rgba(0, 0, 0, .12);
  max-width: 100%;
  max-height: 100%;
}

.pdf-preview-img {
  display: block;
  max-width: 100%;
  max-height: 70vh;
  object-fit: contain;
}

.overlay-canvas {
  position: absolute;
  top: 0;
  left: 0;
  cursor: default;
  pointer-events: auto;
  width: 100%;
  height: 100%;
}

.overlay-canvas.crosshair {
  cursor: crosshair;
}

.preview-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  margin-top: 8px;
  border-top: 1px solid #eee;
}
</style>
