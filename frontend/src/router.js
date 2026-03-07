import { createRouter, createWebHistory } from 'vue-router';
import Dashboard from './views/Dashboard.vue';
import DuplicateRemover from './views/DuplicateRemover.vue';
import Login from './views/Login.vue';

const routes = [
  { path: '/login', name: 'Login', component: Login, meta: { public: true } },
  { path: '/', name: 'Dashboard', component: Dashboard },
  { path: '/duplicates', name: 'Duplicates', component: DuplicateRemover },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

// Auth guard
router.beforeEach(async (to, from, next) => {
  if (to.meta.public) return next();

  // Check for token in URL first (OAuth callback redirect)
  const params = new URLSearchParams(window.location.search);
  const urlToken = params.get('token');
  if (urlToken) {
    sessionStorage.setItem('auth_token', urlToken);
  }

  const token = sessionStorage.getItem('auth_token');
  if (!token) return next('/login');

  try {
    const res = await fetch('/api/auth/me', {
      headers: { 'Authorization': `Bearer ${token}` },
    });
    const data = await res.json();
    if (data.authenticated) return next();
  } catch (e) {
    // network error
  }
  sessionStorage.removeItem('auth_token');
  next('/login');
});

export default router;
