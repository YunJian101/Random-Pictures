/**
 * 管理后台 · 用户：列表、编辑、封禁、删除
 */

import { $, state, api, Toast, Modal, util } from './core.js';

/* ============================== 用户 ============================== */
export async function loadUsers() {
  const body = $('user-table-body');
  body.innerHTML = '<tr><td colspan="6"><div class="empty"><div class="spinner"></div><p>加载中…</p></div></td></tr>';
  try {
    const res = await api('/api/users');
    state.users = (res && res.data && res.data.users) || [];
    renderUsers();
  } catch (e) {
    body.innerHTML = `<tr><td colspan="6"><div class="empty"><i class="fa-solid fa-triangle-exclamation"></i><p>${util.escapeHtml(e.message)}</p></div></td></tr>`;
  }
}

export function renderUsers() {
  const body = $('user-table-body');
  const keyword = $('user-search').value.trim().toLowerCase();
  const status = $('user-status-filter').value;
  const role = $('user-role-filter').value;

  const list = state.users.filter((u) => {
    const hay = `${u.username} ${u.email}`.toLowerCase();
    if (keyword && !hay.includes(keyword)) return false;
    if (status === 'banned' && !u.is_banned) return false;
    if (status === 'active' && u.is_banned) return false;
    if (role && u.role !== role) return false;
    return true;
  });

  $('user-total').textContent = `共 ${list.length} / ${state.users.length} 个用户`;

  if (!list.length) {
    body.innerHTML = '<tr><td colspan="6"><div class="empty"><i class="fa-solid fa-users"></i><p>没有符合条件的用户</p></div></td></tr>';
    return;
  }

  const ROLE = { admin: ['管理员', 'badge--primary'], vip: ['VIP', 'badge--accent'], user: ['普通用户', 'badge--muted'] };

  body.innerHTML = list.map((u) => {
    const [roleLabel, roleCls] = ROLE[u.role] || [u.role, 'badge--muted'];
    return `<tr>
      <td>
        <div class="row gap-2">
          <span class="sidebar__avatar" style="width:28px;height:28px;font-size:11px;flex:0 0 28px">${util.escapeHtml((u.username || '?').slice(0, 1).toUpperCase())}</span>
          <span class="cell-strong">${util.escapeHtml(u.username)}</span>
        </div>
      </td>
      <td class="truncate" title="${util.escapeHtml(u.email)}">${util.escapeHtml(u.email)}</td>
      <td><span class="badge ${roleCls}">${roleLabel}</span></td>
      <td><span class="badge ${u.is_banned ? 'badge--danger' : 'badge--success'}">${u.is_banned ? '已封禁' : '正常'}</span></td>
      <td class="nowrap">${util.formatDate(u.created_at, false)}</td>
      <td>
        <div class="cell-actions">
          <button class="icon-btn" data-user-edit="${u.id}" title="编辑"><i class="fa-solid fa-pen"></i></button>
          ${u.is_banned
            ? `<button class="icon-btn" data-user-unban="${u.id}" title="解封"><i class="fa-solid fa-lock-open"></i></button>`
            : `<button class="icon-btn" data-user-ban="${u.id}" title="封禁"><i class="fa-solid fa-ban"></i></button>`}
          <button class="icon-btn" data-user-del="${u.id}" title="删除"><i class="fa-solid fa-trash"></i></button>
        </div>
      </td>
    </tr>`;
  }).join('');

  body.querySelectorAll('[data-user-edit]').forEach((btn) => {
    btn.addEventListener('click', () => openUserModal(Number(btn.dataset.userEdit)));
  });
  body.querySelectorAll('[data-user-ban]').forEach((btn) => {
    btn.addEventListener('click', () => openBanModal(Number(btn.dataset.userBan)));
  });
  body.querySelectorAll('[data-user-unban]').forEach((btn) => {
    btn.addEventListener('click', () => unbanUser(Number(btn.dataset.userUnban)));
  });
  body.querySelectorAll('[data-user-del]').forEach((btn) => {
    btn.addEventListener('click', () => deleteUser(Number(btn.dataset.userDel)));
  });
}

