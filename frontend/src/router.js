import { createRouter, createWebHistory } from 'vue-router';
import Dashboard from './views/Dashboard.vue';
import DuplicateRemover from './views/DuplicateRemover.vue';

const routes = [
  { path: '/', name: 'Dashboard', component: Dashboard },
  { path: '/duplicates', name: 'Duplicates', component: DuplicateRemover },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;
