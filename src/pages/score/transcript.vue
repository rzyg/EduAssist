<script setup lang="ts">
import {ref, onMounted} from 'vue'
import ScoreForm from '../../components/ScoreForm.vue'
import {api} from '../../config'

const endpoint = ref('')

onMounted(async () => {
  endpoint.value = await api('/api/v1/score/transcript')
})
</script>

<template>
  <ScoreForm
      card-title="成绩单制作"
      :api-endpoint="endpoint"
      success-message="成绩单生成成功！"
      button-label="生成成绩单"
  />
</template>
