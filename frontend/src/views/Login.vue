<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-icon">📦</div>
      <h1 class="login-title">GD Compressor</h1>
      <p class="login-subtitle">Sign in with your Google account to access the dashboard</p>

      <div v-if="error" class="login-error">{{ error }}</div>

      <div id="g_id_onload"
        :data-client_id="clientId"
        data-context="signin"
        data-ux_mode="popup"
        data-callback="handleGoogleCredentialResponse"
        data-auto_prompt="false"
      ></div>

      <div class="g_id_signin"
        data-type="standard"
        data-shape="rectangular"
        data-theme="filled_black"
        data-text="signin_with"
        data-size="large"
        data-logo_alignment="left"
        data-width="300"
      ></div>

      <p class="login-footer">Secure authentication via Google</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';

const router = useRouter();
const error = ref('');
const clientId = ref('');

// Fetch the client ID from the backend config
onMounted(async () => {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    clientId.value = data.google_client_id || '';
  } catch (e) {
    error.value = 'Could not connect to server';
  }

  // Load Google Identity Services script
  const script = document.createElement('script');
  script.src = 'https://accounts.google.com/gsi/client';
  script.async = true;
  script.defer = true;
  document.head.appendChild(script);

  // Global callback for GIS
  window.handleGoogleCredentialResponse = async (response) => {
    try {
      const res = await fetch('/api/auth/google', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ credential: response.credential }),
      });
      const data = await res.json();
      if (!res.ok) {
        error.value = data.error || 'Login failed';
        return;
      }
      router.push('/');
    } catch (e) {
      error.value = 'Login failed: ' + e.message;
    }
  };
});
</script>

<style scoped>
.login-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: var(--bg);
  padding: 1rem;
}
.login-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 2.5rem 2rem;
  text-align: center;
  max-width: 380px;
  width: 100%;
}
.login-icon {
  font-size: 3rem;
  margin-bottom: 0.5rem;
}
.login-title {
  font-size: 1.4rem;
  font-weight: 700;
  margin-bottom: 0.4rem;
}
.login-subtitle {
  font-size: 0.85rem;
  color: var(--text-muted);
  margin-bottom: 1.5rem;
  line-height: 1.5;
}
.login-error {
  background: #ef444422;
  color: var(--red);
  padding: 0.5rem 0.75rem;
  border-radius: var(--radius-sm);
  font-size: 0.82rem;
  margin-bottom: 1rem;
}
.login-footer {
  font-size: 0.72rem;
  color: var(--text-muted);
  margin-top: 1.5rem;
}
.g_id_signin {
  display: flex;
  justify-content: center;
}
</style>
