/**
 * 管理后台 · 审核日志
 *
 * 只读页面：展示谁在什么时候对什么做了什么。
 * 支持按动作、关键字、日期区间筛选，分页由 core 的 renderPagination 统一渲染。
 */

import { $, api, Toast, util, renderPagination } from './core.js';

const PAGE_SIZE = 20;

const pageState = {
  page: 1,
  action: '',
  keyword: '',
  start: '',
  end: '',
  totalPages: 1,
};

/* ============================== 数据加载 ============================== */
export async function loadAudit(page) {
  if (page) pageState.page = page;

  const body = $('audit-body');
  body.innerHTML = '<tr><td colspan="6"><div class="empty"><div class="spinner"></div><p>加载中…</p></div></td></tr>';

  const query = new URLSearchParams({
    page: String(pageState.page),
    page_size: String(PAGE_SIZE),
  });
  if (pageState.action) query.set('action', pageState.action);
  if (pageState.keyword) query.set('keyword', pageState.keyword);
  if (pageState.start) query.set('start', pageState.start);
  if (pageState.end) query.set('end', pageState.end);

  try {
    const res = await api('/api/admin/audit-logs?' + query.toString());
    const data = (res && res.data) || {};
    const items = data.items || [];

    pageState.totalPages = data.total_pages || 1;
    $('audit-total').textContent = `共 ${data.total || 0} 条`;

    fillActionOptions(data.actions || []);

    if (!items.length) {
      body.innerHTML = '<tr><td colspan="6"><div class="empty"><i class="fa-solid fa-clipboard-list"></i><p>没有符合条件的日志</p></div></td></tr>';
      $('audit-pagination').innerHTML = '';
      return;
    }

    body.innerHTML = items.map(renderRow).join('');
    renderPagination($('audit-pagination'), pageState.page, pageState.totalPages, (p) => loadAudit(p));
  } catch (e) {
    body.innerHTML = `<tr><td colspan="6"><div class="empty"><i class="fa-solid fa-triangle-exclamation"></i><p>${util.escapeHtml(e.message || '加载失败')}</p></div></td></tr>`;
    Toast.error(e.message || '审核日志加载失败');
  }
}

/* ============================== 渲染 ============================== */
const ROLE_LABEL = { admin: '管理员', vip: 'VIP', user: '用户' };

function renderRow(item) {
  const time = formatTime(item.created_at);
  const role = ROLE_LABEL[item.actor_role] || '';
  const target = item.target_id
    ? `${util.escapeHtml(item.target_type || '')} #${util.escapeHtml(item.target_id)}`
    : '—';

  return `
    <tr>
      <td class="tiny">${time}</td>
      <td>
        <div>${util.escapeHtml(item.actor_name || '系统')}</div>
        ${role ? `<div class="tiny dim">${role}</div>` : ''}
      </td>
      <td><span class="badge badge--muted">${util.escapeHtml(item.action_label || item.action)}</span></td>
      <td class="tiny">${target}</td>
      <td class="small">${util.escapeHtml(item.detail || '')}</td>
      <td class="tiny dim">${util.escapeHtml(item.ip || '—')}</td>
    </tr>`;
}

function formatTime(iso) {
  if (!iso) return '—';
  // 后端给的是 ISO 字符串；直接 new Date 会按本地时区显示
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return util.escapeHtml(iso);
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

function fillActionOptions(actions) {
  const select = $('audit-action');
  if (!select) return;

  const current = select.value;
  const options = ['<option value="">全部动作</option>'].concat(
    actions.map((a) => `<option value="${util.escapeHtml(a.value)}">${util.escapeHtml(a.label)}（${a.count}）</option>`),
  );
  select.innerHTML = options.join('');
  if (current) select.value = current;
}

/* ============================== 交互 ============================== */
function applyFilters() {
  pageState.action = $('audit-action').value;
  pageState.keyword = $('audit-keyword').value.trim();
  pageState.start = $('audit-start').value;
  pageState.end = $('audit-end').value;

  if (pageState.start && pageState.end && pageState.start > pageState.end) {
    Toast.error('开始日期不能晚于结束日期');
    return;
  }
  loadAudit(1);
}

$('audit-search').addEventListener('click', applyFilters);
$('audit-refresh').addEventListener('click', () => loadAudit());

$('audit-keyword').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') applyFilters();
});

$('audit-action').addEventListener('change', applyFilters);

$('audit-reset').addEventListener('click', () => {
  $('audit-keyword').value = '';
  // 日期控件的显示文字跟随 change 事件更新，直接赋 value 不会触发，这里手动补一次
  ['audit-start', 'audit-end'].forEach((id) => {
    const el = $(id);
    el.value = '';
    el.dispatchEvent(new Event('change', { bubbles: true }));
  });
  $('audit-action').value = '';
  $('audit-action').dispatchEvent(new Event('change', { bubbles: true }));
  applyFilters();
});
