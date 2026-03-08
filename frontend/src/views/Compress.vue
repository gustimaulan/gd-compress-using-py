<template>
  <div>
    <!-- Drive Status -->
    <div class="card">
      <div class="card-title"><span class="icon">🔗</span> Google Drive</div>
      <span v-if="authenticated" class="badge badge-green">✓ Drive connected</span>
      <span v-else class="badge badge-red">Drive not connected — try logging out and back in</span>
      
      <div v-if="driveStorage && driveStorage.limit > 0" style="margin-top: 1rem;">
        <div style="display:flex; justify-content: space-between; font-size: 0.9em; margin-bottom:0.2rem;">
          <span>Storage Used: {{ formatBytes(driveStorage.usage) }}</span>
          <span>Max: {{ formatBytes(driveStorage.limit) }}</span>
        </div>
        <div style="background:var(--border);height:8px;border-radius:4px;overflow:hidden">
          <div :style="`background:var(--accent);height:100%;width:${Math.min(100, (driveStorage.usage / driveStorage.limit) * 100)}%`"></div>
        </div>
      </div>
    </div>

    <!-- Config Section -->
    <div class="card">
      <div class="card-title"><span class="icon">⚙️</span> Configuration</div>
      <div class="config-grid">
        <div class="field">
          <label>Source Folder *</label>
          <div class="select-wrap">
            <select v-model="form.folder_id" :disabled="!authenticated || foldersLoading">
              <option value="">— select a folder —</option>
              <option v-for="f in folders" :key="f.id" :value="f.id">{{ f.name }}</option>
            </select>
            <button class="btn btn-ghost btn-sm" @click="loadFolders" title="Refresh">↻</button>
          </div>
        </div>
        <div class="field">
          <label>Output Folder</label>
          <select v-model="form.output_folder_id" :disabled="!authenticated || foldersLoading">
            <option value="">— same as source —</option>
            <option v-for="f in folders" :key="f.id" :value="f.id">{{ f.name }}</option>
          </select>
        </div>
        <div class="field">
          <label>Quality: {{ form.quality }}</label>
          <input type="range" min="10" max="100" step="5" v-model.number="form.quality" />
        </div>
        <div class="field">
          <label>Min Size (KB)</label>
          <input type="number" v-model.number="form.min_size_kb" placeholder="0" />
        </div>
        <div class="field">
          <label>Max Width (px)</label>
          <input type="number" v-model.number="form.max_width" placeholder="No limit" />
        </div>
        <div class="field">
          <label>Max Height (px)</label>
          <input type="number" v-model.number="form.max_height" placeholder="No limit" />
        </div>
        <div class="field field-checkbox alert-danger" style="margin-top: 1rem; border-radius: var(--radius-sm); border: 1px solid var(--red); background: rgba(239, 68, 68, 0.1); padding: 0.85rem; display: flex; align-items: center; gap: 0.75rem;">
          <input type="checkbox" v-model="form.delete_original" id="deleteOriginals" style="transform: scale(1.2); cursor: pointer;" />
          <div style="flex: 1;">
            <label for="deleteOriginals" style="color: var(--red); font-weight: 600; cursor: pointer; font-size: 0.9rem;">Delete Originals After Compression</label>
          </div>
        </div>
      </div>
      <div :style="{ display: 'flex', gap: '1rem', marginTop: '1rem', flexDirection: isMobile ? 'column' : 'row', alignItems: isMobile ? 'stretch' : 'flex-end', justifyContent: 'space-between' }">
        
        <!-- Left: Configure Auto-Run details if schedule mode is active -->
        <div :style="isMobile ? { width: '100%' } : { flex: 1 }">
          <div v-if="runMode === 'schedule'" :style="{ background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', padding: '1rem', marginRight: isMobile ? '0' : '1rem' }">
            <label style="display:block;margin-bottom:0.5rem;font-weight:600;font-size:0.85rem;">Set Schedule Recurrence</label>
            <select v-model="scheduleType" style="margin-bottom:0.5rem;">
              <option value="0 2 * * *">Daily at 2 AM</option>
              <option value="0 2 * * 0">Weekly (Sunday at 2 AM)</option>
              <option value="custom">Custom Cron Expression</option>
            </select>
            <div v-if="scheduleType === 'custom'" style="margin-top: 0.5rem;">
              <input type="text" v-model="form.cron_schedule" placeholder="e.g. 0 2 * * *" />
              <span style="font-size:0.8em;display:block;margin-top:0.25rem;"><a href="https://crontab.guru" target="_blank" style="color:var(--primary)">Cron Formatting Help</a></span>
            </div>
            <small v-if="nextRunPreview" style="color:var(--text-light);display:block;margin-top:0.5rem;font-weight:500;">
              Preview next run: {{ nextRunPreview.toLocaleString('id-ID', { timeZone: 'Asia/Jakarta', dateStyle: 'short', timeStyle: 'medium' }) }}
            </small>
            <small v-else-if="config && config.next_run > 0 && runMode === 'schedule'" style="color:var(--text-muted);display:block;margin-top:0.5rem;">
              Last saved run: {{ new Date(config.next_run * 1000).toLocaleString('id-ID', { timeZone: 'Asia/Jakarta', dateStyle: 'short', timeStyle: 'medium' }) }}
            </small>
          </div>
        </div>

        <!-- Right: Action Buttons -->
        <div :style="{ display: 'flex', gap: '0.5rem', alignItems: 'center', width: isMobile ? '100%' : 'auto' }">
          <!-- Split Button -->
          <div class="split-btn-group" :style="{ position: 'relative', display: 'flex', width: isMobile ? '100%' : 'auto' }">
            <!-- Main Action -->
            <button
              v-if="runMode === 'manual'"
              class="btn btn-primary split-btn-main"
              @click="doStartJob"
              :disabled="!authenticated || !form.folder_id || jobRunning"
              style="border-top-right-radius:0;border-bottom-right-radius:0;padding:0.6rem 1.2rem;border-right:1px solid rgba(0,0,0,0.1);"
            >
              🚀 {{ jobRunning ? 'Running…' : 'Save & Start Now' }}
            </button>
            <button
              v-else-if="runMode === 'save_only'"
              class="btn btn-primary split-btn-main"
              @click="doSaveConfig"
              :disabled="!authenticated || !form.folder_id"
              style="border-top-right-radius:0;border-bottom-right-radius:0;padding:0.6rem 1.2rem;border-right:1px solid rgba(0,0,0,0.1);"
            >
              💾 Save Settings Only
            </button>
            <button
              v-else
              class="btn btn-primary split-btn-main"
              @click="doSaveConfig"
               style="border-top-right-radius:0;border-bottom-right-radius:0;padding:0.6rem 1.2rem;border-right:1px solid rgba(0,0,0,0.1);"
            >
              ⏱️ Save Auto-Schedule
            </button>

            <!-- Dropdown Toggle -->
            <button 
              class="btn btn-primary split-btn-toggle" 
              @click="dropdownOpen = !dropdownOpen"
              style="border-top-left-radius:0;border-bottom-left-radius:0;padding: 0.6rem 0.5rem;"
            >
              ▼
            </button>

            <!-- Dropdown Menu -->
            <div v-if="dropdownOpen" class="split-btn-menu">
              <div class="split-btn-item" @click="runMode = 'manual'; dropdownOpen = false">
                <strong>▶️ Run Immediately</strong>
                <span>Save and start immediately</span>
              </div>
              <div class="split-btn-item" @click="runMode = 'schedule'; dropdownOpen = false">
                <strong>⏱️ Schedule Later</strong>
                <span>Set automated recurrence</span>
              </div>
              <div class="split-btn-item" @click="runMode = 'save_only'; dropdownOpen = false">
                <strong>💾 Save Draft Settings</strong>
                <span>Set folders, but do not run</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Log Panel -->
    <div v-if="logs.length" class="card">
      <div class="card-title"><span class="icon">📋</span> Job Log</div>
      <div class="log-panel" ref="logPanel">
        <div v-for="(line, i) in logs" :key="i">{{ line }}</div>
      </div>
    </div>

    <!-- Job History -->
    <div v-if="jobHistory.length" class="card">
      <div class="card-title"><span class="icon">📜</span> Job History</div>
      <div v-for="job in jobHistory" :key="job.id" class="dup-file" style="border-top:none;border-bottom:1px solid var(--border);">
        <span class="badge" :class="job.status === 'done' ? 'badge-green' : job.status === 'running' ? 'badge-yellow' : 'badge-red'">
          {{ job.status }}
        </span>
        <span class="dup-file-name">Job {{ job.id }}</span>
        <span class="dup-file-meta">✓{{ job.stats.success }} ✗{{ job.stats.failed }} / {{ job.stats.total }}</span>
      </div>
    </div>
  </div>
