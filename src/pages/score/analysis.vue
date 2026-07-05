<script setup lang="ts">
import ScoreForm from '../../components/ScoreForm.vue'
</script>

<template>
  <ScoreForm
      card-title="成绩分析"
      api-endpoint="http://localhost:8000/api/v1/score/analysis"
      success-message="成绩分析生成成功！"
      button-label="生成成绩分析"
  />
</template>
