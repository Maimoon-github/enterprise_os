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

// The channel's delivery receipt for a message we sent. 'failed' has its own
// "Not delivered" notice, so it shows no tick.
type ChannelStatus = 'sent' | 'delivered' | 'read'

const TICKS: Record<ChannelStatus, { icon: string; label: string }> = {
  sent: { icon: 'fa-solid fa-check', label: 'Sent' },
  delivered: { icon: 'fa-solid fa-check-double', label: 'Delivered' },
  read: { icon: 'fa-solid fa-check-double', label: 'Read' },
}

const props = defineProps<{
  status?: string | null
  // On an accent-filled bubble no blue holds contrast in either theme, so
  // read becomes an inverted badge in the bubble's own colour pair
  onAccent?: boolean
}>()

const tick = computed(() =>
  props.status && props.status in TICKS ? TICKS[props.status as ChannelStatus] : null
)
</script>

<template>
  <span
    v-if="tick"
    class="status-ticks"
    :class="[`status-ticks--${status}`, { 'status-ticks--on-accent': onAccent }]"
    :title="tick.label"
    :aria-label="tick.label"
    role="img"
  >
    <font-awesome-icon :icon="tick.icon" />
  </span>
</template>

<style scoped>
.status-ticks {
  display: inline-flex;
  margin-left: 4px;
  font-size: var(--text-xs);
  vertical-align: baseline;
}

.status-ticks--read {
  color: var(--c-info);
}

.status-ticks--on-accent.status-ticks--read {
  padding: 0 4px;
  border-radius: var(--radius-full);
  background: var(--bubble-agent-fg);
  color: var(--bubble-agent-bg);
}
</style>
