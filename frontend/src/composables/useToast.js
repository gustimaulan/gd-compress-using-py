import { ref } from 'vue';

const toasts = ref([]);
let toastId = 0;

export function useToast() {
  const addToast = (message, type = 'info', duration = 3000) => {
    const id = toastId++;
    const toast = { id, message, type };
    toasts.value.push(toast);
    setTimeout(() => {
      removeToast(id);
    }, duration);
  };

  const removeToast = (id) => {
    const index = toasts.value.findIndex((t) => t.id === id);
    if (index > -1) {
      toasts.value.splice(index, 1);
    }
  };

  return { toasts, addToast, removeToast };
}
