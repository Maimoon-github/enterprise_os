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
import { computed, onMounted, ref, watch } from 'vue'
import { knowledgeService } from '@/services/knowledge'

const props = defineProps<{
  agentId: string
  organizationId: string
}>()

const emit = defineEmits<{
  (e: 'added'): void
  (e: 'cancel'): void
  // While the text is being saved the step around it must hold still.
  (e: 'busy', saving: boolean): void
}>()

// Titles must be unique per org, and someone may paste more than once (or
// already have an "About us"): stamp it so a second paste isn't refused.
const titleNow = () =>
  `About us (${new Date().toLocaleString(undefined, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })})`
const MIN_LENGTH = 40 // enough to answer something from; less is a typo

const textArea = ref<HTMLTextAreaElement | null>(null)
const content = ref('')
const saving = ref(false)
const error = ref<string | null>(null)
const hasText = computed(() => content.value.trim().length > 0)

watch(saving, (value) => emit('busy', value))
// An error is about what was there when they pressed the button.
watch(content, () => {
  error.value = null
})
onMounted(() => textArea.value?.focus())

const add = async () => {
  if (saving.value || !hasText.value) return
  const text = content.value.trim()
  // Say why rather than leave the button dead with no reason given.
  if (text.length < MIN_LENGTH) {
    error.value = 'Add a few sentences so it has something to answer from.'
    return
  }
  saving.value = true
  try {
    await knowledgeService.addText(props.organizationId, titleNow(), text, props.agentId)
    content.value = ''
    emit('added')
  } catch (err: any) {
    error.value = err?.message || 'Could not add that text'
  } finally {
    saving.value = false
  }
}

const cancel = () => {
  if (!saving.value) emit('cancel')
}
</script>

<template>
  <!-- Esc anywhere in the box (textarea or its buttons) backs out of it -->
  <div class="text-fallback" @keydown.esc.prevent="cancel">
    <textarea
      ref="textArea"
      v-model="content"
      class="text-area"
      rows="6"
      aria-label="Text about your business"
      placeholder="Paste what customers ask about: what you sell, prices, delivery, opening hours…"
      :disabled="saving"
    ></textarea>
    <p v-if="error" class="step-error" role="alert">{{ error }}</p>
    <div class="fallback-actions">
      <button type="button" class="btn-soft" :disabled="!hasText || saving" @click="add">
        {{ saving ? 'Adding…' : 'Add this text' }}
      </button>
      <button type="button" class="btn-text" :disabled="saving" @click="cancel">Cancel</button>
    </div>
  </div>
</template>

<style scoped src="./step-controls.css"></style>
<style scoped>
.text-fallback {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.text-area {
  width: 100%;
  box-sizing: border-box;
  padding: 14px 16px;
  background: var(--bg);
  border: 1px solid var(--o12);
  border-radius: var(--radius-input);
  color: var(--text);
  font-size: 14px;
  font-family: var(--font-sans);
  line-height: 1.5;
  resize: vertical;
  outline: none;
  transition: var(--transition-fast);
}

.text-area:focus {
  border-color: var(--accent-ink);
  box-shadow: var(--ring-focus);
}

.fallback-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
