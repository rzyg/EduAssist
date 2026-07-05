<template>
  <div class="homepage-container">
    <div class="content-wrapper">
      <img src="/src/assets/logo.png" alt="EduWork Assistant Logo" class="main-logo"/>

      <div class="title-section">
        <h1 class="app-title">
          𝑬𝒅𝒖𝑾𝒐𝒓𝒌 𝑨𝒔𝒔𝒊𝒔𝒕𝒂𝒏𝒕
        </h1>
        <p class="tagline">让重复的工作自动化 还宝贵的时间于休息</p>
      </div>

      <div class="button-group">
        <div class="button-item" @click="openWebsite">
          <n-button text>
            <template #icon>
              <n-icon :size="32">
                <CompassIcon/>
              </n-icon>
            </template>
          </n-button>
          <span>去官网</span>
        </div>

        <div class="button-item" @click="showCoffeeModal = true">
          <n-button text>
            <template #icon>
              <n-icon :size="32">
                <CoffeeIcon/>
              </n-icon>
            </template>
          </n-button>
          <span>请咖啡</span>
        </div>

        <div class="button-item" @click="showContactModal = true">
          <n-button text>
            <template #icon>
              <n-icon :size="32">
                <MailIcon/>
              </n-icon>
            </template>
          </n-button>
          <span>联系我</span>
        </div>
      </div>

    </div>

    <n-modal v-model:show="showCoffeeModal" preset="dialog" title="请咖啡">
      <div class="modal-content">
        <p>您的支持是我们更新和维护的最大动力</p>
        <div class="container-tip">
          <img
              alt="微信收款码"
              height="200rem"
              src="/src/assets/homepage/tips.jpg"
          />
        </div>
      </div>
      <template #action>
        <n-button @click="showCoffeeModal = false">关闭</n-button>
      </template>
    </n-modal>

    <n-modal v-model:show="showContactModal" preset="dialog" title="联系我">
      <div class="modal-content">
        <p>暂无联系方式</p>
      </div>
      <template #action>
        <n-button @click="showContactModal = false">关闭</n-button>
      </template>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import {ref} from 'vue'
import {Compass as CompassIcon, Coffee as CoffeeIcon, Mail as MailIcon} from '@vicons/tabler'
import {openUrl} from '@tauri-apps/plugin-opener'

const showCoffeeModal = ref(false)
const showContactModal = ref(false)


function openWebsite() {
  openUrl('https://ea-docs.bbts.fun')
}


</script>

<style scoped>
.homepage-container {
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
  background: white;
}

.content-wrapper {
  text-align: center;
  color: #333;
}

.main-logo {
  width: 12rem;
  height: 12rem;
  margin-bottom: 3rem;
  filter: drop-shadow(0 0 2em #448348);
}

.title-section {
  margin-bottom: 2rem;
}

.app-title {
  font-size: 2.5rem;
  font-weight: bold;
  margin-bottom: 1rem;
  color: #2c3e50;
}


.tagline {
  font-size: 1.5rem;
  color: #666;
  margin-top: 1rem;
  font-family: "SimSun", serif;
}


.modal-content {
  padding: 1rem 0;
}

.button-group {
  display: flex;
  gap: 5rem;
  justify-content: center;
}

.button-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
}
</style>
