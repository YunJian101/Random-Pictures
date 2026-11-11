/**
 * 管理后台 · 版本更新：检查、执行、备份与回滚
 */

import { $, api, Toast, util } from './core.js';

/* ============================== 版本更新 ============================== */
/** 语义化比较：a>b 返回 1，相等 0，a<b 返回 -1（1.0.3-beta 这类后缀按数字段拆开比） */
export function compareVersion(a, b) {
  const norm = (v) => String(v || '').replace(/^v/i, '').split(/[.\-+]/)
    .map((x) => parseInt(x, 10) || 0);
  const pa = norm(a);
  const pb = norm(b);
  const len = Math.max(pa.length, pb.length);
  for (let i = 0; i < len; i += 1) {
    const x = pa[i] || 0;
    const y = pb[i] || 0;
    if (x !== y) return x > y ? 1 : -1;
  }
  return 0;
}

export async function loadVersion() {
  try {
    const res = await api('/api/system/version');
    const d = (res && res.data) || {};
    $('ver-current').textContent = d.version ? 'v' + d.version : '未知';
    $('ver-current-date').textContent = d.version_date || '—';
  } catch (e) {
    $('ver-current').textContent = '未知';
  }
}

$('btn-check-update').addEventListener('click', async () => {
  const btn = $('btn-check-update');
  btn.disabled = true;
  btn.innerHTML = '<div class="spinner" style="border-color:rgba(255,255,255,.35);border-top-color:#fff"></div>检查中…';
  try {
    const res = await api('/api/system/check-update');
    const d = (res && res.data) || {};
    $('ver-latest').textContent = d.latest_version || '未知';
    $('ver-latest-date').textContent = d.latest_version_date || '—';

    const changelog = d.changelog || [];
    $('changelog-box').innerHTML = changelog.length
      ? changelog.map((item) => `
        <div class="changelog-item">
          <div class="row--between" style="margin-bottom:6px">
            <span class="strong">${util.escapeHtml(item.version)}</span>
            <span class="tiny dim">${util.escapeHtml(item.date || '')}</span>
          </div>
          <ul>${(item.changes || []).map((line) => `<li class="small muted" style="display:flex;gap:8px;padding:2px 0">
            <i class="fa-solid fa-circle" style="font-size:4px;margin-top:8px;color:var(--text-3);flex:0 0 auto"></i>
            <span>${util.escapeHtml(line)}</span></li>`).join('')}</ul>
        </div>`).join('')
      : '<div class="empty"><i class="fa-regular fa-file-lines"></i><p>暂无更新说明</p></div>';

    const current = $('ver-current').textContent.replace(/^v/, '');
    const latest = (d.latest_version || '').replace(/^v/, '');
    const diff = (latest && current) ? compareVersion(latest, current) : 0;
    // 只有 GitHub 上的版本「更高」才允许更新；用 !== 判断会把降级当成升级
    const hasUpdate = diff > 0;
    $('btn-execute-update').disabled = !hasUpdate;

    if (!latest || !current) Toast.warn('无法比较版本，请手动确认');
    else if (hasUpdate) Toast.info(`发现新版本 ${d.latest_version}`);
    else if (diff < 0) Toast.success(`本地 v${current} 已高于 GitHub 最新发布 ${d.latest_version}`);
    else Toast.success('已是最新版本');
  } catch (e) {
    Toast.error(e.message || '检查更新失败');
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<i class="fa-solid fa-magnifying-glass"></i>检查更新';
  }
});

$('btn-execute-update').addEventListener('click', async () => {
  const ok = await util.confirm('执行更新', '将从 GitHub 拉取最新代码并重启服务，期间可能出现短暂不可用。确定继续？', '开始更新');
  if (!ok) return;
  const btn = $('btn-execute-update');
  btn.disabled = true;
  btn.innerHTML = '<div class="spinner"></div>更新中…';
  try {
    const res = await api('/api/system/execute-update', { method: 'POST' });
    Toast.success((res && res.msg) || '更新已触发');
    setTimeout(loadVersion, 2500);
  } catch (e) {
    Toast.error(e.message || '更新失败');
    btn.disabled = false;
    btn.innerHTML = '<i class="fa-solid fa-download"></i>执行更新';
  }
});

$('btn-load-backups').addEventListener('click', async () => {
  const body = $('backup-table-body');
  body.innerHTML = '<tr><td colspan="5"><div class="empty"><div class="spinner"></div><p>加载中…</p></div></td></tr>';
  try {
    const res = await api('/api/system/backups');
    const backups = (res && res.data && res.data.backups) || [];
    if (!backups.length) {
      body.innerHTML = '<tr><td colspan="5"><div class="empty"><i class="fa-solid fa-box-archive"></i><p>暂无备份</p></div></td></tr>';
      return;
    }
    body.innerHTML = backups.map((b) => `
      <tr>
        <td>${b.id}</td>
        <td class="cell-strong">${util.escapeHtml(b.time)}</td>
        <td>${util.escapeHtml(b.version || '—')}</td>
        <td>${util.escapeHtml(b.size || '—')}</td>
        <td><button class="btn btn--outline btn--sm" data-rollback="${util.escapeHtml(b.filename)}">回滚</button></td>
      </tr>`).join('');

    body.querySelectorAll('[data-rollback]').forEach((btn) => {
      btn.addEventListener('click', () => rollback(btn.dataset.rollback));
    });
  } catch (e) {
    body.innerHTML = `<tr><td colspan="5"><div class="empty"><i class="fa-solid fa-triangle-exclamation"></i><p>${util.escapeHtml(e.message)}</p></div></td></tr>`;
  }
});

export async function rollback(filename) {
  const ok = await util.confirm('回滚版本', '回滚会把代码恢复到该备份的状态，请确认已了解风险。', '回滚');
  if (!ok) return;
  try {
    await api('/api/system/rollback', { method: 'POST', body: { backup_path: filename } });
    Toast.success('回滚已触发');
  } catch (e) {
    Toast.error(e.message || '回滚失败');
  }
}

/* ============================== 站点信息 ============================== */
(async function loadSiteInfo() {
  try {
    const res = await api('/api/system/info');
    const d = (res && res.data) || {};
    if (d.site_name) {
      document.title = `管理后台 · ${d.site_name}`;
      document.querySelectorAll('[data-site-name]').forEach((el) => { el.textContent = d.site_name; });
    }
    if (d.favicon_url) $('favicon').href = d.favicon_url;
  } catch (e) { /* noop */ }
})();

