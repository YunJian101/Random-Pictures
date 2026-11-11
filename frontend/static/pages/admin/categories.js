/**
 * 管理后台 · 分类：列表、增删改
 */

import { $, state, api, Toast, Modal, util } from './core.js';

/* ============================== 分类 ============================== */
/** 确保分类列表已加载（图片管理的筛选、上传弹窗都依赖它） */
export async function ensureCategories() {
  if (state.categories.length) return state.categories;
  try {
    const res = await api('/api/admin/categories');
    state.categories = (res && res.data && res.data.categories) || [];
    fillCategorySelects();
  } catch (e) {
    console.warn('分类加载失败：', e.message);
  }
  return state.categories;
}

export function fillCategorySelects() {
  const options = state.categories.map((c) =>
    `<option value="${c.id}">${util.escapeHtml(c.name)}（${c.image_count}）</option>`).join('');

  const upload = $('upload-category');
  const edit = $('edit-image-category');
  const filter = $('img-category-filter');

  const prevUpload = upload.value;
  upload.innerHTML = options || '<option value="">暂无分类</option>';
  if (prevUpload) upload.value = prevUpload;

  edit.innerHTML = options || '<option value="">未分类</option>';

  const prevFilter = filter.value;
  filter.innerHTML = '<option value="">全部分类</option>' +
    state.categories.map((c) => `<option value="${util.escapeHtml(c.name)}">${util.escapeHtml(c.name)}</option>`).join('');
  filter.value = prevFilter || '';
}

export async function loadCategories() {
  const grid = $('cat-grid');
  grid.innerHTML = '<div class="empty" style="grid-column:1/-1"><div class="spinner"></div><p>加载中…</p></div>';
  try {
    const res = await api('/api/admin/categories');
    state.categories = (res && res.data && res.data.categories) || [];
    fillCategorySelects();

    if (!state.categories.length) {
      grid.innerHTML = '<div class="empty" style="grid-column:1/-1"><i class="fa-solid fa-folder-open"></i><p>还没有分类，先新建一个吧</p></div>';
      return;
    }

    grid.innerHTML = state.categories.map((c) => `
      <div class="cat-tile">
        <div class="cat-tile__head">
          <div style="min-width:0">
            <div class="cat-tile__name truncate">${util.escapeHtml(c.name)}</div>
            <div class="cat-tile__desc truncate">${util.escapeHtml(c.description || '暂无描述')}</div>
          </div>
          <span class="badge ${c.status === 'enabled' ? 'badge--success' : 'badge--muted'}">
            ${c.status === 'enabled' ? '启用' : '停用'}
          </span>
        </div>
        <div class="row--between tiny dim">
          <span><i class="fa-solid fa-images"></i> ${c.image_count} 张</span>
          <span>#${c.id}</span>
        </div>
        <div class="cat-tile__actions">
          <button class="btn btn--outline btn--sm" data-cat-edit="${c.id}"><i class="fa-solid fa-pen"></i>编辑</button>
          <button class="btn btn--danger btn--sm" data-cat-del="${c.id}"><i class="fa-solid fa-trash"></i>删除</button>
        </div>
      </div>`).join('');

    grid.querySelectorAll('[data-cat-edit]').forEach((btn) => {
      btn.addEventListener('click', () => openCategoryModal(Number(btn.dataset.catEdit)));
    });
    grid.querySelectorAll('[data-cat-del]').forEach((btn) => {
      btn.addEventListener('click', () => deleteCategory(Number(btn.dataset.catDel)));
    });
  } catch (e) {
    grid.innerHTML = `<div class="empty" style="grid-column:1/-1"><i class="fa-solid fa-triangle-exclamation"></i><p>${util.escapeHtml(e.message)}</p></div>`;
  }
}

export function openCategoryModal(id) {
  const editing = id != null;
  const cat = editing ? state.categories.find((c) => c.id === id) : null;
  $('category-id').value = editing ? String(id) : '';
  $('category-name').value = cat ? cat.name : '';
  $('category-desc').value = cat ? (cat.description || '') : '';
  $('category-status').value = cat ? cat.status : 'enabled';
  $('category-modal-title').innerHTML = `<i class="fa-solid fa-layer-group"></i>${editing ? '编辑分类' : '新建分类'}`;
  Modal.open('modal-category');
}

$('cat-add').addEventListener('click', () => openCategoryModal(null));

$('category-save').addEventListener('click', async () => {
  const id = $('category-id').value;
  const name = $('category-name').value.trim();
  if (!name) { Toast.warn('请填写分类名称'); return; }

  const payload = {
    name,
    description: $('category-desc').value.trim(),
    status: $('category-status').value,
  };
  const btn = $('category-save');
  btn.disabled = true;
  try {
    if (id) await api(`/api/admin/categories/${id}`, { method: 'PUT', body: payload });
    else await api('/api/admin/categories', { method: 'POST', body: payload });
    Toast.success(id ? '分类已更新' : '分类已创建');
    Modal.close('modal-category');
    loadCategories();
  } catch (e) {
    Toast.error(e.message || '保存失败');
  } finally {
    btn.disabled = false;
  }
});

export async function deleteCategory(id) {
  const cat = state.categories.find((c) => c.id === id);
  const ok = await util.confirm(
    '删除分类',
    `确定删除「${cat ? cat.name : id}」吗？该分类下的图片会变成未分类，不会被删除。`,
    '删除'
  );
  if (!ok) return;
  try {
    await api(`/api/admin/categories/${id}`, { method: 'DELETE' });
    Toast.success('分类已删除');
    loadCategories();
  } catch (e) {
    Toast.error(e.message || '删除失败');
  }
}

