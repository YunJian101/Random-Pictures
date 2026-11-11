/**
 * 管理后台 · 图片：列表、筛选、批量操作、上传
 */

import { $, state, renderPagination, api, Toast, Modal, util } from './core.js';
import { ensureCategories } from './categories.js';

/* ============================== 图片 ============================== */
export async function loadImages(page) {
  if (page) state.images.page = page;

  // 首次进「图片管理」时分类还没加载过，筛选下拉会是空的
  await ensureCategories();

  const body = $('img-table-body');
  body.innerHTML = '<tr><td colspan="9"><div class="empty"><div class="spinner"></div><p>加载中…</p></div></td></tr>';

  const params = new URLSearchParams({
    page: String(state.images.page),
    category: state.images.category || '',
    q: state.images.keyword || '',
    sort: state.images.sort || 'created_desc',
  });

  try {
    const res = await api(`/api/images?${params.toString()}`);
    const items = (res && res.images) || [];
    state.images.items = items;
    state.images.totalPages = Math.max(1, (res && res.total_pages) || 1);
    state.images.total = (res && res.total_images) || 0;
    state.images.page = (res && res.current_page) || 1;
    state.images.selected.clear();

    if (!items.length) {
      body.innerHTML = '<tr><td colspan="9"><div class="empty"><i class="fa-regular fa-images"></i><p>没有符合条件的图片</p></div></td></tr>';
    } else {
      body.innerHTML = items.map((img) => `
        <tr>
          <td><input type="checkbox" class="checkbox" data-img-check="${img.id}"></td>
          <td><div class="thumb"><img src="/thumb?path=${encodeURIComponent(img.path)}&w=160" alt="" loading="lazy"></div></td>
          <td class="cell-strong" title="${util.escapeHtml(img.path)}">${util.escapeHtml(img.name)}</td>
          <td><span class="badge badge--muted">${util.escapeHtml(img.category)}</span></td>
          <td>${util.escapeHtml(img.size || util.formatBytes(img.size_bytes))}</td>
          <td class="nowrap">${util.escapeHtml(img.resolution || '—')}</td>
          <td class="nowrap">${(img.views || 0).toLocaleString('zh-CN')}</td>
          <td class="nowrap">${util.formatDate(img.modified_time)}</td>
          <td>
            <div class="cell-actions">
              <button class="icon-btn" data-img-edit="${img.id}" title="编辑"><i class="fa-solid fa-pen"></i></button>
              <button class="icon-btn" data-img-del="${img.id}" title="删除"><i class="fa-solid fa-trash"></i></button>
            </div>
          </td>
        </tr>`).join('');

      body.querySelectorAll('[data-img-check]').forEach((box) => {
        box.addEventListener('change', () => {
          const id = Number(box.dataset.imgCheck);
          if (box.checked) state.images.selected.add(id);
          else state.images.selected.delete(id);
          syncImageSelection();
        });
      });
      body.querySelectorAll('[data-img-edit]').forEach((btn) => {
        btn.addEventListener('click', () => openImageModal(Number(btn.dataset.imgEdit)));
      });
      body.querySelectorAll('[data-img-del]').forEach((btn) => {
        btn.addEventListener('click', () => deleteImage(Number(btn.dataset.imgDel)));
      });
    }

    const start = (state.images.page - 1) * 20 + 1;
    const end = start + items.length - 1;
    $('img-page-info').textContent = items.length
      ? `显示 ${start}–${end} 条，共 ${state.images.total} 条`
      : `共 ${state.images.total} 条`;
    renderPagination($('img-pagination'), state.images.page, state.images.totalPages, (p) => loadImages(p));
    syncImageSelection();
  } catch (e) {
    body.innerHTML = `<tr><td colspan="9"><div class="empty"><i class="fa-solid fa-triangle-exclamation"></i><p>${util.escapeHtml(e.message)}</p></div></td></tr>`;
  }
}

export function syncImageSelection() {
  const count = state.images.selected.size;
  $('img-sel-count').textContent = count;
  $('img-sel-bar').classList.toggle('hidden', count === 0);
  ['img-download', 'img-delete', 'img-move'].forEach((id) => { $(id).disabled = count === 0; });

  const checkAll = $('img-check-all');
  const boxes = [...document.querySelectorAll('[data-img-check]')];
  checkAll.checked = boxes.length > 0 && count === boxes.length;
  checkAll.indeterminate = count > 0 && count < boxes.length;
}

$('img-check-all').addEventListener('change', (e) => {
  document.querySelectorAll('[data-img-check]').forEach((box) => {
    box.checked = e.target.checked;
    const id = Number(box.dataset.imgCheck);
    if (e.target.checked) state.images.selected.add(id);
    else state.images.selected.delete(id);
  });
  syncImageSelection();
});

$('img-select-all').addEventListener('click', () => {
  $('img-check-all').checked = true;
  $('img-check-all').dispatchEvent(new Event('change'));
});
$('img-select-none').addEventListener('click', () => {
  $('img-check-all').checked = false;
  $('img-check-all').dispatchEvent(new Event('change'));
});

