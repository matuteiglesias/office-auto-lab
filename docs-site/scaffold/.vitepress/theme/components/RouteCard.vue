<script setup lang="ts">defineProps<{ title: string, href: string, signal?: string }>()</script>
<template><a class="route-card" :href="href"><span class="route-signal">{{ signal || 'ROUTE' }}</span><strong>{{ title }}</strong><span class="route-copy"><slot /></span><span aria-hidden="true" class="route-arrow">→</span></a></template>
