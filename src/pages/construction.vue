<script setup lang="ts">
import construction from '../assets/construction.png'
</script>

<template>
  <div class="page-container">
    <img :src="construction" alt="under construction" class="icon"/>
    <h1 class="title">页面施工中...</h1>
  </div>
</template>

<style scoped>
.page-container {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  height: 100%;
  background: #f8f9fa;
  user-select: none;
}

.icon {
  height: 15rem;
  margin-bottom: 24px;
  opacity: 0.8;
}

.title {
  font-size: 1.5rem;
  font-weight: 500;
  color: #6c757d;
  margin: 0;
  letter-spacing: 2px;
}
</style>