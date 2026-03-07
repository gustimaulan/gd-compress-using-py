<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-icon">📦</div>
      <h1 class="login-title">GD Compressor</h1>
      <p class="login-subtitle">Sign in with your Google account to compress and manage your Drive images</p>

      <div v-if="error" class="login-error">{{ error }}</div>

      <button class="btn btn-google" @click="doLogin" :disabled="loading">
        <svg viewBox="0 0 24 24" width="18" height="18" style="margin-right:8px;">
          <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"/>
          <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
          <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
          <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
        </svg>
        {{ loading ? 'Redirecting…' : 'Sign in with Google' }}
      </button>

      <p class="login-footer">One click grants sign-in and Google Drive access</p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';

const error = ref('');
const loading = ref(false);

async function doLogin() {
  loading.value = true;
  error.value = '';
  try {
    const res = await fetch('/api/auth/login');
    const data = await res.json();
    if (!res.ok) {
      error.value = data.error || 'Login failed';
      loading.value = false;
      return;
    }
    // Redirect to Google's consent page
    window.location.href = data.url;
  } catch (e) {
    error.value = 'Could not connect to server';
    loading.value = false;
  }
}
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
.login-icon { font-size: 3rem; margin-bottom: 0.5rem; }
.login-title { font-size: 1.4rem; font-weight: 700; margin-bottom: 0.4rem; }
.login-subtitle {
  font-size: 0.85rem; color: var(--text-muted);
  margin-bottom: 1.5rem; line-height: 1.5;
}
.login-error {
  background: #ef444422; color: var(--red);
  padding: 0.5rem 0.75rem; border-radius: var(--radius-sm);
  font-size: 0.82rem; margin-bottom: 1rem;
}
.login-footer {
  font-size: 0.72rem; color: var(--text-muted); margin-top: 1.5rem;
}
.btn-google {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.65rem 1.5rem;
  background: #fff;
  color: #3c4043;
  border: 1px solid #dadce0;
  border-radius: var(--radius-sm);
  font-size: 0.9rem;
  font-weight: 500;
  font-family: inherit;
  cursor: pointer;
  transition: background 0.15s, box-shadow 0.15s;
}
.btn-google:hover {
  background: #f7f8f8;
  box-shadow: 0 1px 3px rgba(0,0,0,0.15);
}
.btn-google:disabled { opacity: 0.6; cursor: not-allowed; }
</style>
