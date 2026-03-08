<template>
  <template v-if="showNav">
    <!-- Desktop Navigation -->
    <nav class="nav" v-if="!isMobile">
      <router-link to="/" class="nav-brand">📦 GD Compressor <span class="version-tag">v1.0.3</span></router-link>
      <div class="nav-links">
        <router-link to="/" class="nav-link">Compress</router-link>
        <router-link to="/duplicates" class="nav-link">Find Duplicates</router-link>
      </div>
      <div class="nav-user" v-if="user">
        <img v-if="user.picture" :src="user.picture" class="avatar" referrerpolicy="no-referrer" />
        <span class="user-name">{{ user.name }}</span>
        <button class="btn btn-ghost btn-sm" @click="doLogout">Logout</button>
      </div>
    </nav>

    <!-- Mobile Header & Sidebar (Extracted Component) -->
    <MobileNav v-else :user="user" @logout="doLogout" />
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

  <!-- Global Toasts -->
  <div class="toast-container">
    <div 
      v-for="toast in toasts" 
      :key="toast.id" 
      class="toast" 
      :class="'toast-' + toast.type"
    >
      {{ toast.message }}
      <button class="toast-close" @click="removeToast(toast.id)">&times;</button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { getStatus, logout as apiLogout } from './api/client';
import { useToast } from './composables/useToast';
import { useMobile } from './composables/useMobile';
import MobileNav from './components/MobileNav.vue';

const { toasts, removeToast } = useToast();

const route = useRoute();
const router = useRouter();

const driveConnected = ref(false);
const config = ref({});
const user = ref(null);

const { isMobile } = useMobile();
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

/* Toasts */
.toast-container {
  position: fixed;
  bottom: 1.5rem;
  right: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  z-index: 9999;
}
.toast {
  background: var(--bg-card);
  color: var(--text);
  border: 1px solid var(--border);
  padding: 0.8rem 1.2rem;
  border-radius: var(--radius-sm);
  box-shadow: 0 4px 12px rgba(0,0,0,0.3);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  font-size: 0.85rem;
  font-weight: 500;
  animation: slideIn 0.3s ease-out forwards;
}
.toast-success {
  border-left: 4px solid var(--green);
}
.toast-error {
  border-left: 4px solid var(--red);
}
.toast-info {
  border-left: 4px solid var(--accent);
}
.toast-close {
  background: transparent;
  border: none;
  color: var(--text-muted);
  font-size: 1.2rem;
  cursor: pointer;
  line-height: 1;
}
.toast-close:hover { color: var(--text); }

.version-tag { font-size: 0.65rem; background: var(--bg); color: var(--text-muted); padding: 0.1rem 0.4rem; border-radius: 999px; margin-left: 0.25rem; font-weight: normal; border: 1px solid var(--border); }
@keyframes slideIn {
  from { transform: translateX(100%); opacity: 0; }
  to { transform: translateX(0); opacity: 1; }
}
</style>
