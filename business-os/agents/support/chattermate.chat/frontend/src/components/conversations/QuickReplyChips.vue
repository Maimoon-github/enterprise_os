<!--
Copyright 2024-2026 ChatterMate

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
-->

<script setup lang="ts">
import { computed } from 'vue'

// The choices a message went out with (the backend's record of what was
// actually sent). Read-only: they were tapped on the customer's phone.
interface SentChoices {
  as_text?: boolean
  choices?: Array<{ id: string; text: string }>
}

const props = defineProps<{
  sent?: SentChoices | null
}>()

const choices = computed(() => props.sent?.choices ?? [])
const label = computed(() =>
  props.sent?.as_text ? 'Choices offered (sent as a numbered list)' : 'Choices offered'
)
</script>

<template>
  <ul v-if="choices.length" class="quick-reply-chips" :aria-label="label" :title="label">
    <li v-for="choice in choices" :key="choice.id" class="quick-reply-chip">{{ choice.text }}</li>
  </ul>
</template>

<style scoped>
.quick-reply-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 8px 0 0;
  padding: 0;
  list-style: none;
}

.quick-reply-chip {
  padding: 3px 10px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-full);
  background: var(--background-soft);
  color: var(--text-color);
  font-size: var(--text-xs);
  line-height: 1.5;
}
</style>