$('img-category-filter').addEventListener('change', (e) => {
  state.images.category = e.target.value;
  loadImages(1);
});
$('img-sort').addEventListener('change', (e) => {
  state.images.sort = e.target.value;
  loadImages(1);
});
$('img-search').addEventListener('input', util.debounce((e) => {
  state.images.keyword = e.target.value.trim();
  loadImages(1);
}, 380));

$('img-move').addEventListener('click', () => {
  if (!state.categories.length) { Toast.warn('请先创建分类'); return; }
  const count = state.images.selected.size;
  $('move-hint').textContent = `已选择 ${count} 张图片，选择要移动到的分类：`;
  $('move-category').innerHTML = state.categories.map((c) =>
    `<option value="${c.id}">${util.escapeHtml(c.name)}（${c.image_count} 张）</option>`).join('');
  Modal.open('modal-move');
});

$('move-submit').addEventListener('click', async () => {
  const categoryId = Number($('move-category').value);
  if (!categoryId) { Toast.warn('请选择目标分类'); return; }
  const btn = $('move-submit');
  btn.disabled = true;
  try {
    await batchAction('move', categoryId);
    Modal.close('modal-move');
  } finally {
    btn.disabled = false;
  }
});

$('img-download').addEventListener('click', () => batchAction('download'));
$('img-delete').addEventListener('click', async () => {
  const ok = await util.confirm('删除图片', `确定删除选中的 ${state.images.selected.size} 张图片吗？此操作不可恢复。`, '删除');
  if (ok) await batchAction('delete');
});

export async function batchAction(action, categoryId) {
  const ids = [...state.images.selected];
  try {
    if (action === 'download') {
      const res = await fetch('/api/admin/batch-action', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, image_ids: ids }),
      });
      if (!res.ok) throw new Error(`下载失败（HTTP ${res.status}）`);
      const blob = await res.blob();
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = `images-${Date.now()}.zip`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(link.href), 5000);
      Toast.success('已开始下载');
      return;
    }

    await api('/api/admin/batch-action', {
      method: 'POST',
      body: { action, image_ids: ids, category_id: categoryId || null },
    });
    Toast.success(action === 'move' ? '已移动' : '已删除');
    loadImages();
  } catch (e) {
    Toast.error(e.message || '批量操作失败');
  }
}

export async function deleteImage(id) {
  const ok = await util.confirm('删除图片', '确定删除这张图片吗？此操作不可恢复。', '删除');
  if (!ok) return;
  try {
    await api(`/api/image/${id}`, { method: 'DELETE' });
    Toast.success('已删除');
    loadImages();
  } catch (e) {
    Toast.error(e.message || '删除失败');
  }
}

export function openImageModal(id) {
  const img = state.images.items.find((i) => i.id === id);
  if (!img) return;
  $('edit-image-id').value = String(id);
  $('edit-image-name').value = img.name;
  const cat = state.categories.find((c) => c.name === img.category);
  $('edit-image-category').value = cat ? String(cat.id) : '';
  Modal.open('modal-image');
}

$('edit-image-save').addEventListener('click', async () => {
  const id = $('edit-image-id').value;
  const filename = $('edit-image-name').value.trim();
  const categoryId = Number($('edit-image-category').value);
  if (!filename) { Toast.warn('请填写文件名'); return; }
  if (!categoryId) { Toast.warn('请选择分类'); return; }

  const btn = $('edit-image-save');
  btn.disabled = true;
  try {
    await api(`/api/image/${id}`, { method: 'PUT', body: { filename, category_id: categoryId } });
    Toast.success('已保存');
    Modal.close('modal-image');
    loadImages();
  } catch (e) {
    Toast.error(e.message || '保存失败');
  } finally {
    btn.disabled = false;
  }
});

/* -------------------------- 上传 -------------------------- */
export let uploadFiles = [];

document.querySelectorAll('[data-open-upload]').forEach((btn) => {
  btn.addEventListener('click', async () => {
    await ensureCategories();
    if (!state.categories.length) {
      Toast.warn('请先创建至少一个分类');
      return;
    }
    uploadFiles = [];
    renderUploadList();
    Modal.open('modal-upload');
  });
});

$('dropzone').addEventListener('click', () => $('upload-input').click());

['dragenter', 'dragover'].forEach((evt) => {
  $('dropzone').addEventListener(evt, (e) => {
    e.preventDefault();
    $('dropzone').classList.add('is-over');
  });
});
['dragleave', 'drop'].forEach((evt) => {
  $('dropzone').addEventListener(evt, (e) => {
    e.preventDefault();
    $('dropzone').classList.remove('is-over');
  });
});
$('dropzone').addEventListener('drop', (e) => addFiles(e.dataTransfer.files));
$('upload-input').addEventListener('change', (e) => addFiles(e.target.files));

