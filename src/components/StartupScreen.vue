<script setup lang="ts">
defineProps<{
  status: string
}>()
</script>

<template>
  <div class="startup-overlay">
    <div class="startup-card">
      <div class="logo-wrapper">
        <img class="startup-logo" src="/src/assets/logo.png" alt="logo">
      </div>
      <h1 class="app-name">下班工具箱</h1>
      <p class="startup-status">{{ status }}</p>
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
