<script setup lang="ts">
import ScoreForm from '../../components/ScoreForm.vue'
</script>

<template>
  <ScoreForm
      card-title="成绩单制作"
      api-endpoint="http://localhost:8000/api/v1/score/transcript"
      success-message="成绩单生成成功！"
      button-label="生成成绩单"
  />
</template>
