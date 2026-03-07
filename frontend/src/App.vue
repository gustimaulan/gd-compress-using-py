<template>
  <nav class="nav">
    <router-link to="/" class="nav-brand">📦 GD Compressor</router-link>
    <div class="nav-links">
      <router-link to="/" class="nav-link">Dashboard</router-link>
      <router-link to="/duplicates" class="nav-link">Duplicates</router-link>
    </div>
    <span v-if="authenticated" class="badge badge-green">● Connected</span>
    <span v-else class="badge badge-red">● Offline</span>
  </nav>

  <main class="main-content">
    <router-view
      :authenticated="authenticated"
      :oauth-ready="oauthReady"
      :creds-uploaded="credsUploaded"
      :config="config"
      @refresh-status="loadStatus"
    />
  </main>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { getStatus } from './api/client';

const authenticated = ref(false);
const oauthReady = ref(false);
const credsUploaded = ref(false);
const config = ref({});

async function loadStatus() {
  try {
    const data = await getStatus();
    authenticated.value = data.authenticated;
    oauthReady.value = data.oauth_ready;
    credsUploaded.value = data.creds_uploaded;
    config.value = data.config;
  } catch (e) {
    console.error('Status load failed', e);
  }
}

onMounted(loadStatus);
</script>
