<script setup lang="ts">defineProps<{ kind?: string }>()</script>
<template><span class="status-badge" :data-kind="kind"><slot /></span></template>