export const ALLOWED = ['.jpg', '.jpeg', '.png', '.gif', '.webp'];

export function addFiles(fileList) {
  const rejected = [];
  [...fileList].forEach((file) => {
    const ext = file.name.slice(file.name.lastIndexOf('.')).toLowerCase();
    if (!ALLOWED.includes(ext)) { rejected.push(`${file.name}（格式不支持）`); return; }
    if (uploadFiles.some((f) => f.name === file.name && f.size === file.size)) return;
    uploadFiles.push(file);
  });
  if (uploadFiles.length > 10) {
    uploadFiles = uploadFiles.slice(0, 10);
    Toast.warn('单次最多上传 10 张，多余文件已忽略');
  }
  if (rejected.length) Toast.warn(rejected.join('，'));
  renderUploadList();
}

export function renderUploadList() {
  const list = $('upload-list');
  if (!uploadFiles.length) {
    list.innerHTML = '';
    $('upload-count').textContent = '未选择文件';
    $('upload-submit').disabled = true;
    return;
  }
  list.innerHTML = uploadFiles.map((file, i) => `
    <div class="upload-item">
      <i class="fa-solid fa-image" style="color:var(--primary)"></i>
      <span class="upload-item__name" title="${util.escapeHtml(file.name)}">${util.escapeHtml(file.name)}</span>
      <span class="upload-item__size">${util.formatBytes(file.size)}</span>
      <button class="icon-btn" style="width:24px;height:24px" data-remove="${i}" title="移除">
        <i class="fa-solid fa-xmark" style="font-size:11px"></i>
      </button>
    </div>`).join('');
  list.querySelectorAll('[data-remove]').forEach((btn) => {
    btn.addEventListener('click', () => {
      uploadFiles.splice(Number(btn.dataset.remove), 1);
      renderUploadList();
    });
  });
  $('upload-count').textContent = `已选择 ${uploadFiles.length} 个文件 · ${util.formatBytes(uploadFiles.reduce((s, f) => s + f.size, 0))}`;
  $('upload-submit').disabled = false;
}

$('upload-clear').addEventListener('click', () => {
  uploadFiles = [];
  $('upload-input').value = '';
  renderUploadList();
});

/** 上传结果弹窗：一共上传几张 / 成功几张 / 失败几张，失败项目逐条列文件名 + 原因 */
function showUploadResult(total, payload) {
  const okCount = payload.uploaded_count || 0;
  const dupCount = payload.duplicate_count || 0;
  const failed = payload.failed_files || [];
  const failCount = payload.failed_count != null ? payload.failed_count : failed.length;

  $('upload-result-title').textContent =
    `一共上传 ${total} 张，成功 ${okCount} 张，失败 ${failCount} 张`;
  $('upload-result-extra').textContent = dupCount
    ? `另有 ${dupCount} 张因重复被跳过`
    : (failCount ? '' : '全部上传成功');

  const block = $('upload-result-fail-block');
  const list = $('upload-result-failures');
  if (failed.length) {
    list.innerHTML = failed.map((f, i) => `
      <li style="margin-bottom:8px">
        <b>${i + 1}. ${util.escapeHtml(f.filename)}</b>
        <div class="tiny dim">${util.escapeHtml(f.error || '未知原因')}</div>
      </li>`).join('');
    block.classList.remove('hidden');
  } else {
    list.innerHTML = '';
    block.classList.add('hidden');
  }
  Modal.open('modal-upload-result');
}

$('upload-submit').addEventListener('click', async () => {
  if (!uploadFiles.length) return;
  const categoryId = $('upload-category').value;
  const cat = state.categories.find((c) => String(c.id) === categoryId);
  if (!cat) { Toast.warn('请选择目标分类'); return; }

  const form = new FormData();
  uploadFiles.forEach((file) => form.append('files', file));
  form.append('category', cat.name);
  const total = uploadFiles.length;

  const btn = $('upload-submit');
  btn.disabled = true;
  btn.innerHTML = '<div class="spinner"></div>上传中…';

  // 收尾：弹结果 → 清空选择 → 关上传弹窗 → 刷新列表
  const finish = (payload) => {
    showUploadResult(total, payload || {});
    uploadFiles = [];
    $('upload-input').value = '';
    renderUploadList();
    Modal.close('modal-upload');
    state.categories = [];   // 图片数量变了，下次重新拉分类
    loadImages(1);
  };

  try {
    const res = await api('/api/admin/upload', { method: 'POST', body: form });
    finish((res && res.data) || {});
  } catch (e) {
    // 全部失败时后端返回 HTTP 400，明细在 payload.data.failed_files 里，
    // 只报「上传失败」等于让用户猜，所以照样把结果弹出来
    const payload = (e && e.payload && e.payload.data) || null;
    if (payload && (payload.failed_files || payload.failed_count != null)) {
      finish(payload);
    } else {
      Toast.error(e.message || '上传失败');
    }
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<i class="fa-solid fa-upload"></i>开始上传';
  }
});

