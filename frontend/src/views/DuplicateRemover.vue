<template>
  <div>
    <!-- Toast notification -->
    <Transition name="toast">
      <div v-if="toast.show" class="toast" :class="`toast-${toast.type}`">
        {{ toast.message }}
      </div>
    </Transition>

    <div class="card">
      <div class="card-title"><span class="icon">🔍</span> Duplicate File Finder</div>

      <div v-if="!authenticated" class="empty-state">
        <span>🔗</span>
        <p>Sign in with Google to scan for duplicates.</p>
      </div>

      <template v-else>
        <!-- Folder selector + scan button -->
        <div class="scan-row">
          <div class="field" style="flex:1; min-width:0;">
            <label>Scan Folder</label>
            <div class="select-wrap">
              <select v-model="folderId" :disabled="loading || deleting">
                <option value="">— select a folder —</option>
                <option v-for="f in folders" :key="f.id" :value="f.id">{{ f.name }}</option>
              </select>
              <button class="btn btn-ghost btn-sm" @click="loadFolders" :disabled="loading || deleting" title="Refresh folders">↻</button>
            </div>
          </div>
          <button
            class="btn btn-primary"
            @click="scan"
            :disabled="!folderId || loading || deleting"
          >
            <span v-if="loading" class="spinner"></span>
            <span v-else>🔍</span>
            {{ loading ? 'Scanning…' : 'Scan for Duplicates' }}
          </button>
        </div>

        <!-- Scanning skeleton -->
        <div v-if="loading" class="skeleton-wrap">
          <div class="skeleton-label">Scanning your Drive folder for duplicates…</div>
          <div class="skeleton-bar" style="width:85%"></div>
          <div class="skeleton-bar" style="width:60%"></div>
          <div class="skeleton-bar" style="width:75%"></div>
        </div>

        <!-- Results -->
        <template v-else-if="result">
          <!-- Summary badges -->
          <div class="result-summary">
            <span class="badge badge-muted">{{ result.total_files }} files scanned</span>
            <span class="badge" :class="result.duplicate_groups > 0 ? 'badge-yellow' : 'badge-green'" style="margin-left:0.4rem;">
              {{ result.duplicate_groups }} duplicate group{{ result.duplicate_groups !== 1 ? 's' : '' }}
            </span>
            <span v-if="selectedIds.length" class="badge badge-red" style="margin-left:0.4rem;">
              {{ selectedIds.length }} selected
            </span>
          </div>

          <!-- Action bar -->
          <div v-if="result.groups.length" class="action-bar">
            <button class="btn btn-ghost btn-sm" @click="autoSelect">
              ⚡ Auto-select duplicates
            </button>
            <button
              class="btn btn-danger btn-sm"
              @click="deleteSelected"
              :disabled="selectedIds.length === 0 || deleting"
            >
              <span v-if="deleting" class="spinner"></span>
              <span v-else>🗑️</span>
              {{ deleting ? `Deleting ${deleteProgress}/${selectedIds.length}…` : `Delete Selected (${selectedIds.length})` }}
            </button>
          </div>

          <!-- Delete progress bar -->
          <div v-if="deleting" class="progress-wrap">
            <div class="progress-bar" :style="{ width: deleteProgressPct + '%' }"></div>
          </div>

          <!-- Duplicate groups -->
          <div v-if="result.groups.length" class="groups-list">
            <div v-for="group in result.groups" :key="group.hash" class="dup-group">
              <div class="dup-group-header">
                <span>🔗 {{ group.count }} copies — <span class="dup-file-meta">{{ group.files[0].name }}</span></span>
                <button class="btn btn-ghost btn-sm" @click="selectGroup(group)">Select extras</button>
              </div>
              <div
                v-for="(file, idx) in group.files"
                :key="file.id"
                class="dup-file"
                :class="{ 'dup-file-selected': selectedIds.includes(file.id), 'dup-file-keep': idx === 0 }"
                @click="toggleFile(file.id)"
              >
                <input
                  type="checkbox"
                  :value="file.id"
                  v-model="selectedIds"
                  @click.stop
                />
                <span class="dup-file-name">{{ file.name }}</span>
                <span class="dup-file-meta">
                  {{ formatSize(file.size) }}
                  · {{ formatDate(file.modifiedTime) }}
                  <span v-if="idx === 0" class="keep-tag">KEEP</span>
                </span>
              </div>
            </div>
          </div>

          <!-- No duplicates -->
          <div v-else class="empty-state success">
            <span>✅</span>
            <p>No duplicates found! Your folder is clean.</p>
          </div>
        </template>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue';
import { getFolders, getDuplicates, cleanupDuplicates } from '../api/client';

const props = defineProps({ authenticated: Boolean, config: Object });

const folders = ref([]);
const folderId = ref('');
const loading = ref(false);
const deleting = ref(false);
const deleteProgress = ref(0);
const result = ref(null);
const selectedIds = ref([]);

const deleteProgressPct = computed(() =>
  selectedIds.value.length ? Math.round((deleteProgress.value / selectedIds.value.length) * 100) : 0
);

// Toast
const toast = ref({ show: false, message: '', type: 'success' });
function showToast(message, type = 'success') {
  toast.value = { show: true, message, type };
  setTimeout(() => { toast.value.show = false; }, 3500);
}

