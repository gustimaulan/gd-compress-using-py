<template>
  <div>
    <!-- Drive Status -->
    <div class="card">
      <div class="card-title"><span class="icon">🔗</span> Google Drive</div>
      <span v-if="authenticated" class="badge badge-green">✓ Drive connected</span>
      <span v-else class="badge badge-red">Drive not connected — try logging out and back in</span>
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
        <div class="field field-checkbox">
          <label>Delete originals</label>
          <input type="checkbox" v-model="form.delete_original" />
        </div>
      </div>
      <div style="display:flex;gap:0.5rem;margin-top:1rem;">
        <button class="btn btn-ghost btn-sm" @click="doSaveConfig">💾 Save Config</button>
        <button
          class="btn btn-primary"
          @click="doStartJob"
          :disabled="!authenticated || !form.folder_id || jobRunning"
        >
          🚀 {{ jobRunning ? 'Running…' : 'Start Compression' }}
        </button>
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

<script setup>
import { ref, onMounted, nextTick, watch } from 'vue';
import { saveConfig, getFolders, startJob, getJobs, streamJob } from '../api/client';

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

const form = ref({
  folder_id: '',
  output_folder_id: '',
  quality: 80,
  min_size_kb: 0,
  max_width: null,
  max_height: null,
  delete_original: false,
});

watch(() => props.config, (cfg) => {
  if (cfg) {
    form.value.folder_id = cfg.folder_id || '';
    form.value.output_folder_id = cfg.output_folder_id || '';
    form.value.quality = cfg.quality ?? 80;
    form.value.min_size_kb = cfg.min_size_kb || 0;
    form.value.max_width = cfg.max_width || null;
    form.value.max_height = cfg.max_height || null;
    form.value.delete_original = !!cfg.delete_original;
  }
}, { immediate: true });

watch(() => props.authenticated, (v) => {
  if (v) loadFolders();
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
  try { await saveConfig(form.value); } catch (e) { alert(e.message); }
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
  } catch (e) { alert(e.message); }
}
</script>
