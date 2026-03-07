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
import { getStatus, logout as apiLogout } from './api/client';

const route = useRoute();
const router = useRouter();

const driveConnected = ref(false);
const config = ref({});
const user = ref(null);

const showNav = computed(() => route.name !== 'Login');

// Capture auth token from URL on initial load (after OAuth callback redirect)
function captureToken() {
  const params = new URLSearchParams(window.location.search);
  const token = params.get('token');
  if (token) {
    sessionStorage.setItem('auth_token', token);
    localStorage.setItem('auth_token', token);
    // Clean the URL so the token isn't visible / bookmarkable
    const clean = window.location.pathname;
    window.history.replaceState({}, '', clean);
  } else {
    const localToken = localStorage.getItem('auth_token');
    if (localToken && !sessionStorage.getItem('auth_token')) {
      sessionStorage.setItem('auth_token', localToken);
    }
  }
}

async function loadStatus() {
  try {
    const token = sessionStorage.getItem('auth_token');
    if (!token) return;

    const meRes = await fetch('/api/auth/me', {
      headers: { 'Authorization': `Bearer ${token}` },
    });
    const meData = await meRes.json();
    if (meData.authenticated) {
      user.value = { email: meData.email, name: meData.name, picture: meData.picture };
      driveConnected.value = meData.drive_connected;
    } else {
      // Token is invalid or expired
      user.value = null;
      driveConnected.value = false;
    }

    const data = await getStatus();
    config.value = data.config;
  } catch (e) {
    console.error('Status load failed', e);
  }
}

async function doLogout() {
  await apiLogout();
  user.value = null;
  driveConnected.value = false;
  router.push('/login');
}

// On mount: capture token first, then load status
captureToken();

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
