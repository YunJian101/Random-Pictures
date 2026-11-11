/**
 * 管理后台 · 系统设置：站点信息与功能开关
 */

import { $, api, Toast, util } from './core.js';

/* ============================== 设置 ============================== */
export const CONFIG_KEYS = [
  // 站点信息
  'site_name', 'site_domain', 'icp_beian', 'beian_link', 'timezone', 'favicon_url',
  // 功能开关
  'show_beian_info', 'enable_access_log', 'enable_path_traversal_protection',
  'enable_hotlink_protection', 'enable_ip_blacklist',
  // 限流与登录防护（运行时配置，保存即生效）
  'enable_rate_limit', 'rate_limit_per_minute', 'rate_limit_auth_per_minute',
  'enable_login_guard', 'login_max_failures', 'login_ip_max_failures',
  'login_lock_base_seconds', 'login_lock_max_seconds',
  'max_sessions_per_user', 'session_cleanup_interval', 'audit_retention_days',
  'enable_register_guard', 'register_max_per_window',
  'register_window_seconds', 'register_min_interval_seconds',
];
export const BOOL_KEYS = [
  'show_beian_info', 'enable_access_log', 'enable_path_traversal_protection',
  'enable_hotlink_protection', 'enable_ip_blacklist',
  'enable_rate_limit', 'enable_login_guard', 'enable_register_guard',
];

export async function loadConfig() {
  try {
    const res = await api('/api/admin/system/config');
    const config = (res && res.data) || {};
    CONFIG_KEYS.forEach((key) => {
      const el = $('cfg-' + key);
      if (!el) return;
      const value = config[key] ? config[key].value : '';
      if (BOOL_KEYS.includes(key)) el.checked = value === 'true';
      else el.value = value;
    });
  } catch (e) {
    Toast.error(e.message || '配置加载失败');
  }
}

$('settings-save').addEventListener('click', async () => {
  const items = {};
  CONFIG_KEYS.forEach((key) => {
    const el = $('cfg-' + key);
    if (!el) return;
    items[key] = BOOL_KEYS.includes(key) ? (el.checked ? 'true' : 'false') : el.value.trim();
  });

  const btn = $('settings-save');
  btn.disabled = true;
  btn.innerHTML = '<div class="spinner" style="border-color:rgba(255,255,255,.35);border-top-color:#fff"></div>保存中…';
  try {
    await api('/api/admin/system/config/batch', { method: 'PUT', body: { items } });
    Toast.success('设置已保存');
    const info = await api('/api/system/info');
    const d = (info && info.data) || {};
    if (d.site_name) {
      document.title = `管理后台 · ${d.site_name}`;
      document.querySelectorAll('[data-site-name]').forEach((el) => { el.textContent = d.site_name; });
    }
  } catch (e) {
    Toast.error(e.message || '保存失败');
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i>保存设置';
  }
});

$('settings-reload').addEventListener('click', loadConfig);

$('settings-reset').addEventListener('click', async () => {
  const ok = await util.confirm('恢复默认设置', '所有配置项都会恢复为默认值，站点名称等信息将被重置。确定继续？', '恢复默认');
  if (!ok) return;
  try {
    await api('/api/admin/system/config/reset', { method: 'POST' });
    Toast.success('已恢复默认设置');
    loadConfig();
  } catch (e) {
    Toast.error(e.message || '重置失败');
  }
});

