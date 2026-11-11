/**
 * 首页：演示图、分类浏览、数据概览、反馈入口
 *
 * 从页面内联脚本抽出，逻辑未改动；HTML 只保留结构。
 */
document.addEventListener('DOMContentLoaded', function () {
  'use strict';

  const { api, Toast, Modal, util, countUp } = window.RP;
  const BASE = util.baseUrl();
  const $ = (id) => document.getElementById(id);

  /* ------------------------------ 状态 ------------------------------ */
  const state = {
    categories: [],          // 当前页分类
    allCategories: [],       // 全部分类（用于下拉/文档/统计）
    page: 1,
    totalPages: 1,
    totalCategories: 0,
    imagesLoaded: false,
    category: '',
    categoryPage: 1,
    categoryTotalPages: 1,
    categoryTotalImages: 0,
    currentBlobUrl: null,
    currentImageUrl: '',
  };

  /* ------------------------------ 模块切换 ------------------------------ */
  const MODULES = ['hero', 'demo', 'docs', 'categories', 'category-images', 'overview', 'feedback'];

  function showModule(id) {
    if (!MODULES.includes(id)) return;
    MODULES.forEach((m) => $(m) && $(m).classList.add('hidden'));
    const target = $(id);
    if (target) {
      target.classList.remove('hidden');
      target.classList.add('fade-in');
      setTimeout(() => target.classList.remove('fade-in'), 400);
    }

    document.querySelectorAll('.nav__link').forEach((btn) => {
      const match = btn.dataset.module === id || (id === 'category-images' && btn.dataset.module === 'categories');
      btn.classList.toggle('is-active', match);
    });

    if (id === 'demo') loadRandomImage();
    if (id === 'categories') loadCategoryImages();
    if (id === 'overview') renderOverview();

    window.scrollTo({ top: 0, behavior: 'smooth' });
  }
  window.showModule = showModule;

  document.querySelectorAll('[data-module]').forEach((btn) => {
    btn.addEventListener('click', () => showModule(btn.dataset.module));
  });

  $('back-to-categories').addEventListener('click', () => showModule('categories'));
  $('category-random-btn').addEventListener('click', () => {
    window.open(`${BASE}/random?type=${encodeURIComponent(state.category)}`, '_blank', 'noopener');
  });
  $('changelog-link').addEventListener('click', () => {
    showModule('docs');
    switchTab('changelog');
    setTimeout(() => $('docs').scrollIntoView({ behavior: 'smooth', block: 'start' }), 120);
  });

  /* ------------------------------ 站点信息 ------------------------------ */
  async function loadSiteInfo() {
    try {
      const res = await api('/api/system/info');
      const d = (res && res.data) || {};
      if (d.site_name) {
        $('site-name').textContent = d.site_name;
        document.title = `${d.site_name} - 随机图 API`;
      }
      if (d.favicon_url) $('favicon').href = d.favicon_url;
      if (d.icp_beian_code && d.show_beian_info === 'true') {
        const link = $('beian-link');
        link.textContent = d.icp_beian_code;
        link.href = d.icp_beian_url || 'https://beian.miit.gov.cn';
        $('beian-wrap').classList.remove('hidden');
      }
    } catch (e) {
      console.warn('站点信息加载失败：', e.message);
    }

    try {
      const res = await api('/api/system/version');
      const version = res && res.data && res.data.version;
      if (version) $('current-version').textContent = 'v' + version;
    } catch (e) {
      // 版本接口不可用时保持占位，不阻塞页面
      $('current-version').textContent = 'v—';
    }
  }

  /* ------------------------------ 登录状态 ------------------------------ */
  async function loadAuthState() {
    const btn = $('auth-btn');
    const text = $('auth-text');
    const icon = $('auth-icon');
    const user = await window.RP.Session.verify();
    window.RP.Session.setLocal(user);
    const isAdmin = Boolean(user && user.role === 'admin');
    // 仅管理员可见的入口（接口文档等）
    document.querySelectorAll('[data-admin-only]').forEach((el) => {
      el.classList.toggle('hidden', !isAdmin);
    });

    if (user) {
      text.textContent = user.role === 'admin' ? `${user.username} · 管理` : user.username;
      btn.href = user.role === 'admin' ? '/admin-panel' : '/user-panel';
      btn.classList.add('is-user');
      icon.className = 'fa-solid fa-user-check';
    } else {
      text.textContent = '登录';
      btn.href = '/login';
      btn.classList.remove('is-user');
      icon.className = 'fa-solid fa-user';
    }
  }

  /* ------------------------------ 分类数据 ------------------------------ */
  async function fetchAllCategories() {
    const all = [];
    let page = 1;
    let total = 1;
    do {
      const res = await api(`/api/categories?page=${page}`);
      if (res && Array.isArray(res.category_list)) all.push(...res.category_list);
      total = (res && res.total_pages) || 1;
      page += 1;
    } while (page <= total && page <= 50);
    return all;
  }

  async function loadCategories(page = 1) {
    try {
      const res = await api(`/api/categories?page=${page}`);
      const list = (res && res.category_list) || [];
      state.page = (res && res.current_page) || 1;
      state.totalPages = Math.max(1, (res && res.total_pages) || 1);
      state.totalCategories = (res && res.total_categories) || list.length;
      state.categories = list.map((c) => ({ name: c.name, count: c.image_count || 0 }));

      renderCategoryCards();
      updateCategoryPagination();
      $('categories-total').textContent = `${state.totalCategories} 个分类`;

      // 下拉框 & 文档 & 统计都需要全量分类
      state.allCategories = await fetchAllCategories();
      populateSelect();
      renderDocCategories();
      updateDocUrls();
      renderOverview();
      updateCategoryInfoText();

      state.imagesLoaded = false;
      if (!$('categories').classList.contains('hidden')) loadCategoryImages();
    } catch (e) {
      $('categories-grid').innerHTML = `<div class="empty" style="grid-column:1/-1">
        <i class="fa-solid fa-plug-circle-xmark"></i><p>分类加载失败：${util.escapeHtml(e.message)}</p></div>`;
    }
  }

  function renderCategoryCards() {
    const grid = $('categories-grid');
    if (!state.categories.length) {
      grid.innerHTML = `<div class="empty" style="grid-column:1/-1">
        <i class="fa-solid fa-folder-open"></i><p>还没有任何分类</p></div>`;
      return;
    }
    grid.innerHTML = state.categories.map((cat) => `
      <article class="card card--lift cat-card card--glow hairline-top">
        <div class="cat-card__media">
          <img alt="${util.escapeHtml(cat.name)}" loading="lazy"
               data-src="${BASE}/random?type=${encodeURIComponent(cat.name)}&w=320"
               src="data:image/svg+xml;charset=utf-8,%3Csvg xmlns='http://www.w3.org/2000/svg'/%3E">
          <span class="cat-card__count">${cat.count} 张</span>
        </div>
        <div class="cat-card__body">
          <div class="row--between">
            <h3 class="cat-card__name">${util.escapeHtml(cat.name)}</h3>
          </div>
          <div class="cat-card__actions">
            <button class="btn btn--outline btn--sm" data-category="${util.escapeHtml(cat.name)}">
              <i class="fa-solid fa-images"></i>查看
            </button>
            <button class="btn btn--soft btn--sm" data-category-random="${util.escapeHtml(cat.name)}">
              <i class="fa-solid fa-shuffle"></i>随机
            </button>
          </div>
        </div>
      </article>`).join('');

    grid.querySelectorAll('[data-category]').forEach((btn) => {
      btn.addEventListener('click', () => openCategory(btn.dataset.category));
    });
    grid.querySelectorAll('[data-category-random]').forEach((btn) => {
      btn.addEventListener('click', () => {
        window.open(`${BASE}/random?type=${encodeURIComponent(btn.dataset.categoryRandom)}`, '_blank', 'noopener');
      });
    });
  }

  function loadCategoryImages() {
    if (state.imagesLoaded) return;
    const imgs = document.querySelectorAll('.cat-card__media img[data-src]');
    imgs.forEach((img) => {
      img.src = img.dataset.src;
      img.removeAttribute('data-src');
      img.addEventListener('error', () => {
        img.replaceWith(Object.assign(document.createElement('div'), {
          className: 'empty',
          style: 'height:100%;padding:0',
          innerHTML: '<i class="fa-solid fa-image-slash"></i>',
        }));
      }, { once: true });
    });
    state.imagesLoaded = true;
  }

  function updateCategoryPagination() {
    $('category-page-info').textContent = `第 ${state.page} / ${state.totalPages} 页`;
    $('category-prev-page').disabled = state.page <= 1;
    $('category-next-page').disabled = state.page >= state.totalPages;
  }

  $('category-prev-page').addEventListener('click', () => {
    if (state.page > 1) loadCategories(state.page - 1);
  });
  $('category-next-page').addEventListener('click', () => {
    if (state.page < state.totalPages) loadCategories(state.page + 1);
  });

  function populateSelect() {
    const sel = $('category-select');
    const previous = sel.value;
    sel.innerHTML = '<option value="all">全部（全局随机）</option>' +
      state.allCategories.map((c) => `<option value="${util.escapeHtml(c.name)}">${util.escapeHtml(c.name)}</option>`).join('');
    if (previous && Array.from(sel.options).some((o) => o.value === previous)) sel.value = previous;
  }

  function updateCategoryInfoText() {
    const el = $('category-info');
    if (!el) return;
    const total = state.totalCategories || state.allCategories.length;
    const names = state.allCategories.slice(0, 4).map((c) => c.name).join('、');
    el.textContent = names
      ? `${total} 个图片分类，覆盖 ${names} 等场景，按需取用。`
      : '按分类随机，无需解析 JSON，图片随取随用。';
  }

  /* ------------------------------ 分类详情 ------------------------------ */
  async function openCategory(name) {
    state.category = name;
    state.categoryPage = 1;
    showModule('category-images');
    $('category-title').textContent = name;
    $('category-images-desc').textContent = '加载中…';
    await loadCategoryImagesPage();
  }

  async function loadCategoryImagesPage() {
    const grid = $('category-images-grid');
    grid.innerHTML = Array.from({ length: 6 }).map(() => `
      <div class="card" style="height:220px"><div class="skeleton" style="height:150px;border-radius:14px 14px 0 0"></div>
      <div style="padding:14px"><div class="skeleton" style="height:12px;width:60%"></div></div></div>`).join('');

    try {
      const res = await api(`/api/category/images?name=${encodeURIComponent(state.category)}&page=${state.categoryPage}`);
      state.categoryTotalPages = Math.max(1, (res && res.total_pages) || 1);
      state.categoryTotalImages = (res && res.total_images) || 0;
      const images = (res && res.images) || [];
      $('category-images-desc').textContent = `共 ${state.categoryTotalImages} 张图片 · 第 ${state.categoryPage} / ${state.categoryTotalPages} 页`;
      renderImageCards(images);
      updateImagesPagination();
    } catch (e) {
      grid.innerHTML = `<div class="empty" style="grid-column:1/-1">
        <i class="fa-solid fa-triangle-exclamation"></i><p>${util.escapeHtml(e.message)}</p></div>`;
      $('category-images-desc').textContent = '加载失败';
    }
  }

  function renderImageCards(images) {
    const grid = $('category-images-grid');
    if (!images.length) {
      grid.innerHTML = `<div class="empty" style="grid-column:1/-1">
        <i class="fa-solid fa-image-slash"></i><p>该分类下暂无图片</p></div>`;
      return;
    }
    grid.innerHTML = images.map((img) => {
      const url = BASE + img.url;
      const thumbUrl = `${BASE}/thumb?path=${encodeURIComponent(img.path)}&w=480`;
      const safeName = util.escapeHtml(img.name);
      return `
        <article class="card card--lift img-card">
          <div class="img-card__media">
            <img src="${thumbUrl}" alt="${safeName}" loading="lazy">
          </div>
          <div class="img-card__body">
            <p class="small truncate muted" title="${safeName}">${safeName}</p>
            <div class="row gap-2">
              <a class="btn btn--outline btn--sm grow" href="${url}" target="_blank" rel="noopener">
                <i class="fa-solid fa-up-right-from-square"></i>查看
              </a>
              <button class="btn btn--soft btn--sm btn--icon" data-download="${url}" data-name="${safeName}" title="下载">
                <i class="fa-solid fa-download"></i>
              </button>
            </div>
          </div>
        </article>`;
    }).join('');

    grid.querySelectorAll('[data-download]').forEach((btn) => {
      btn.addEventListener('click', () => downloadFile(btn.dataset.download, btn.dataset.name));
    });
  }

  function updateImagesPagination() {
    $('category-images-page-info').textContent = `第 ${state.categoryPage} / ${state.categoryTotalPages} 页`;
    $('category-images-prev').disabled = state.categoryPage <= 1;
    $('category-images-next').disabled = state.categoryPage >= state.categoryTotalPages;
  }

  $('category-images-prev').addEventListener('click', () => {
    if (state.categoryPage > 1) { state.categoryPage--; loadCategoryImagesPage(); }
  });
  $('category-images-next').addEventListener('click', () => {
    if (state.categoryPage < state.categoryTotalPages) { state.categoryPage++; loadCategoryImagesPage(); }
  });

  async function downloadFile(url, filename) {
    try {
      const res = await fetch(url, { credentials: 'same-origin' });
      if (!res.ok) throw new Error('下载失败');
      const blob = await res.blob();
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = filename || 'image';
      document.body.appendChild(link);
      link.click();
      link.remove();
      // 立刻 revoke 会让部分浏览器取消下载，延迟释放
      setTimeout(() => URL.revokeObjectURL(link.href), 4000);
    } catch (e) {
      Toast.error(e.message || '下载失败，请重试');
    }
  }

  /* ------------------------------ 随机图片演示 ------------------------------ */
  async function loadRandomImage() {
    const category = $('category-select').value;
    const url = category && category !== 'all'
      ? `${BASE}/random?type=${encodeURIComponent(category)}`
      : `${BASE}/random`;

    $('api-url').value = url;
    $('loading').classList.remove('hidden');
    $('loading').innerHTML = '<div class="spinner spinner--lg"></div><p>正在获取图片…</p>';
    $('random-image').classList.add('hidden', 'is-fading');
    $('image-tools').classList.add('hidden');

    try {
      const res = await fetch(url, { credentials: 'same-origin', cache: 'no-store' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      if (state.currentBlobUrl) URL.revokeObjectURL(state.currentBlobUrl);
      state.currentBlobUrl = URL.createObjectURL(blob);

      const img = $('random-image');
      img.onload = () => {
        $('loading').classList.add('hidden');
        $('image-tools').classList.remove('hidden');
        requestAnimationFrame(() => img.classList.remove('is-fading'));
        $('image-meta').innerHTML = `
          <span><i class="fa-solid fa-ruler-combined"></i>${img.naturalWidth} × ${img.naturalHeight}</span>
          <span><i class="fa-solid fa-file-lines"></i>${util.formatBytes(blob.size)}</span>
          <span><i class="fa-solid fa-tag"></i>${util.escapeHtml(category === 'all' ? '全局随机' : category)}</span>`;
      };
      img.onerror = () => {
        $('loading').classList.add('hidden');
        $('loading').classList.remove('hidden');
        $('loading').innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i><p>图片渲染失败，请重试</p>';
      };
      img.src = state.currentBlobUrl;
      img.classList.remove('hidden');
      state.currentImageUrl = url;
    } catch (e) {
      $('loading').innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i><p>获取失败，请稍后重试</p>';
      Toast.error('获取随机图片失败');
    }
  }

  $('refresh-btn').addEventListener('click', loadRandomImage);
  $('category-select').addEventListener('change', () => {
    if (!$('demo').classList.contains('hidden')) loadRandomImage();
  });

  $('open-btn').addEventListener('click', () => {
    if (state.currentImageUrl) window.open(state.currentImageUrl, '_blank', 'noopener');
  });
  $('download-btn').addEventListener('click', () => {
    if (state.currentBlobUrl) downloadFile(state.currentBlobUrl, 'random-image');
  });
  $('copy-btn').addEventListener('click', async () => {
    const ok = await util.copy($('api-url').value);
    Toast[ok ? 'success' : 'error'](ok ? '链接已复制' : '复制失败，请手动选择');
  });
  $('hero-copy').addEventListener('click', async () => {
    const ok = await util.copy($('hero-url').textContent);
    Toast[ok ? 'success' : 'error'](ok ? '直链已复制' : '复制失败');
  });

  /* 嵌入代码 */
  $('embed-btn').addEventListener('click', () => {
    const url = $('api-url').value || `${BASE}/random`;
    $('html-code').textContent = `<img src="${url}" alt="随机图片">`;
    $('markdown-code').textContent = `![随机图片](${url})`;
    $('url-code').textContent = url;
    Modal.open('embed-modal');
  });
  $('copy-embed-code').addEventListener('click', async () => {
    const text = `HTML:\n${$('html-code').textContent}\n\nMarkdown:\n${$('markdown-code').textContent}\n\nURL:\n${$('url-code').textContent}`;
    const ok = await util.copy(text);
    Toast[ok ? 'success' : 'error'](ok ? '已复制全部代码' : '复制失败');
  });

  /* ------------------------------ 文档 ------------------------------ */
  function switchTab(name) {
    document.querySelectorAll('.tab').forEach((t) => t.classList.toggle('is-active', t.dataset.tab === name));
    document.querySelectorAll('.doc-pane').forEach((p) => p.classList.toggle('hidden', p.dataset.pane !== name));
    if (name === 'changelog' && !$('changelog-content').dataset.loaded) loadChangelog();
  }
  document.querySelectorAll('.tab').forEach((tab) => {
    tab.addEventListener('click', () => switchTab(tab.dataset.tab));
  });

  function renderDocCategories() {
    const box = $('doc-category-list');
    if (!state.allCategories.length) {
      box.innerHTML = '<span class="tiny dim">暂无分类</span>';
      return;
    }
    box.innerHTML = state.allCategories
      .map((c) => `<span class="badge badge--muted">${util.escapeHtml(c.name)}</span>`).join('');
  }

  function firstCategoryName(index, fallback) {
    const list = state.allCategories;
    if (!list.length) return fallback;
    return list[Math.min(index, list.length - 1)].name;
  }

  async function updateDocUrls() {
    const c0 = firstCategoryName(0, '<分类名>');
    $('doc-base-url').textContent = `${BASE}/random`;
    $('doc-category-url').textContent = `${BASE}/random?type=${encodeURIComponent(c0)}`;

    // 直链示例必须用真实存在的文件，否则贴到浏览器里就是 404。
    // 取该分类第一张图；分类为空时退回占位说明。
    let sample = `${c0}/<文件名>`;
    try {
      const res = await api('/api/category/images?name=' + encodeURIComponent(c0) + '&page=1');
      const first = (res && res.images && res.images[0]) || null;
      if (first && first.path) sample = first.path;
    } catch (e) { /* 拿不到就用占位符，不影响其它文档内容 */ }

    $('doc-image-url').textContent = `${BASE}/image?path=${encodeURIComponent(sample)}`;
    $('doc-thumb-url').textContent = `${BASE}/thumb?path=${encodeURIComponent(sample)}&w=320`;
    $('doc-combo-url').textContent = `${BASE}/random?type=${encodeURIComponent(c0)}&w=640`;

    const cat = (i, fb) => encodeURIComponent(firstCategoryName(i, fb));
    $('example-html').textContent =
`<!-- 基础用法 -->
<img src="${BASE}/random?type=${cat(0, '<分类名>')}" alt="随机图片">

<!-- 指定分类 -->
<img src="${BASE}/random?type=${cat(1, 'city')}" alt="分类随机图片">`;

    $('example-js').textContent =
`async function loadRandomImage(el) {
  const res = await fetch('${BASE}/random?type=${cat(0, 'animal')}');
  if (!res.ok) throw new Error('HTTP ' + res.status);
  const blob = await res.blob();
  el.src = URL.createObjectURL(blob);   // 记得在合适时机 revoke
}

loadRandomImage(document.querySelector('#cover'));`;

    $('example-python').textContent =
`import requests

def save_random_image(path='random.jpg'):
    url = '${BASE}/random?type=${cat(0, 'art')}'
    res = requests.get(url, timeout=15)
    if res.status_code == 200:
        with open(path, 'wb') as f:
            f.write(res.content)
        print('saved:', path)
    else:
        print('failed:', res.status_code)

save_random_image()`;

    $('example-php').textContent =
`<?php
$url = '${BASE}/random?type=${cat(0, 'food')}';
echo "<img src='{$url}' alt='随机图片'>";`;

    const faq = $('faq-api-usage');
    if (faq) faq.textContent = `把 ${BASE}/random 当作图片地址使用即可，例如 <img src="${BASE}/random">。`;
  }

  /* ------------------------------ 更新日志 ------------------------------ */
  const REPO = 'YunJian101/Random-Pictures';

  function parseReleaseBody(body) {
    const items = [];
    let group = '';
    String(body || '').split(/\r?\n/).forEach((raw) => {
      const line = raw.trim();
      if (!line) return;
      const heading = line.match(/^#{1,4}\s+(.+)$/);
      if (heading) { group = heading[1].trim(); return; }
      const bullet = line.match(/^(?:[-*•]|\d+[.)])\s+(.+)$/);
      const text = bullet ? bullet[1].trim() : (line.length < 140 && !/^https?:/.test(line) ? line : '');
      if (!text) return;
      items.push({ group, text: text.replace(/[*_`]/g, '') });
    });
    return items.slice(0, 12);
  }

  /** 顶部公告栏：取 GitHub 最新一条 release 的说明滚动展示 */
  async function loadAnnouncement() {
    try {
      const res = await fetch(`https://api.github.com/repos/${REPO}/releases?per_page=1`, {
        headers: { Accept: 'application/vnd.github+json' },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      updateAnnouncement(await res.json());
    } catch (e) {
      updateAnnouncement(null);   // 取不到就保持欢迎语，不报错
    }
  }

  async function loadChangelog() {
    const box = $('changelog-content');
    box.dataset.loaded = '1';
    box.innerHTML = '<div class="row gap-2 muted small"><div class="spinner"></div>正在从 GitHub 拉取更新日志…</div>';

    try {
      const res = await fetch(`https://api.github.com/repos/${REPO}/releases?per_page=5`, {
        headers: { Accept: 'application/vnd.github+json' },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const releases = await res.json();
      updateAnnouncement(releases);

      if (!Array.isArray(releases) || !releases.length) {
        box.innerHTML = '<div class="empty"><i class="fa-regular fa-folder-open"></i><p>暂无发布记录</p></div>';
        return;
      }

      box.innerHTML = releases.map((rel, i) => {
        const version = rel.tag_name || rel.name || '未命名版本';
        const date = rel.published_at ? util.formatDate(rel.published_at, false) : '';
        const items = parseReleaseBody(rel.body);
        const badge = i === 0
          ? '<span class="badge badge--primary">最新</span>'
          : (rel.prerelease ? '<span class="badge badge--warn">预览</span>' : '');
        const list = items.length
          ? items.map((it) => `<li class="small" style="display:flex;gap:8px;padding:3px 0">
              <i class="fa-solid fa-circle" style="font-size:4px;margin-top:9px;color:var(--text-3);flex:0 0 auto"></i>
              <span class="muted">${it.group ? `<b style="color:var(--text);font-weight:600">${util.escapeHtml(it.group)} · </b>` : ''}${util.escapeHtml(it.text)}</span>
            </li>`).join('')
          : '<li class="small dim">暂无详细说明</li>';

        return `<div class="card card--pad">
          <div class="row--between wrap gap-2" style="margin-bottom:10px">
            <div class="row gap-2">
              <span class="strong" style="font-size:15px">${util.escapeHtml(version)}</span>
              ${badge}
            </div>
            <span class="tiny dim">${date}</span>
          </div>
          <ul>${list}</ul>
          <a class="tiny" style="display:inline-flex;gap:5px;margin-top:10px;color:var(--primary)"
             href="${rel.html_url || `https://github.com/${REPO}/releases`}" target="_blank" rel="noopener">
            在 GitHub 查看完整说明 <i class="fa-solid fa-arrow-up-right-from-square" style="font-size:10px;margin-top:3px"></i>
          </a>
        </div>`;
      }).join('');
    } catch (e) {
      box.innerHTML = `<div class="empty"><i class="fa-brands fa-github"></i>
        <p>无法获取更新日志（${util.escapeHtml(e.message)}）</p>
        <a class="btn btn--outline btn--sm" href="https://github.com/${REPO}/releases" target="_blank" rel="noopener">
          <i class="fa-brands fa-github"></i>前往 GitHub 查看
        </a></div>`;
      updateAnnouncement(null);
    }
  }

  let annTimer = null;
  let annIndex = 0;
  let annList = [];

  function updateAnnouncement(releases) {
    const textEl = $('announcement-text');
    const fallback = '欢迎使用随机图 API · 一行代码即可接入随机图片';
    if (!Array.isArray(releases) || !releases.length) {
      textEl.textContent = fallback;
      return;
    }
    const latest = releases[0];
    const version = latest.tag_name || latest.name || '';
    const items = parseReleaseBody(latest.body).slice(0, 4).map((i) => i.text);
    annList = [version ? `${version} 已发布` : '新版本已发布', ...items];
    if (!annList.length) { textEl.textContent = fallback; return; }

    annIndex = 0;
    textEl.textContent = annList[0];
    if (annTimer) clearInterval(annTimer);
    if (annList.length > 1) {
      annTimer = setInterval(() => {
        annIndex = (annIndex + 1) % annList.length;
        textEl.style.opacity = '0';
        setTimeout(() => { textEl.textContent = annList[annIndex]; textEl.style.opacity = '1'; }, 180);
      }, 5000);
    }
  }

  /* ------------------------------ 数据概览 ------------------------------ */
  function renderOverview() {
    const cats = state.allCategories;
    const totalImages = cats.reduce((sum, c) => sum + (c.image_count || 0), 0);

    countUp($('kpi-categories'), cats.length, { suffix: '个' });
    countUp($('kpi-images'), totalImages, { suffix: '张' });
    countUp($('kpi-average'), cats.length ? Math.round(totalImages / cats.length) : 0, { suffix: '张' });
    $('overview-updated').textContent = '更新于 ' + util.formatDate(new Date(), true);

    // 首屏指标条
    const heroCats = $('hero-stat-cats');
    const heroImgs = $('hero-stat-imgs');
    if (heroCats) countUp(heroCats, cats.length);
    if (heroImgs) countUp(heroImgs, totalImages);

    if (!cats.length) {
      countUp($('donut-total'), 0);
      $('overview-legend').innerHTML = '<span class="tiny dim">暂无分类数据</span>';
      $('overview-bars').innerHTML = '<div class="empty"><i class="fa-solid fa-chart-simple"></i><p>暂无分类数据</p></div>';
      return;
    }

    // ---- 环形图（按数量取前 3，其余归入「其他」）----
    const sorted = [...cats].sort((a, b) => (b.image_count || 0) - (a.image_count || 0));
    const top = sorted.slice(0, 3);
    const others = sorted.slice(3).reduce((sum, c) => sum + (c.image_count || 0), 0);
    const total = Math.max(1, totalImages);

    const segments = top.map((c, i) => ({
      label: c.name,
      value: c.image_count || 0,
      color: ['var(--primary)', 'color-mix(in srgb, var(--primary) 55%, var(--accent))', 'var(--accent)'][i],
    }));
    if (others > 0 || sorted.length > 3) {
      segments.push({ label: '其他分类', value: others, color: 'var(--surface-3)' });
    }

    const donut = $('overview-donut');
    let acc = 0;
    segments.forEach((seg, i) => {
      acc += (seg.value / total) * 100;
      donut.style.setProperty(`--p${i + 1}`, `${Math.min(100, acc).toFixed(2)}%`);
    });
    // 补齐剩余段，避免超过 100% 时色带错位
    for (let i = segments.length; i < 4; i += 1) donut.style.setProperty(`--p${i + 1}`, '0%');
    countUp($('donut-total'), totalImages);

    $('overview-legend').innerHTML = segments.map((seg) => `
      <div class="legend__item">
        <span class="legend__dot" style="background:${seg.color}"></span>
        <span class="truncate">${util.escapeHtml(seg.label)}</span>
        <span class="legend__value">${seg.value.toLocaleString('zh-CN')}</span>
      </div>`).join('');

    // ---- 分布条 ----
    const max = Math.max(1, ...sorted.map((c) => c.image_count || 0));
    $('overview-bars').innerHTML = sorted.map((c) => {
      const count = c.image_count || 0;
      return `<div class="bar-row">
        <span class="bar-row__name" title="${util.escapeHtml(c.name)}">${util.escapeHtml(c.name)}</span>
        <span class="bar-row__track"><span class="bar-row__fill" style="width:${Math.max(3, (count / max) * 100)}%"></span></span>
        <span class="bar-row__val">${count}</span>
      </div>`;
    }).join('');
  }

  /* ------------------------------ 反馈 ------------------------------ */
  const feedbackContent = $('feedback-content');
  feedbackContent.addEventListener('input', () => {
    // 上限只认 textarea 的 maxlength，避免和 HTML 里各写一个数字后对不上
    const max = feedbackContent.maxLength > 0 ? feedbackContent.maxLength : 1000;
    $('feedback-count').textContent = `${feedbackContent.value.length} / ${max}`;
  });

  $('feedback-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const content = feedbackContent.value.trim();
    if (content.length < 5) {
      Toast.warn('请至少输入 5 个字，方便我们定位问题');
      feedbackContent.focus();
      return;
    }
    const btn = $('feedback-submit');
    btn.disabled = true;
    btn.innerHTML = '<div class="spinner"></div>提交中…';
    try {
      const type = $('feedback-type').value;
      await api('/api/feedbacks', {
        method: 'POST',
        body: { content: `[${type}] ${content}` },
      });
      feedbackContent.value = '';
      const max = feedbackContent.maxLength > 0 ? feedbackContent.maxLength : 1000;
      $('feedback-count').textContent = `0 / ${max}`;
      Modal.result(true, '反馈已提交', '感谢你的反馈，我们会在处理后在「我的反馈」中回复。');
    } catch (err) {
      if (err.status === 401) {
        const go = await util.confirm('需要登录', '提交反馈需要先登录账号，是否现在前往登录？', '去登录');
        if (go) window.location.href = '/login';
      } else {
        Toast.error(err.message || '提交失败，请稍后重试');
      }
    } finally {
      btn.disabled = false;
      btn.innerHTML = '<i class="fa-solid fa-paper-plane"></i>提交反馈';
    }
  });

  /* ------------------------------ 启动 ------------------------------ */
  $('footer-year').textContent = new Date().getFullYear();
  $('hero-url').textContent = `${BASE}/random`;

  (async function init() {
    // 支持从其它页面跳转时直接打开指定模块
    let target = null;
    try {
      target = new URLSearchParams(location.search).get('m');
      if (!target) {
        target = localStorage.getItem('openModule');
        if (target) localStorage.removeItem('openModule');
      }
    } catch (err) { /* noop */ }

    await Promise.allSettled([loadSiteInfo(), loadAuthState(), loadCategories(1), loadAnnouncement()]);

    if (target) showModule(target);
    else loadCategoryImages();
  })();

  /* ------------------------------ 服务状态 ------------------------------ */
  // 之前写死「运行中 · 服务可用」，接口挂了也照样亮绿灯。这里真打一次公开接口。
  (async function probeStatus() {
    const text = $('hero-status-text');
    const desc = $('hero-status-desc');
    const dot = $('hero-status-dot');
    const box = $('hero-status');
    if (!text || !desc) return;

    const started = performance.now();
    try {
      await api('/api/system/info', { timeout: 6000 });
      text.textContent = '运行中';
      desc.textContent = `服务可用 · ${Math.round(performance.now() - started)}ms`;
    } catch (e) {
      text.textContent = '接口异常';
      desc.textContent = '服务暂不可用，请稍后重试';
      if (box) box.classList.add('is-down');
      if (dot) dot.classList.add('is-down');
    }
  })();

});
