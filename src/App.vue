<template>
  <!-- 启动加载屏 -->
  <StartupScreen v-if="initializing" :status="initStatus" />

  <!-- 主界面 -->
  <template v-else>
    <n-config-provider :theme-overrides="themeOverrides">
      <n-message-provider>
        <DragArea/>
        <n-layout has-sider class="sider">
          <n-layout-sider
              bordered
              collapse-mode="width"
              :collapsed-width="64"
              :width="220"
              :collapsed="collapsed"
              show-trigger
              @collapse="collapsed = true"
              @expand="collapsed = false"
              class="sider-content"
          >
            <div class="menu-wrapper">
              <div class="sider-header">
                <img class="logo" src="/src/assets/logo.png" alt="logo" :style="{ left: collapsed ? '20%' : '17%' }">
                <transition name="fade">
                  <p v-show="!collapsed" class="title">下班工具箱</p>
                </transition>
              </div>
              <n-menu
                  v-model:value="activeKey"
                  :collapsed="collapsed"
                  :collapsed-width="64"
                  :collapsed-icon-size="22"
                  :options="topMenuOptions"
                  key-field="childrenKey"
                  label-field="childrenLabel"
                  children-field="childrenChildren"
              />
              <n-menu
                  v-model:value="activeKey"
                  :collapsed="collapsed"
                  :collapsed-width="64"
                  :collapsed-icon-size="22"
                  :options="bottomMenuOptions"
                  key-field="childrenKey"
                  label-field="childrenLabel"
                  children-field="childrenChildren"
                  class="bottom-menu"
              />
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
</template>

<script setup lang="ts">
import type {MenuOption} from 'naive-ui'
import type {Component} from 'vue'
import type {GlobalThemeOverrides} from 'naive-ui'
import {NMessageProvider} from 'naive-ui'
import DragArea from './components/DragArea.vue'

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

import {
  Home as HomeIcon,
  Award as AwardIcon,
  Books as BooksIcon,
  Book2 as PdfIcon,
  Businessplan as AllowanceIcon,
  InfoCircle as AboutIcon,
  Settings as SettingIcon
} from '@vicons/tabler'
import {NIcon, createDiscreteApi} from 'naive-ui'
import {h, ref, watch, onMounted, onUnmounted} from 'vue'
import {useRouter, useRoute} from 'vue-router'
import {API_BASE} from './config'
import StartupScreen from './components/StartupScreen.vue'

const {message} = createDiscreteApi(['message'])

function renderIcon(icon: Component) {
  return () => h(NIcon, null, {default: () => h(icon)})
}

const router = useRouter()
const route = useRoute()
const activeKey = ref<string | null>(route.name as string || 'home')

watch(activeKey, (newKey) => {
  if (newKey) {
    router.push({name: newKey})
  }
})

watch(() => route.name, (newName) => {
  activeKey.value = newName as string
})

const topMenuOptions: MenuOption[] = [
  {
    childrenLabel: '主页',
    childrenKey: 'home',
    icon: renderIcon(HomeIcon)
  },
  {
    childrenLabel: '成绩',
    childrenKey: 'score',
    icon: renderIcon(AwardIcon),
    childrenChildren: [
      {
        childrenLabel: '成绩单',
        childrenKey: 'transcript'
      }, {
        childrenLabel: '分析',
        childrenKey: 'analysis'
      }
    ]
  },
  {
    childrenLabel: '刷课',
    childrenKey: 'fuck-the-online-class',
    icon: renderIcon(BooksIcon)
  },
  {
    childrenLabel: 'PDF编辑',
    childrenKey: 'edit-pdf',
    icon: renderIcon(PdfIcon),
  },
  {
    childrenLabel: '津贴',
    childrenKey: 'allowance',
    icon: renderIcon(AllowanceIcon)
  }
]

const bottomMenuOptions: MenuOption[] = [
  {
    childrenLabel: '关于',
    childrenKey: 'about',
    icon: renderIcon(AboutIcon)
  },
  {
    childrenLabel: '设置',
    childrenKey: 'setting',
    icon: renderIcon(SettingIcon)
  }
]

const collapsed = ref(false)

// ── 启动流程 ─────────────────────────────────────────────────────────────
const initializing = ref(true)
const initStatus = ref('')

const BACKEND_URL = API_BASE

async function checkAlive(): Promise<boolean> {
  try {
    const res = await fetch(`${BACKEND_URL}/health`, {
      signal: AbortSignal.timeout(1500)
    })
    const data = await res.json()
    return res.ok && data.status === 'ok'
  } catch {
    return false
  }
}

async function initApp() {
  // 1. 先快速尝试几次健康检测（可能后端刚启动还没完全就绪）
  initStatus.value = '正在连接后端…'
  for (let i = 0; i < 3; i++) {
    if (await checkAlive()) {
      initializing.value = false
      return
    }
    await new Promise(r => setTimeout(r, 500))
  }

  // 2. 不在线 → 尝试通过 Tauri 拉起
  initStatus.value = '正在启动后端…'
  try {
    const {invoke} = await import('@tauri-apps/api/core')
    await invoke('start_backend')
  } catch {
    // 非 Tauri 环境，交给用户手动启动
    initializing.value = false
    message.warning('后端未启动，请手动运行 python core/main.py')
    return
  }

  // 3. 等待后端就绪（最多 30 秒）
  initStatus.value = '等待后端就绪…'
  for (let i = 0; i < 30; i++) {
    await new Promise(r => setTimeout(r, 1000))
    if (await checkAlive()) {
      initStatus.value = '就绪！'
      await new Promise(r => setTimeout(r, 300))
      initializing.value = false
      return
    }
  }

  // 4. 超时
  initializing.value = false
  message.warning('后端启动超时，请手动检查')
}

// ── 运行时健康检测（持续监控） ────────────────────────────────────────────
let healthCheckTimer: ReturnType<typeof setInterval> | null = null
let healthMsg: any = null

async function checkHealth() {
  if (await checkAlive()) {
    healthMsg?.destroy()
    healthMsg = null
  } else if (!healthMsg) {
    healthMsg = message.warning('后端服务已断开，部分功能不可用', {duration: 0})
  }
}

onMounted(async () => {
  await initApp()
  // 初始化完成后再启动运行时健康检测
  healthCheckTimer = setInterval(checkHealth, 5000)
})

onUnmounted(() => {
  if (healthCheckTimer) clearInterval(healthCheckTimer)
  healthMsg?.destroy()
})
</script>
<style scoped>
.sider {
  height: 100vh;
  user-select: none;
}

.main-content {
  height: 100vh;
  padding-top: 1rem
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

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.zoom-fade-enter-active,
.zoom-fade-leave-active {
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
