<script setup lang="ts">
import { VPLink } from 'vitepress/theme'

defineProps<{ title: string, href: string, signal?: string }>()
</script>
<template><VPLink class="route-card" :href="href"><span class="route-signal">{{ signal || 'ROUTE' }}</span><strong>{{ title }}</strong><span class="route-copy"><slot /></span><span aria-hidden="true" class="route-arrow">→</span></VPLink></template>
