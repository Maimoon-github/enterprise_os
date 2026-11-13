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
// A small icon + label above a message saying where it came from (a tapped
// button, an external app).
defineProps<{
  icon: string
  label: string
}>()
</script>

<template>
  <span class="message-tag">
    <font-awesome-icon :icon="icon" /> {{ label }}
  </span>
</template>

<style scoped>
.message-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-bottom: 4px;
  font-size: var(--text-xs);
  color: var(--muted);
}
</style>