</template>

<!-- Click outside directive logic handled by minimal dropdown toggle if needed -->
<script setup>
import { ref, computed, onMounted, nextTick, watch, onUnmounted } from 'vue';
import { saveConfig, getFolders, startJob, getJobs, streamJob, getDriveStorage } from '../api/client';
import { useToast } from '../composables/useToast';
import { useMobile } from '../composables/useMobile';
import cronParser from 'cron-parser';

const { addToast } = useToast();
const { isMobile } = useMobile();

const props = defineProps({
  authenticated: Boolean,
  config: Object,
});

const emit = defineEmits(['refresh-status']);

const folders = ref([]);
const foldersLoading = ref(false);
const jobRunning = ref(false);
const logs = ref([]);
const logPanel = ref(null);
const jobHistory = ref([]);
const driveStorage = ref(null);

const dropdownOpen = ref(false);

// Close dropdown when clicking outside
const closeDropdown = (e) => {
  if (!e.target.closest('.split-btn-group')) {
    dropdownOpen.value = false;
  }
};
onMounted(() => {
  document.addEventListener('click', closeDropdown);
  loadJobHistory();
});
onUnmounted(() => {
  document.removeEventListener('click', closeDropdown);
});

const form = ref({
  folder_id: '',
  output_folder_id: '',
  quality: 80,
  min_size_kb: 0,
  max_width: null,
  max_height: null,
  delete_original: false,
  cron_schedule: '',
});

