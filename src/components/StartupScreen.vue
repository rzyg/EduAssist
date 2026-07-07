<script lang="ts" setup>
import logoSrc from '../assets/logo.png'

defineProps<{
  status: string
  error?: boolean
}>()

const emit = defineEmits<{
  retry: []
}>()
</script>

<template>
  <div class="startup-overlay">
    <div class="startup-card">
      <div class="logo-wrapper">
        <img :src="logoSrc" alt="logo" class="startup-logo">
      </div>
      <h1 class="app-name">下班工具箱</h1>
      <p v-if="!error" class="startup-status">{{ status }}</p>
      <template v-else>
        <p class="startup-status error-text">{{ status }}</p>
        <button class="retry-btn" @click="emit('retry')">重试</button>
      </template>
    </div>
  </div>
</template>

<style scoped>
.startup-overlay {
  position: fixed;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(180deg, #f6f6f6 0%, #f7eeff 100%);
  z-index: 99999;
}

.startup-card {
  text-align: center;
}

.logo-wrapper {
  animation: pulse 1.5s ease-in-out infinite;
}

.startup-logo {
  width: 80px;
  height: 80px;
  border-radius: 20px;
  box-shadow: 0 8px 32px rgba(102, 126, 234, 0.25);
}

.app-name {
  margin-top: 20px;
  font-size: 24px;
  font-weight: 700;
  color: #333;
  letter-spacing: 2px;
}

.startup-status {
  margin-top: 32px;
  font-size: 14px;
  color: #999;
  letter-spacing: 1px;
}

.error-text {
  color: #e74c3c;
}

.retry-btn {
  margin-top: 20px;
  padding: 8px 28px;
  border: 1px solid #3288ed;
  border-radius: 6px;
  background: #fff;
  color: #3288ed;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
}

.retry-btn:hover {
  background: #3288ed;
  color: #fff;
}

@keyframes pulse {
  0%, 100% {
    transform: scale(1);
    opacity: 1;
  }
  50% {
    transform: scale(1.06);
    opacity: 0.85;
  }
}
</style>
