<script setup lang="ts">
import type {MenuOption} from 'naive-ui'
import type {Component} from 'vue'
import type {GlobalThemeOverrides} from 'naive-ui'
import {NMessageProvider, NIcon, createDiscreteApi} from 'naive-ui'
import {h, ref, watch, onMounted, onUnmounted} from 'vue'
import {useRouter, useRoute} from 'vue-router'
import {getApiBase} from '../config'
import DragArea from './DragArea.vue'
import logoSrc from '../assets/logo.png'

const {message} = createDiscreteApi(['message'])

// ── 主题 ──
const themeOverrides: GlobalThemeOverrides = {
  common: {
    primaryColor: '#3288ed',
    primaryColorHover: '#55a1f8',
    primaryColorPressed: '#2a6fca',
    primaryColorSuppl: '#5aa5fa',
    successColor: '#4caf50',
    successColorHover: '#66bb6a',
    successColorPressed: '#3d9e41',
    successColorSuppl: '#81c784',
    warningColor: '#ff9800',
    warningColorHover: '#ffa726',
    warningColorPressed: '#f57c00',
    warningColorSuppl: '#ffb74d',
    errorColor: '#f44336',
    errorColorHover: '#ef5350',
    errorColorPressed: '#d32f2f',
    errorColorSuppl: '#e57373',
    infoColor: '#8ea3e8',
    infoColorHover: '#a4b6f0',
    infoColorPressed: '#3f51b5',
    infoColorSuppl: '#9fa8da',
  },
}

// ── 图标渲染 ──
import {
  Home as HomeIcon,
  Award as AwardIcon,
  Books as BooksIcon,
  Book2 as PdfIcon,
  Businessplan as AllowanceIcon,
  InfoCircle as AboutIcon,
  Settings as SettingIcon
} from '@vicons/tabler'

function renderIcon(icon: Component) {
  return () => h(NIcon, null, {default: () => h(icon)})
}

// ── 路由 & 菜单 ──
const router = useRouter()
const route = useRoute()
const activeKey = ref<string | null>(route.name as string || 'home')
const collapsed = ref(false)

watch(activeKey, (newKey) => {
  if (newKey) router.push({name: newKey})
})
watch(() => route.name, (newName) => {
  activeKey.value = newName as string
})

const topMenuOptions: MenuOption[] = [
  {childrenLabel: '主页', childrenKey: 'home', icon: renderIcon(HomeIcon)},
  {
    childrenLabel: '成绩', childrenKey: 'score', icon: renderIcon(AwardIcon),
    childrenChildren: [
      {childrenLabel: '成绩单', childrenKey: 'transcript'},
      {childrenLabel: '分析', childrenKey: 'analysis'},
    ],
  },
  {childrenLabel: '刷课', childrenKey: 'fuck-the-online-class', icon: renderIcon(BooksIcon)},
  {childrenLabel: 'PDF编辑', childrenKey: 'edit-pdf', icon: renderIcon(PdfIcon)},
  {childrenLabel: '津贴', childrenKey: 'allowance', icon: renderIcon(AllowanceIcon)},
]

const bottomMenuOptions: MenuOption[] = [
  {childrenLabel: '关于', childrenKey: 'about', icon: renderIcon(AboutIcon)},
  {childrenLabel: '设置', childrenKey: 'setting', icon: renderIcon(SettingIcon)},
]

// ── 运行时健康检测 ──
let backendUrl = 'http://127.0.0.1:8000'
let healthCheckTimer: ReturnType<typeof setInterval> | null = null
let healthMsg: any = null
let healthFailCount = 0
const MAX_FAILS_BEFORE_RESTART = 3

async function checkAlive(): Promise<boolean> {
  try {
    const res = await fetch(`${backendUrl}/health`, {signal: AbortSignal.timeout(1500)})
    return res.ok && (await res.json()).status === 'ok'
  } catch {
    return false
  }
}

