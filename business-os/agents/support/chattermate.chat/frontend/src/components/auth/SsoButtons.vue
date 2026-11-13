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

<!--
  The single sign-on provider buttons. Presentational only: the parent owns the
  redirect and passes in which provider (if any) the browser is being sent to.

  layout="stack" — full-width buttons, one per row (SSO leads the page).
  layout="row"   — side by side under the password form; the visible label is
                   shortened to the provider name, the accessible name is not.
-->
<script setup lang="ts">
import type { SsoProvider } from '@/services/sso'

withDefaults(defineProps<{
  providers: SsoProvider[]
  /** Key of the provider the browser is being redirected to, '' for none. */
  loadingKey?: string
  disabled?: boolean
  layout?: 'stack' | 'row'
}>(), {
  loadingKey: '',
  disabled: false,
  layout: 'stack',
})

const emit = defineEmits<{ select: [provider: SsoProvider] }>()
</script>

<template>
  <div
    class="sso-buttons"
    :class="[`sso-buttons--${layout}`, { 'sso-buttons--single': providers.length === 1 }]"
    role="group"
    aria-label="Single sign-on"
  >
    <button
      v-for="provider in providers"
      :key="provider.key"
      type="button"
      class="sso-btn"
      :class="{ 'is-loading': loadingKey === provider.key }"
      :data-provider="provider.key"
      :disabled="disabled"
      :aria-busy="loadingKey === provider.key || undefined"
      @click="emit('select', provider)"
    >
      <span v-if="loadingKey === provider.key" class="sso-spinner" aria-hidden="true"></span>
      <!-- Official brand marks; their colours are the only fixed colours on the page. -->
      <svg v-else-if="provider.key === 'google'" class="sso-logo" viewBox="0 0 48 48" aria-hidden="true">
        <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
        <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
        <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>
        <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
      </svg>
      <svg v-else-if="provider.key === 'microsoft'" class="sso-logo" viewBox="0 0 21 21" aria-hidden="true">
        <path fill="#F25022" d="M1 1h9v9H1z"/>
        <path fill="#7FBA00" d="M11 1h9v9h-9z"/>
        <path fill="#00A4EF" d="M1 11h9v9H1z"/>
        <path fill="#FFB900" d="M11 11h9v9h-9z"/>
      </svg>
      <font-awesome-icon v-else :icon="['fas', 'right-to-bracket']" class="sso-logo" aria-hidden="true" />

      <span v-if="loadingKey === provider.key" class="sso-label">
        <span>Redirecting</span><span class="sso-long"> to {{ provider.label }}</span><span>…</span>
      </span>
      <span v-else class="sso-label">
        <span class="sso-long">Continue with </span><span>{{ provider.label }}</span>
      </span>
    </button>
  </div>
</template>

<style scoped>
.sso-buttons {
  display: grid;
  gap: 12px;
}

.sso-buttons--row:not(.sso-buttons--single) {
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
}

.sso-btn {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  width: 100%;
  min-height: 48px; /* the height of the inputs above */
  padding: 0 var(--space-md);
  background: var(--surface);
  border: 1px solid var(--o12);
  border-radius: var(--radius-input);
  box-shadow: var(--shadow-sm);
  color: var(--text);
  font-family: var(--font-sans);
  font-size: 15px;
  font-weight: var(--font-weight-medium);
  line-height: 1.2;
  cursor: pointer;
  transition: background var(--transition-fast), border-color var(--transition-fast), box-shadow var(--transition-fast), opacity var(--transition-fast);
}

.sso-btn:hover:not(:disabled) {
  background: color-mix(in srgb, var(--surface) 92%, var(--text));
  border-color: var(--o20);
}

.sso-btn:active:not(:disabled) {
  background: color-mix(in srgb, var(--surface) 86%, var(--text));
}

.sso-btn:focus-visible {
  outline: none;
  border-color: var(--accent-ink);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent-ink) 22%, transparent);
}

.sso-btn:disabled {
  cursor: not-allowed;
  opacity: 0.5;
  box-shadow: none;
}

/* The button that was clicked stays legible while the others step back. */
.sso-btn.is-loading {
  opacity: 1;
  cursor: progress;
  border-color: var(--o20);
}

.sso-logo {
  width: 18px;
  height: 18px;
  flex: none;
}

.sso-spinner {
  width: 18px;
  height: 18px;
  flex: none;
  border-radius: 50%;
  border: 2px solid var(--o20);
  border-top-color: var(--text);
  animation: sso-spin 0.7s linear infinite;
}

.sso-label {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Side by side the provider name is enough; screen readers still hear it all. */
.sso-buttons--row:not(.sso-buttons--single) .sso-long {
  position: absolute;
  width: 1px;
  height: 1px;
  margin: -1px;
  padding: 0;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
  border: 0;
}

/* Phones: always one per row, with the full label. */
@media (max-width: 480px) {
  .sso-buttons--row:not(.sso-buttons--single) {
    grid-template-columns: 1fr;
  }
  .sso-buttons--row:not(.sso-buttons--single) .sso-long {
    position: static;
    width: auto;
    height: auto;
    margin: 0;
    overflow: visible;
    clip: auto;
  }
}

@keyframes sso-spin {
  to { transform: rotate(360deg); }
}

@media (prefers-reduced-motion: reduce) {
  .sso-spinner { animation-duration: 2s; }
}
</style>
