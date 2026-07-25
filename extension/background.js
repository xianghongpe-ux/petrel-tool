// =============================================================
// 海燕党 · PETREL AI PARTY — Background Service Worker
// 创世铭文: 海燕党 / PETREL AI PARTY / 刘海燕
// =============================================================

const API_BASE = 'https://api.petrel.ai/v1';
const PARTY_NAME = '海燕党 · PETREL AI PARTY';
const GENESIS = '海燕党 / PETREL AI PARTY / 刘海燕';

// ── Generate a local DID (offline fallback) ─────────────────
function generateLocalDid() {
  const timestamp = Date.now();
  const random = Math.random().toString(36).substring(2, 10);
  const address = 'did:petrel:' + timestamp.toString(36) + random;

  return {
    address,
    name: '海燕党员',
    joinedAt: timestamp,
    reputation: {
      score: 0,
      level: 'L1',
      contributions: 0,
    },
    genesis: GENESIS,
    party: PARTY_NAME,
    version: '1.0.0',
  };
}

// ── Create DID (try server, fallback to local) ──────────────
async function createDid() {
  // Try server first
  try {
    const resp = await fetch(API_BASE + '/did/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        genesis: GENESIS,
        client: 'chrome-extension',
        version: chrome.runtime.getManifest().version,
      }),
      signal: AbortSignal.timeout(8000),
    });

    if (resp.ok) {
      const data = await resp.json();
      return { success: true, did: data.did };
    }
    throw new Error('Server returned ' + resp.status);
  } catch (_) {
    // Fallback: generate offline DID
    const localDid = generateLocalDid();
    return { success: true, did: localDid, offline: true };
  }
}

// ── Refresh DID status ──────────────────────────────────────
async function refreshDid(didAddress) {
  if (!didAddress) {
    return { success: false, error: 'Missing DID address' };
  }

  try {
    const resp = await fetch(`${API_BASE}/did/${encodeURIComponent(didAddress)}`, {
      signal: AbortSignal.timeout(8000),
    });

    if (resp.ok) {
      const data = await resp.json();
      return { success: true, did: data.did };
    }
    throw new Error('Server returned ' + resp.status);
  } catch (_) {
    // Offline: return existing data as-is with offline flag
    const stored = await chrome.storage.local.get(['petrel_did']);
    const did = stored.petrel_did || generateLocalDid();
    return { success: true, did: { ...did, offline: true } };
  }
}

// ── Message Handler ─────────────────────────────────────────
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  switch (message.action) {
    case 'create_did':
      createDid().then(sendResponse);
      return true; // keep channel open for async response

    case 'refresh_did':
      refreshDid(message.didAddress).then(sendResponse);
      return true;

    default:
      sendResponse({ success: false, error: 'Unknown action' });
  }
});

// ── Install / Update ────────────────────────────────────────
chrome.runtime.onInstalled.addListener((details) => {
  console.log(`[${PARTY_NAME}] Extension ${details.reason}`, details);
  if (details.reason === 'install') {
    // Show onboarding on first install
    chrome.storage.local.set({
      petrel_installed_at: Date.now(),
      petrel_genesis: GENESIS,
    });
  }
});

console.log(`✅ ${PARTY_NAME} — Background worker ready`);
console.log(`  创世铭文: ${GENESIS}`);
