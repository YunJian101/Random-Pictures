/**
 * 管理后台 · 反馈：列表、对话线程、删除
 */

import { $, state, STATUS, api, Toast, util, renderThread } from './core.js';

/* ============================== 反馈 ============================== */
export async function loadFeedbacks() {
  const host = $('fb-list');
  host.innerHTML = '<div class="empty"><div class="spinner"></div><p>加载中…</p></div>';
  try {
    const res = await api('/api/admin/feedbacks');
    state.feedbacks = (res && res.data && res.data.feedbacks) || [];

    const pending = state.feedbacks.filter((f) => f.status === 'pending').length;
    const badge = $('nav-fb-badge');
    badge.textContent = pending;
    badge.classList.toggle('hidden', pending === 0);

    renderFeedbacks();
  } catch (e) {
    host.innerHTML = `<div class="empty"><i class="fa-solid fa-triangle-exclamation"></i><p>${util.escapeHtml(e.message)}</p></div>`;
  }
}

export function renderFeedbacks() {
  const host = $('fb-list');
  const filter = $('fb-status-filter').value;
  const list = filter ? state.feedbacks.filter((f) => f.status === filter) : state.feedbacks;

  if (!list.length) {
    host.innerHTML = '<div class="empty"><i class="fa-regular fa-comment-dots"></i><p>暂无反馈</p></div>';
    return;
  }

  host.innerHTML = list.map((fb) => {
    const st = STATUS[fb.status] || { label: fb.status, cls: 'badge--muted' };
    const options = Object.entries(STATUS).map(([value, meta]) =>
      `<option value="${value}" ${value === fb.status ? 'selected' : ''}>${meta.label}</option>`).join('');
    const messages = fb.messages || [];
    // 老数据没有对话记录时退回显示原始内容
    const body = messages.length
      ? renderThread(fb, { scroll: messages.length > 3 })
      : `<p style="margin-top:10px;font-size:13.5px;line-height:1.7;white-space:pre-wrap;color:var(--text-2)">${util.escapeHtml(fb.content)}</p>`;

    // 关闭来源：区分用户自行关闭 / 管理员关闭
    const closedBadge = (fb.status === 'closed' && fb.closed_by)
      ? `<span class="badge badge--muted">${fb.closed_by === 'user' ? '用户关闭' : '管理员关闭'}</span>`
      : '';

    // 只有还活着的反馈才能继续对话；已解决/已关闭只能看
    let footer = '';
    if (fb.status === 'pending' || fb.status === 'processing') {
      footer = `
        <form class="fb-reply-form" data-feedback="${fb.id}">
          <div class="input-group grow">
            <i class="fa-solid fa-reply"></i>
            <input class="input input--sm" maxlength="900" placeholder="回复用户…（发送后状态变为处理中）">
          </div>
          <button class="btn btn--primary btn--sm" type="submit"><i class="fa-solid fa-paper-plane"></i>发送</button>
        </form>`;
    } else {
      footer = `<p class="fb-hint"><i class="fa-solid fa-lock"></i>该反馈${st.label}，已归档不可回复；如需继续沟通请把状态改回「处理中」。</p>`;
    }

    return `<article class="card card--pad" style="margin-bottom:12px">
      <div class="row--between wrap gap-3">
        <div class="row gap-2 wrap">
          <span class="badge ${st.cls}">${st.label}</span>
          ${closedBadge}
          <span class="strong">${util.escapeHtml(fb.username || '未知用户')}</span>
          <span class="tiny dim">#${fb.id} · ${util.formatDate(fb.created_at)}</span>
          ${messages.length > 1 ? `<span class="tiny dim">· ${messages.length} 条对话</span>` : ''}
        </div>
        <div class="row gap-2">
          <select class="select select--sm" data-fb-status="${fb.id}" style="width:110px">${options}</select>
          <button class="btn btn--danger btn--sm" data-fb-del="${fb.id}"><i class="fa-solid fa-trash"></i></button>
        </div>
      </div>
      ${body}
      ${footer}
    </article>`;
  }).join('');

  host.querySelectorAll('[data-fb-status]').forEach((sel) => {
    sel.addEventListener('change', async () => {
      try {
        await api(`/api/admin/feedbacks/${sel.dataset.fbStatus}/status?status=${sel.value}`, { method: 'PUT' });
        Toast.success('状态已更新');
        loadFeedbacks();
      } catch (e) {
        Toast.error(e.message || '更新失败');
      }
    });
  });
  host.querySelectorAll('[data-fb-del]').forEach((btn) => {
    btn.addEventListener('click', () => deleteFeedback(Number(btn.dataset.fbDel)));
  });
  host.querySelectorAll('.fb-reply-form').forEach((form) => {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const input = form.querySelector('input');
      const content = input.value.trim();
      if (content.length < 2) { Toast.warn('请至少输入 2 个字'); input.focus(); return; }

      const btn = form.querySelector('button');
      btn.disabled = true;
      try {
        await api(`/api/admin/feedbacks/${form.dataset.feedback}/messages`, {
          method: 'POST',
          body: { content },
        });
        Toast.success('已回复，状态更新为处理中');
        loadFeedbacks();
      } catch (err) {
        Toast.error(err.message || '回复失败');
        btn.disabled = false;
      }
    });
  });
}

$('fb-status-filter').addEventListener('change', renderFeedbacks);

export async function deleteFeedback(id) {
  const ok = await util.confirm('删除反馈', '确定删除这条反馈吗？删除后用户也无法再看到。', '删除');
  if (!ok) return;
  try {
    await api(`/api/admin/feedbacks/${id}`, { method: 'DELETE' });
    Toast.success('已删除');
    loadFeedbacks();
  } catch (e) {
    Toast.error(e.message || '删除失败');
  }
}

