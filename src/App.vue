<template>
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
          <img class="logo" src="/src/assets/logo.png" alt="logo">
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
    <n-layout/>
  </n-layout>
</template>

<script setup lang="ts">
import type {MenuOption} from 'naive-ui'
import type {Component} from 'vue'
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
import {h, ref} from 'vue'

function renderIcon(icon: Component) {
  return () => h(NIcon, null, {default: () => h(icon)})
}

const activeKey = ref<string | null>(null)

const topMenuOptions: MenuOption[] = [
  {
    childrenLabel: '主页',
    childrenKey: 'home-page',
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
  left: 17%;
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
</style>