const runMode = ref('manual');
const scheduleType = ref('0 2 * * *');

const nextRunPreview = computed(() => {
  if (runMode.value !== 'schedule') return null;
  const cronExpr = scheduleType.value === 'custom' ? form.value.cron_schedule : scheduleType.value;
  if (!cronExpr) return null;
  try {
    const interval = cronParser.parseExpression(cronExpr, { tz: 'Asia/Jakarta' });
    return interval.next().toDate();
  } catch (e) {
    return null;
  }
});

watch(runMode, (mode) => {
  if (mode === 'manual' || mode === 'save_only') {
    form.value.cron_schedule = '';
  } else {
    form.value.cron_schedule = scheduleType.value;
  }
});

watch(scheduleType, (newVal) => {
  if (newVal !== 'custom') {
    form.value.cron_schedule = newVal;
  }
});

watch(() => form.value.cron_schedule, (newVal) => {
  if (!newVal) {
    if (runMode.value === 'schedule') runMode.value = 'manual';
    scheduleType.value = '0 2 * * *'; // default fallback
  } else {
    runMode.value = 'schedule';
    if (newVal === '0 2 * * *') {
      scheduleType.value = '0 2 * * *';
    } else if (newVal === '0 2 * * 0') {
      scheduleType.value = '0 2 * * 0';
    } else {
      scheduleType.value = 'custom';
    }
  }
});

function formatBytes(bytes) {
  if (bytes === 0) return '0 B';
  const k = 1024, sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

watch(() => props.config, (cfg) => {
  if (cfg) {
    form.value.folder_id = cfg.folder_id || '';
    form.value.output_folder_id = cfg.output_folder_id || '';
    form.value.quality = cfg.quality ?? 80;
    form.value.min_size_kb = cfg.min_size_kb || 0;
    form.value.max_width = cfg.max_width || null;
    form.value.max_height = cfg.max_height || null;
    form.value.delete_original = !!cfg.delete_original;
    form.value.cron_schedule = cfg.cron_schedule || '';
  }
}, { immediate: true });

watch(() => props.authenticated, (v) => {
  if (v) {
    loadFolders();
    loadStorage();
  }
}, { immediate: true });

onMounted(loadJobHistory);

async function loadFolders() {
  foldersLoading.value = true;
  try {
    folders.value = await getFolders();
  } catch (e) {
    console.error('Folder load failed', e);
  } finally {
    foldersLoading.value = false;
  }
}

async function loadStorage() {
  try {
    driveStorage.value = await getDriveStorage();
  } catch (e) {
    console.error('Failed to load drive storage', e);
  }
}

async function loadJobHistory() {
  try {
    const jobs = await getJobs();
    jobHistory.value = jobs;
    const runningJob = jobs.find(j => j.status === 'running');
    if (runningJob && !jobRunning.value) {
      jobRunning.value = true;
      streamJob(
        runningJob.id,
        (msg) => {
          logs.value.push(msg);
          nextTick(() => { if (logPanel.value) logPanel.value.scrollTop = logPanel.value.scrollHeight; });
        },
        () => { jobRunning.value = false; loadJobHistory(); },
      );
    }
  } catch (e) { /* ok */ }
}

async function doSaveConfig() {
  try { 
    await saveConfig(form.value); 
    addToast('Configuration successfully saved!', 'success');
    emit('refresh-status');
  } catch (e) { 
    addToast('Failed to save config: ' + e.message, 'error'); 
  }
}

async function doStartJob() {
  try {
    await saveConfig(form.value);
    const data = await startJob();
    jobRunning.value = true;
    logs.value = [];
    streamJob(
      data.job_id,
      (msg) => {
        logs.value.push(msg);
        nextTick(() => { if (logPanel.value) logPanel.value.scrollTop = logPanel.value.scrollHeight; });
      },
      () => { jobRunning.value = false; loadJobHistory(); },
    );
  } catch (e) { 
    addToast('Job failed: ' + e.message, 'error'); 
  }
}
</script>