$('user-search').addEventListener('input', util.debounce(renderUsers, 200));
$('user-status-filter').addEventListener('change', renderUsers);
$('user-role-filter').addEventListener('change', renderUsers);

export function openUserModal(id) {
  const editing = id != null;
  const user = editing ? state.users.find((u) => u.id === id) : null;

  $('user-id').value = editing ? String(id) : '';
  $('user-username').value = user ? user.username : '';
  $('user-email').value = user ? (user.email === '-' ? '' : user.email) : '';
  $('user-password').value = '';

  // 新建：密码必填、不选角色（默认普通用户）；编辑：密码留空即不修改，可改角色
  $('user-password-field').classList.remove('hidden');
  $('user-password-label').textContent = editing ? '重置密码（可选）' : '初始密码';
  $('user-password-hint').textContent = editing
    ? '留空表示不修改密码；填写后该用户所有登录会话会失效。'
    : '';
  $('user-role-field').classList.toggle('hidden', !editing);
  $('user-role').value = user && user.role ? user.role : 'user';

  $('user-modal-title').innerHTML = `<i class="fa-solid fa-user-plus"></i>${editing ? '编辑用户' : '新建用户'}`;
  Modal.open('modal-user');
}

$('user-add').addEventListener('click', () => openUserModal(null));

$('user-save').addEventListener('click', async () => {
  const id = $('user-id').value;
  const username = $('user-username').value.trim();
  const email = $('user-email').value.trim();
  const password = $('user-password').value;
  const role = $('user-role').value;

  if (!/^[a-zA-Z0-9_]{3,16}$/.test(username)) { Toast.warn('用户名需为 3-16 位字母、数字或下划线'); return; }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { Toast.warn('请输入有效的邮箱'); return; }
  if (!id && password.length < 6) { Toast.warn('初始密码至少 6 位'); return; }
  if (id && password && password.length < 6) { Toast.warn('重置密码至少 6 位'); return; }

  const btn = $('user-save');
  btn.disabled = true;
  try {
    if (id) {
      // 空密码交给后端当作"不修改"
      await api(`/api/users/${id}`, { method: 'PUT', body: { username, email, password, role } });
      Toast.success('用户已更新');
    } else {
      await api('/api/users', { method: 'POST', body: { username, email, password } });
      Toast.success('用户已创建');
    }
    Modal.close('modal-user');
    loadUsers();
  } catch (e) {
    Toast.error(e.message || '保存失败');
  } finally {
    btn.disabled = false;
  }
});

export function openBanModal(id) {
  const user = state.users.find((u) => u.id === id);
  $('ban-user-id').value = String(id);
  $('ban-user-name').textContent = user ? `即将封禁：${user.username}（${user.email}）` : '';
  $('ban-reason').value = '';
  Modal.open('modal-ban');
}

$('ban-submit').addEventListener('click', async () => {
  const id = $('ban-user-id').value;
  const btn = $('ban-submit');
  btn.disabled = true;
  try {
    await api(`/api/users/${id}/ban`, { method: 'PUT', body: { reason: $('ban-reason').value.trim() } });
    Toast.success('已封禁该用户');
    Modal.close('modal-ban');
    loadUsers();
  } catch (e) {
    Toast.error(e.message || '封禁失败');
  } finally {
    btn.disabled = false;
  }
});

export async function unbanUser(id) {
  try {
    await api(`/api/users/${id}/unban`, { method: 'PUT' });
    Toast.success('已解封');
    loadUsers();
  } catch (e) {
    Toast.error(e.message || '解封失败');
  }
}

export async function deleteUser(id) {
  const user = state.users.find((u) => u.id === id);
  const ok = await util.confirm('删除用户', `确定删除用户「${user ? user.username : id}」吗？其反馈也会一并删除。`, '删除');
  if (!ok) return;
  try {
    await api(`/api/users/${id}`, { method: 'DELETE' });
    Toast.success('用户已删除');
    loadUsers();
  } catch (e) {
    Toast.error(e.message || '删除失败');
  }
}

