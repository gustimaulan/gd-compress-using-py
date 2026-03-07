const BASE = '';

function getAuthToken() {
  return sessionStorage.getItem('auth_token') || '';
}

function authHeaders() {
  const token = getAuthToken();
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  return headers;
}

async function request(path, opts = {}) {
  const url = `${BASE}${path}`;
  const res = await fetch(url, {
    headers: { ...authHeaders(), ...opts.headers },
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
  const result = await request('/api/auth/logout', { method: 'POST' });
  sessionStorage.removeItem('auth_token');
  localStorage.removeItem('auth_token');
  return result;
}

export async function uploadFile(endpoint, file) {
  const fd = new FormData();
  fd.append('file', file);
  const token = getAuthToken();
  const headers = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(`${BASE}${endpoint}`, { method: 'POST', body: fd, headers });
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

export function cleanupDuplicates(fileIds, onProgress, onDone, onError) {
  const token = getAuthToken();
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  fetch(`${BASE}/api/drive/duplicates/cleanup`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ file_ids: fileIds }),
  })
    .then(async (res) => {
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.error || `HTTP ${res.status}`);
      }
      
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop();
        
        for (const part of parts) {
          if (part.startsWith('data: ')) {
            const dataStr = part.substring(6);
            if (dataStr === '__done__') {
              if (onDone) onDone();
              return;
            }
            try {
              const parsed = JSON.parse(dataStr);
              if (onProgress) onProgress(parsed);
            } catch (e) {
              console.error('Failed to parse SSE JSON', e);
            }
          }
        }
      }
    })
    .catch((err) => {
      if (onError) onError(err);
    });
}

export async function startOAuth() {
  return request('/api/auth/login');
}

export function streamJob(jobId, onMessage, onDone) {
  const token = getAuthToken();
  // EventSource doesn't support custom headers, so pass token as query param
  const url = `${BASE}/api/jobs/${jobId}/stream?token=${encodeURIComponent(token)}`;
  const es = new EventSource(url);
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
