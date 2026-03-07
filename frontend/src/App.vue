<template>
  <template v-if="showNav">
    <nav class="nav">
      <router-link to="/" class="nav-brand">📦 GD Compressor</router-link>
      <div class="nav-links">
        <router-link to="/" class="nav-link">Dashboard</router-link>
        <router-link to="/duplicates" class="nav-link">Duplicates</router-link>
      </div>
      <div class="nav-user" v-if="user">
        <img v-if="user.picture" :src="user.picture" class="avatar" referrerpolicy="no-referrer" />
        <span class="user-name">{{ user.name }}</span>
        <button class="btn btn-ghost btn-sm" @click="doLogout">Logout</button>
      </div>
    </nav>
  </template>

  <main :class="{ 'main-content': showNav }">
    <router-view v-slot="{ Component }">
      <keep-alive>
        <component
          :is="Component"
          :authenticated="driveConnected"
          :config="config"
          @refresh-status="loadStatus"
        />
      </keep-alive>
    </router-view>
  </main>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { getStatus } from './api/client';

const route = useRoute();
const router = useRouter();

const driveConnected = ref(false);
const config = ref({});
const user = ref(null);

const showNav = computed(() => route.name !== 'Login');

async function loadStatus() {
  try {
    const meRes = await fetch('/api/auth/me');
    const meData = await meRes.json();
    if (meData.authenticated) {
      user.value = { email: meData.email, name: meData.name, picture: meData.picture };
      driveConnected.value = meData.drive_connected;
    }

    const data = await getStatus();
    config.value = data.config;
  } catch (e) {
    console.error('Status load failed', e);
  }
}

async function doLogout() {
  await fetch('/api/auth/logout', { method: 'POST' });
  user.value = null;
  router.push('/login');
}

watch(() => route.path, () => {
  if (route.name !== 'Login') loadStatus();
}, { immediate: true });
</script>

<style scoped>
.nav-user { display: flex; align-items: center; gap: 0.5rem; margin-left: 0.5rem; }
.avatar { width: 28px; height: 28px; border-radius: 999px; }
.user-name { font-size: 0.82rem; color: var(--text-muted); }
@media (max-width: 640px) { .user-name { display: none; } }
</style>
