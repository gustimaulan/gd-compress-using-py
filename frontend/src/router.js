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

  try {
    const res = await fetch('/api/auth/me');
    const data = await res.json();
    if (data.authenticated) return next();
  } catch (e) {
    // network error
  }
  next('/login');
});

export default router;
