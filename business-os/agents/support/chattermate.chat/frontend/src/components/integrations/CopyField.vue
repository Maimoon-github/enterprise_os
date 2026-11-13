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

<!-- A read-only value the customer copies into another product's settings
     (a webhook URL, a verify token). -->
<script setup lang="ts">
import { toast } from 'vue-sonner'

const props = defineProps<{
  fieldId: string
  label: string
  /** What the toast calls it ("Webhook URL copied") */
  name: string
  value: string
}>()

const copy = async () => {
  try {
    await navigator.clipboard.writeText(props.value)
    toast.success(`${props.name} copied`)
  } catch {
    // No clipboard on plain-http origins: the field stays selectable
    toast.error('Could not copy. Select the text and copy it instead.')
  }
}
</script>

<template>
  <div class="copy-field">
    <label class="copy-label" :for="fieldId">{{ label }}</label>
    <div class="copy-row">
      <input :id="fieldId" class="copy-input" :value="value" readonly />
      <button class="copy-btn" type="button" @click="copy">Copy</button>
    </div>
  </div>
</template>

<style scoped>
.copy-field + .copy-field {
  margin-top: 10px;
}

.copy-label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 6px;
}

.copy-row {
  display: flex;
  gap: 8px;
}

.copy-input {
  flex: 1;
  min-width: 0;
  padding: 8px 10px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-btn);
  background: var(--background-soft);
  color: inherit;
  font-size: 13px;
}

.copy-btn {
  padding: 8px 12px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-btn);
  background: var(--background-soft);
  color: inherit;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.copy-btn:hover {
  border-color: var(--muted);
}

.copy-btn:focus-visible,
.copy-input:focus-visible {
  outline: 2px solid var(--accent-ink);
  outline-offset: 1px;
}
</style>
