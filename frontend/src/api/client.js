const BASE = '';

async function request(path, opts = {}) {
  const url = `${BASE}${path}`;
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...opts.headers },
    ...opts,
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

export async function getStatus() {
  return request('/api/status');
}

export async function login(password) {
  return request('/api/login', {
    method: 'POST',
    body: JSON.stringify({ password }),
  });
}

export async function logout() {
  return request('/api/logout', { method: 'POST' });
}

export async function uploadFile(endpoint, file) {
  const fd = new FormData();
  fd.append('file', file);
  const res = await fetch(`${BASE}${endpoint}`, { method: 'POST', body: fd });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || 'Upload failed');
  return data;
}

export async function getConfig() {
  return request('/api/config');
}

export async function saveConfig(config) {
  return request('/api/config', {
    method: 'POST',
    body: JSON.stringify(config),
  });
}

export async function getFolders() {
  return request('/api/drive/folders');
}

export async function startJob() {
  return request('/api/jobs', { method: 'POST' });
}

export async function getJobs() {
  return request('/api/jobs');
}

export async function getJob(id) {
  return request(`/api/jobs/${id}`);
}

export async function getDuplicates(folderId) {
  return request(`/api/drive/duplicates?folder_id=${encodeURIComponent(folderId)}`);
}

export async function cleanupDuplicates(fileIds) {
  return request('/api/drive/duplicates/cleanup', {
    method: 'POST',
    body: JSON.stringify({ file_ids: fileIds }),
  });
}

export async function startOAuth() {
  return request('/api/oauth/start');
}

export function streamJob(jobId, onMessage, onDone) {
  const es = new EventSource(`${BASE}/api/jobs/${jobId}/stream`);
  es.onmessage = (e) => {
    if (e.data === '__done__') {
      es.close();
      if (onDone) onDone();
      return;
    }
    if (e.data === '__ping__') return;
    if (onMessage) onMessage(e.data);
  };
  es.onerror = () => {
    es.close();
    if (onDone) onDone();
  };
  return es;
}
