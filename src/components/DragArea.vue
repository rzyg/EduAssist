<script setup lang="ts">
import {getCurrentWindow} from '@tauri-apps/api/window'

const appWindow = getCurrentWindow()

const handleMinimize = async () => {
  await appWindow.minimize()
}

const handleMaximize = async () => {
  const isMaximized = await appWindow.isMaximized()
  if (isMaximized) {
    await appWindow.unmaximize()
  } else {
    await appWindow.maximize()
  }
}

const handleClose = async () => {
  await appWindow.close()
}

const handleDrag = (e: MouseEvent) => {
  if (e.button === 0) {
    appWindow.startDragging()
  }
}
</script>

<template>
  <div class="titlebar">
    <div class="drag-area" @mousedown="handleDrag"></div>
    <div class="controls">
      <button class="control-btn minimize" @click="handleMinimize" title="最小化">
        <span class="dot yellow-dot"></span>
      </button>
      <button class="control-btn maximize" @click="handleMaximize" title="最大化">
        <span class="dot green-dot"></span>
      </button>
      <button class="control-btn close" @click="handleClose" title="关闭">
        <span class="dot red-dot"></span>
      </button>
    </div>

  </div>
</template>

<style scoped>
.titlebar {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 1.75rem;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  z-index: 9999;
  background: transparent;
}

.drag-area {
  flex: 1;
  height: 100%;
  cursor: default;
}

.controls {
  display: flex;
  gap: 1rem;
  padding-right: 0.75rem;
  height: 100%;
  align-items: center;
}

.control-btn {
  width: 0.75rem;
  height: 0.75rem;
  border-radius: 50%;
  border: none;
  padding: 0;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
  position: relative;
}

.control-btn::before {
  content: '';
  position: absolute;
  inset: -2px;
  border-radius: 50%;
  opacity: 0;
  transition: opacity 0.2s ease;
}

.control-btn:hover::before {
  opacity: 1;
}

.dot {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  transition: all 0.2s ease;
}

.yellow-dot {
  background-color: #febc2e;
}

.green-dot {
  background-color: #28c840;
}

.red-dot {
  background-color: #ff5f57;
}

.control-btn:hover .yellow-dot {
  background-color: #f5a623;
}

.control-btn:hover .green-dot {
  background-color: #23b839;
}

.control-btn:hover .red-dot {
  background-color: #ee4d45;
}

.control-btn:active {
  transform: scale(0.9);
}
</style>
