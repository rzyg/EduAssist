<template>
  <n-config-provider :theme-overrides="themeOverrides">
    <n-message-provider>
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

<script setup lang="ts">
import type {MenuOption} from 'naive-ui'
import type {Component} from 'vue'
import type {GlobalThemeOverrides} from 'naive-ui'
import {NMessageProvider} from 'naive-ui'

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
import {NIcon} from 'naive-ui'
import {h, ref, watch} from 'vue'
import {useRouter, useRoute} from 'vue-router'

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
</script>
<style scoped>
.sider {
  height: 100vh;
  user-select: none;
}

.main-content {
  height: 100vh;
  overflow: auto;
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
