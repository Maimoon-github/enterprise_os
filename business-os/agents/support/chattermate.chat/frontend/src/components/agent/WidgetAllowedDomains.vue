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
import { toRef } from 'vue'
import { useWidgetAllowedDomains } from '@/composables/useWidgetAllowedDomains'

const props = defineProps<{ widgetId: string | undefined }>()

const { domains, draft, loaded, loading, saving, error, add, remove } = useWidgetAllowedDomains(toRef(props, 'widgetId'))
</script>

<template>
  <div class="allowed-domains">
    <h4 class="allowed-domains-title">Allowed domains</h4>
    <p class="allowed-domains-description">
      Leave this empty to show the widget on any site, including localhost. Add domains to show it only there.
    </p>

    <form class="allowed-domains-form" @submit.prevent="add">
      <input
        v-model="draft"
        class="allowed-domains-input"
        type="text"
        placeholder="example.com"
        aria-label="Domain to allow"
        :disabled="!loaded || saving"
      >
      <button class="allowed-domains-add" type="submit" :disabled="!loaded || saving || !draft.trim()">
        Add
      </button>
    </form>
    <p class="allowed-domains-hint">
      example.com also covers www.example.com. *.example.com covers its subdomains, not example.com itself.
    </p>

    <p v-if="error" class="allowed-domains-error" role="alert">{{ error }}</p>

    <ul v-if="domains.length" class="allowed-domains-list" aria-label="Allowed domains">
      <li v-for="domain in domains" :key="domain" class="allowed-domains-chip">
        <span class="allowed-domains-name">{{ domain }}</span>
        <button
          class="allowed-domains-remove"
          type="button"
          :aria-label="`Remove ${domain}`"
          :disabled="saving"
          @click="remove(domain)"
        >
          <font-awesome-icon icon="fa-solid fa-times" />
        </button>
      </li>
    </ul>
    <p v-else-if="loaded" class="allowed-domains-empty">Any site can show this widget.</p>
  </div>
</template>

<style scoped>
.allowed-domains {
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
}

.allowed-domains-title {
  font-family: var(--font-display);
  font-size: 16px;
  font-weight: 600;
  color: var(--text);
  margin: 0;
}

.allowed-domains-description,
.allowed-domains-hint,
.allowed-domains-empty {
  color: var(--muted);
  font-size: 14px;
  line-height: 1.6;
  margin: 0;
}

.allowed-domains-hint {
  font-size: 13px;
}

.allowed-domains-form {
  display: flex;
  gap: var(--space-sm);
}

.allowed-domains-input {
  flex: 1;
  min-width: 0;
  padding: 8px 12px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-input);
  background: var(--background-base);
  color: var(--text);
  font-family: var(--font-mono);
  font-size: 14px;
}

.allowed-domains-input:focus {
  outline: none;
  box-shadow: var(--ring-focus);
}

.allowed-domains-add {
  padding: 8px 16px;
  border: none;
  border-radius: var(--radius-btn);
  background: var(--accent-solid);
  color: var(--on-accent-solid);
  font-weight: 600;
  cursor: pointer;
}

.allowed-domains-add:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.allowed-domains-error {
  color: var(--error-color);
  font-size: 13px;
  margin: 0;
}

.allowed-domains-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-xs);
  list-style: none;
  padding: 0;
  margin: 0;
}

.allowed-domains-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 6px 4px 12px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-pill);
  background: var(--background-soft);
  color: var(--text);
  font-family: var(--font-mono);
  font-size: 13px;
}

.allowed-domains-remove {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border: none;
  border-radius: var(--radius-full);
  background: transparent;
  color: var(--muted);
  cursor: pointer;
}

.allowed-domains-remove:hover:not(:disabled) {
  background: var(--hover-bg);
  color: var(--text);
}
</style>