watch(() => props.authenticated, (v) => { if (v) loadFolders(); }, { immediate: true });

async function loadFolders() {
  try { folders.value = await getFolders(); } catch (e) { /* ignored */ }
}

async function scan() {
  loading.value = true;
  selectedIds.value = [];
  result.value = null;
  try {
    result.value = await getDuplicates(folderId.value);
    if (result.value.duplicate_groups === 0) showToast('No duplicates found — folder is clean! ✅');
    else showToast(`Found ${result.value.duplicate_groups} duplicate group(s).`, 'warn');
  } catch (e) {
    showToast(e.message, 'error');
  } finally {
    loading.value = false;
  }
}

function autoSelect() {
  selectedIds.value = [];
  for (const group of result.value.groups) {
    for (let i = 1; i < group.files.length; i++) {
      selectedIds.value.push(group.files[i].id);
    }
  }
}

function selectGroup(group) {
  for (let i = 1; i < group.files.length; i++) {
    const id = group.files[i].id;
    if (!selectedIds.value.includes(id)) selectedIds.value.push(id);
  }
}

function toggleFile(id) {
  const idx = selectedIds.value.indexOf(id);
  if (idx === -1) selectedIds.value.push(id);
  else selectedIds.value.splice(idx, 1);
}

async function deleteSelected() {
  if (!confirm(`Delete ${selectedIds.value.length} file(s)? This cannot be undone.`)) return;
  deleting.value = true;
  deleteProgress.value = 0;
  const toDelete = [...selectedIds.value];
  
  cleanupDuplicates(
    toDelete,
    (progressData) => {
      // onProgress callback
      deleteProgress.value = progressData.deleted + progressData.errors.length;
    },
    async () => {
      // onDone callback
      deleting.value = false;
      showToast(`Finished deleting! 🗑️`);
      selectedIds.value = [];
      await scan();
    },
    (err) => {
      // onError callback
      deleting.value = false;
      showToast(err.message, 'error');
    }
  );
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
/* ── Layout ── */
.scan-row {
  display: flex;
  align-items: flex-end;
  gap: 0.75rem;
  margin-bottom: 1rem;
  flex-wrap: wrap;
}
.result-summary { margin-bottom: 0.75rem; }
.action-bar {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
  flex-wrap: wrap;
}
.groups-list { margin-top: 0.5rem; }

/* ── Keep tag ── */
.keep-tag {
  display: inline-block;
  font-size: 0.65rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  background: var(--primary);
  color: #fff;
  border-radius: 3px;
  padding: 1px 5px;
  margin-left: 4px;
  vertical-align: middle;
}

/* ── File row highlight ── */
.dup-file {
  cursor: pointer;
  transition: background 0.1s;
}
.dup-file:hover { background: rgba(255,255,255,0.04); }
.dup-file-selected { background: rgba(239,68,68,0.08) !important; }

/* ── Spinner ── */
.spinner {
  display: inline-block;
  width: 13px;
  height: 13px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  margin-right: 4px;
  vertical-align: middle;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* ── Skeleton loader ── */
.skeleton-wrap { padding: 0.75rem 0; }
.skeleton-label {
  font-size: 0.8rem;
  color: var(--text-muted);
  margin-bottom: 0.75rem;
  animation: pulse 1.4s ease infinite;
}
.skeleton-bar {
  height: 12px;
  border-radius: 6px;
  background: var(--border);
  margin-bottom: 0.5rem;
  animation: pulse 1.4s ease infinite;
}
@keyframes pulse { 0%,100%{opacity:0.4} 50%{opacity:1} }

/* ── Progress bar ── */
.progress-wrap {
  height: 4px;
  background: var(--border);
  border-radius: 2px;
  overflow: hidden;
  margin-bottom: 0.75rem;
}
.progress-bar {
  height: 100%;
  background: var(--primary);
  border-radius: 2px;
  transition: width 0.3s ease;
}

/* ── Toast ── */
.toast {
  position: fixed;
  bottom: 1.5rem;
  right: 1.5rem;
  padding: 0.65rem 1rem;
  border-radius: var(--radius-sm);
  font-size: 0.85rem;
  font-weight: 500;
  z-index: 999;
  box-shadow: 0 4px 16px rgba(0,0,0,0.3);
}
.toast-success { background: #166534; color: #bbf7d0; border: 1px solid #15803d; }
.toast-warn    { background: #713f12; color: #fef08a; border: 1px solid #ca8a04; }
.toast-error   { background: #7f1d1d; color: #fecaca; border: 1px solid #dc2626; }
.toast-enter-active, .toast-leave-active { transition: all 0.3s ease; }
.toast-enter-from, .toast-leave-to { opacity: 0; transform: translateY(10px); }

/* ── Empty states ── */
.empty-state {
  text-align: center;
  padding: 2rem 1rem;
  color: var(--text-muted);
}
.empty-state span { font-size: 2rem; }
.empty-state p { margin-top: 0.5rem; font-size: 0.9rem; }
.empty-state.success p { color: var(--green); }

/* ── Btn danger ── */
.btn-danger {
  background: #dc2626;
  color: #fff;
  border: none;
}
.btn-danger:hover:not(:disabled) { background: #b91c1c; }
.btn-danger:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