async function checkHealth() {
  if (await checkAlive()) {
    // 之前失联过，现在恢复了 → 给个成功提示
    if (healthMsg) {
      message.success('后端服务已恢复')
    }
    healthFailCount = 0
    healthMsg?.destroy()
    healthMsg = null
  } else {
    healthFailCount++
    const remain = MAX_FAILS_BEFORE_RESTART - healthFailCount
    const text = remain > 0
        ? `后端连接失败，${remain} 次后将尝试重新拉起`
        : '正在尝试重新拉起后端…'

    // 销毁旧消息重建（Naive UI message 不支持动态更新 content）
    healthMsg?.destroy()
    healthMsg = message.warning(text, {duration: 0})

    if (healthFailCount >= MAX_FAILS_BEFORE_RESTART) {
      healthFailCount = 0
      try {
        const {invoke} = await import('@tauri-apps/api/core')
        await invoke('start_backend')
      } catch { /* 非 Tauri 环境 */
      }
    }
  }
}

onMounted(async () => {
  backendUrl = await getApiBase()
  healthCheckTimer = setInterval(checkHealth, 5000)
})

onUnmounted(() => {
  if (healthCheckTimer) clearInterval(healthCheckTimer)
  healthMsg?.destroy()
})
</script>

<template>
  <n-config-provider :theme-overrides="themeOverrides">
    <n-message-provider>
      <DragArea/>
      <n-layout has-sider class="sider">
        <n-layout-sider
            bordered collapse-mode="width" :collapsed-width="64" :width="220"
            :collapsed="collapsed" show-trigger
            @collapse="collapsed = true" @expand="collapsed = false"
            class="sider-content"
        >
          <div class="menu-wrapper">
            <div class="sider-header">
              <img class="logo" :src="logoSrc" alt="logo"
                   :style="{ left: collapsed ? '20%' : '17%' }">
              <transition name="fade">
                <p v-show="!collapsed" class="title">下班工具箱</p>
              </transition>
            </div>
            <n-menu v-model:value="activeKey" :collapsed="collapsed" :collapsed-width="64"
                    :collapsed-icon-size="22" :options="topMenuOptions"
                    key-field="childrenKey" label-field="childrenLabel" children-field="childrenChildren"/>
            <n-menu v-model:value="activeKey" :collapsed="collapsed" :collapsed-width="64"
                    :collapsed-icon-size="22" :options="bottomMenuOptions"
                    key-field="childrenKey" label-field="childrenLabel" children-field="childrenChildren"
                    class="bottom-menu"/>
          </div>
        </n-layout-sider>
        <n-layout class="main-content">
          <router-view v-slot="{ Component }">
            <transition name="zoom-fade" mode="out-in">
              <component :is="Component" :key="route.path"/>
            </transition>
          </router-view>
        </n-layout>
      </n-layout>
    </n-message-provider>
  </n-config-provider>
</template>

<style scoped>
.sider {
  height: 100vh;
  user-select: none;
}

.main-content {
  height: 100vh;
  padding-top: 1rem;
}

.sider-content {
  position: relative;
}

.menu-wrapper {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  background: linear-gradient(180deg, #f6f6f6 0%, #f7eeff 100%);
}

.bottom-menu {
  margin-top: auto;
}

.sider-header {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 4.5rem;
  overflow: hidden;
  position: relative;
}

.logo {
  width: 2.5rem;
  height: 2.5rem;
  flex-shrink: 0;
  transition: all 0.3s ease;
  position: absolute;
}

.title {
  font-size: 1.25rem;
  font-weight: bold;
  margin: 0;
  white-space: nowrap;
  padding-left: 3rem;
}

.fade-enter-active, .fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from, .fade-leave-to {
  opacity: 0;
}

.zoom-fade-enter-active, .zoom-fade-leave-active {
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.zoom-fade-enter-from {
  opacity: 0;
  transform: scale(0.95);
}

.zoom-fade-leave-to {
  opacity: 0;
  transform: scale(1.02);
}
</style>
