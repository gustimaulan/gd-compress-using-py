<template>
  <header class="mobile-header">
    <button class="btn btn-ghost menu-btn" @click="sidebarOpen = true">☰</button>
    <div class="nav-brand">📦 GD Compressor</div>
    <div style="width: 38px"></div> <!-- Spacer for center alignment -->
  </header>

  <!-- Sidebar Overlay -->
  <div v-if="sidebarOpen" class="sidebar-overlay" @click="sidebarOpen = false"></div>

  <!-- Slide-out Sidebar -->
  <aside class="sidebar" :class="{ 'sidebar-open': sidebarOpen }">
    <div class="sidebar-header">
      <div style="display:flex; flex-direction:column">
        <span class="nav-brand">📦 Menu</span>
        <span class="version-tag-mobile">v1.0.3</span>
      </div>
      <button class="btn btn-ghost menu-btn" @click="sidebarOpen = false">✕</button>
    </div>
    <div class="sidebar-links" @click="sidebarOpen = false">
      <router-link to="/" class="nav-link sidebar-link">Compress</router-link>
      <router-link to="/duplicates" class="nav-link sidebar-link">Find Duplicates</router-link>
    </div>
    <div class="sidebar-footer" v-if="user">
      <div class="sidebar-user">
        <img v-if="user.picture" :src="user.picture" class="avatar" referrerpolicy="no-referrer" />
        <div class="user-name" style="display:block">{{ user.name }}</div>
      </div>
      <button class="btn btn-ghost" style="width:100%; justify-content:center; margin-top:0.5rem;" @click="onLogout">Logout</button>
    </div>
  </aside>
</template>

<script setup>
import { ref } from 'vue';

const props = defineProps({
  user: {
    type: Object,
    default: null
  }
});

const emit = defineEmits(['logout']);

const sidebarOpen = ref(false);

function onLogout() {
  sidebarOpen.value = false;
  emit('logout');
}
</script>

<style scoped>
.mobile-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem 1rem;
  background: var(--bg-card);
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 0;
  z-index: 90;
}
.menu-btn {
  font-size: 1.25rem;
  padding: 0.2rem 0.6rem;
}
.sidebar-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.5);
  backdrop-filter: blur(4px);
  z-index: 100;
  animation: fadeIn 0.1s ease-out forwards;
}
.sidebar {
  position: fixed;
  top: 0; bottom: 0; left: -280px;
  width: 280px;
  background: var(--bg-card);
  border-right: 1px solid var(--border);
  z-index: 101;
  display: flex;
  flex-direction: column;
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 4px 0 15px rgba(0,0,0,0.5);
}
.sidebar-open {
  transform: translateX(280px);
}
.sidebar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.5rem;
  border-bottom: 1px solid var(--border);
}
.sidebar-links {
  display: flex;
  flex-direction: column;
  padding: 1rem;
  gap: 0.5rem;
  flex: 1;
}
.sidebar-link {
  padding: 0.75rem 1rem;
  font-size: 1rem;
  border-radius: var(--radius-sm);
}
.sidebar-footer {
  padding: 1.5rem;
  border-top: 1px solid var(--border);
  background: var(--bg);
}
.sidebar-user {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 1rem;
}
.sidebar-user .user-name { display: block; font-size: 0.9rem; }
.version-tag-mobile { font-size: 0.6rem; color: var(--text-muted); margin-top: -0.2rem; margin-left: 2rem; }
.avatar { width: 28px; height: 28px; border-radius: 999px; }

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}
</style>
