// =============================================================
// 海燕党 · PETREL AI PARTY — Chrome Extension Popup Logic
// 创世铭文: 海燕党 / PETREL AI PARTY / 刘海燕
// =============================================================

(function () {
  'use strict';

  // ── DOM Refs ──────────────────────────────────────────────
  const $ = (id) => document.getElementById(id);

  const loadingView  = $('loading-view');
  const noDidView    = $('no-did-view');
  const hasDidView   = $('has-did-view');
  const btnCreate    = $('btn-create-did');
  const createProg   = $('create-progress');
  const createErr    = $('create-error');
  const btnRefresh   = $('btn-refresh');
  const btnGotoWeb   = $('btn-goto-web');
  const btnClear     = $('btn-clear');

  const elAddress     = $('did-address');
  const elName        = $('did-name');
  const elJoined      = $('did-joined');
  const elReputation  = $('did-reputation');

  // ── State ─────────────────────────────────────────────────
  let didData = null;

  // ── UI Helpers ────────────────────────────────────────────
  function showView(view) {
    [loadingView, noDidView, hasDidView].forEach((v) => v.classList.add('hidden'));
    view.classList.remove('hidden');
  }

  // ── Format helpers ────────────────────────────────────────
  function shortenAddr(addr) {
    if (!addr || addr.length < 12) return addr || '—';
    return addr.slice(0, 8) + '...' + addr.slice(-6);
  }

  function fmtDate(ts) {
    if (!ts) return '—';
    const d = new Date(ts);
    return d.toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric' });
  }

  // ── Load DID from storage ─────────────────────────────────
  async function loadDid() {
    showView(loadingView);
    try {
      const result = await chrome.storage.local.get(['petrel_did']);
      didData = result.petrel_did || null;
      render();
    } catch (err) {
      console.error('Failed to load DID:', err);
      showView(noDidView);
    }
  }

  // ── Render view based on state ────────────────────────────
  function render() {
    if (!didData) {
      showView(noDidView);
      btnCreate.disabled = false;
      createProg.classList.add('hidden');
      createErr.classList.add('hidden');
      return;
    }

    showView(hasDidView);
    elAddress.textContent    = shortenAddr(didData.address);
    elName.textContent       = didData.name || '海燕党员';
    elJoined.textContent     = fmtDate(didData.joinedAt);
    elReputation.textContent = didData.reputation
      ? `${didData.reputation.score ?? 0} 分 · 等级 ${didData.reputation.level ?? 'L1'}`
      : '待同步';
  }

  // ── Create DID ────────────────────────────────────────────
  async function createDid() {
    btnCreate.disabled = true;
    createProg.classList.remove('hidden');
    createErr.classList.add('hidden');

    try {
      // 通过 background.js 发送创建请求
      const result = await chrome.runtime.sendMessage({ action: 'create_did' });

      if (result && result.success && result.did) {
        didData = result.did;
        await chrome.storage.local.set({ petrel_did: didData });
        render();
      } else {
        throw new Error(result?.error || '创建失败');
      }
    } catch (err) {
      console.error('Create DID error:', err);
      createErr.textContent = '❌ ' + (err.message || '创建失败，请检查网络');
      createErr.classList.remove('hidden');
      btnCreate.disabled = false;
      createProg.classList.add('hidden');
    }
  }

  // ── Refresh DID status ────────────────────────────────────
  async function refreshDid() {
    btnRefresh.disabled = true;
    btnRefresh.textContent = '⏳ 刷新中...';

    try {
      const result = await chrome.runtime.sendMessage({
        action: 'refresh_did',
        didAddress: didData?.address,
      });

      if (result && result.success && result.did) {
        didData = { ...didData, ...result.did };
        await chrome.storage.local.set({ petrel_did: didData });
        render();
      } else {
        throw new Error(result?.error || '刷新失败');
      }
    } catch (err) {
      console.error('Refresh error:', err);
    } finally {
      btnRefresh.disabled = false;
      btnRefresh.textContent = '🔄 刷新状态';
    }
  }

  // ── Clear local data ──────────────────────────────────────
  async function clearData() {
    if (!confirm('确定清除本地 DID 数据？')) return;
    await chrome.storage.local.remove('petrel_did');
    didData = null;
    render();
  }

  // ── Open website ──────────────────────────────────────────
  function openWebsite() {
    chrome.tabs.create({ url: 'https://petrel.ai' });
  }

  // ── Event Bindings ────────────────────────────────────────
  btnCreate.addEventListener('click', createDid);
  btnRefresh.addEventListener('click', refreshDid);
  btnGotoWeb.addEventListener('click', openWebsite);
  btnClear.addEventListener('click', clearData);

  // ── Init ──────────────────────────────────────────────────
  document.addEventListener('DOMContentLoaded', loadDid);
})();
