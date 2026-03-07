<template>
  <div>
    <div class="card">
      <div class="card-title"><span class="icon">🔍</span> Duplicate File Finder</div>

      <div v-if="!authenticated" class="text-muted" style="font-size:0.85rem;">
        Connect your Google account on the Dashboard first.
      </div>

      <template v-else>
        <div class="auth-row" style="margin-bottom:0.75rem;">
          <div class="field" style="flex:1;">
            <label>Scan Folder</label>
            <div class="select-wrap">
              <select v-model="folderId" :disabled="loading">
                <option value="">— select a folder —</option>
                <option v-for="f in folders" :key="f.id" :value="f.id">{{ f.name }}</option>
              </select>
              <button class="btn btn-ghost btn-sm" @click="loadFolders" :disabled="loading">↻</button>
            </div>
          </div>
          <button
            class="btn btn-primary"
            @click="scan"
            :disabled="!folderId || loading"
            style="align-self:flex-end;"
          >
            {{ loading ? 'Scanning…' : '🔍 Scan for Duplicates' }}
          </button>
        </div>

        <!-- Results summary -->
        <div v-if="result" style="margin-bottom:0.75rem; font-size:0.85rem;">
          <span class="badge badge-muted">{{ result.total_files }} files scanned</span>
          <span class="badge" :class="result.duplicate_groups ? 'badge-yellow' : 'badge-green'" style="margin-left:0.4rem;">
            {{ result.duplicate_groups }} duplicate group{{ result.duplicate_groups !== 1 ? 's' : '' }}
          </span>
        </div>

        <!-- Duplicate Groups -->
        <div v-if="result && result.groups.length">
          <div style="display:flex;align-items:center;gap:0.5rem;margin-bottom:0.75rem;">
            <button class="btn btn-danger btn-sm" @click="deleteSelected" :disabled="selectedIds.length === 0 || deleting">
              🗑️ Delete Selected ({{ selectedIds.length }})
            </button>
            <button class="btn btn-ghost btn-sm" @click="autoSelect">⚡ Auto-select duplicates</button>
          </div>

          <div v-for="group in result.groups" :key="group.hash" class="dup-group">
            <div class="dup-group-header">
              <span>🔗 {{ group.count }} copies</span>
              <span class="dup-file-meta">{{ group.files[0].name }}</span>
            </div>
            <div v-for="file in group.files" :key="file.id" class="dup-file">
              <input
                type="checkbox"
                :value="file.id"
                v-model="selectedIds"
              />
              <span class="dup-file-name">{{ file.name }}</span>
              <span class="dup-file-meta">
                {{ formatSize(file.size) }}
                · {{ formatDate(file.modifiedTime) }}
              </span>
            </div>
          </div>
        </div>

        <div v-else-if="result && result.groups.length === 0" style="font-size:0.85rem;color:var(--green);">
          ✅ No duplicates found! Your folder is clean.
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue';
import { getFolders, getDuplicates, cleanupDuplicates } from '../api/client';

const props = defineProps({
  authenticated: Boolean,
  oauthReady: Boolean,
  credsUploaded: Boolean,
  config: Object,
});

const folders = ref([]);
const folderId = ref('');
const loading = ref(false);
const deleting = ref(false);
const result = ref(null);
const selectedIds = ref([]);

watch(() => props.authenticated, (v) => {
  if (v) loadFolders();
}, { immediate: true });

async function loadFolders() {
  try {
    folders.value = await getFolders();
  } catch (e) { /* ignored */ }
}

async function scan() {
  loading.value = true;
  selectedIds.value = [];
  result.value = null;
  try {
    result.value = await getDuplicates(folderId.value);
  } catch (e) {
    alert(e.message);
  } finally {
    loading.value = false;
  }
}

function autoSelect() {
  // For each group, select all but the first (keep oldest / first listed)
  selectedIds.value = [];
  for (const group of result.value.groups) {
    for (let i = 1; i < group.files.length; i++) {
      selectedIds.value.push(group.files[i].id);
    }
  }
}

async function deleteSelected() {
  if (!confirm(`Delete ${selectedIds.value.length} file(s)? This cannot be undone.`)) return;
  deleting.value = true;
  try {
    const res = await cleanupDuplicates(selectedIds.value);
    alert(`Deleted ${res.deleted} file(s).${res.errors.length ? ` ${res.errors.length} error(s).` : ''}`);
    // Re-scan
    selectedIds.value = [];
    await scan();
  } catch (e) {
    alert(e.message);
  } finally {
    deleting.value = false;
  }
}

function formatSize(bytes) {
  const kb = parseInt(bytes || 0) / 1024;
  return kb >= 1024 ? `${(kb / 1024).toFixed(1)} MB` : `${kb.toFixed(0)} KB`;
}

function formatDate(iso) {
  if (!iso) return '';
  return new Date(iso).toLocaleDateString();
}
</script>

<style scoped>
.text-muted { color: var(--text-muted); }
</style>
