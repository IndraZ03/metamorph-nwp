const DB_NAME = 'metamorph-nwp-draw';
const STORE = 'kv';
const KEY = 'state';
const VERSION = 1;

function openDb() {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === 'undefined') {
      reject(new Error('IndexedDB tidak tersedia'));
      return;
    }
    const req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE)) db.createObjectStore(STORE);
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error || new Error('IndexedDB gagal dibuka'));
  });
}

export async function loadDrawings() {
  const db = await openDb();
  try {
    return await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, 'readonly');
      const req = tx.objectStore(STORE).get(KEY);
      req.onsuccess = () => resolve(req.result || null);
      req.onerror = () => reject(req.error);
    });
  } finally {
    db.close();
  }
}

function clonePlain(value) {
  try {
    return JSON.parse(JSON.stringify(value));
  } catch (err) {
    throw new Error(err?.message || 'Gagal serialisasi drawing');
  }
}

export async function saveDrawings(payload) {
  const db = await openDb();
  const record = clonePlain({
    version: VERSION,
    savedAt: new Date().toISOString(),
    units: payload.units === 'nm' ? 'nm' : 'km',
    activeLayerId: payload.activeLayerId || null,
    layers: Array.isArray(payload.layers) ? payload.layers : [],
  });
  try {
    await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, 'readwrite');
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
      tx.objectStore(STORE).put(record, KEY);
    });
  } finally {
    db.close();
  }
}

export function sanitizeText(value, max = 200) {
  return String(value ?? '')
    .replace(/[<>]/g, '')
    .replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/g, '')
    .slice(0, max);
}

export function downloadBlob(filename, blob) {
  const a = document.createElement('a');
  const url = URL.createObjectURL(blob);
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function downloadText(filename, text, type = 'application/geo+json') {
  downloadBlob(filename, new Blob([text], { type }));
}
