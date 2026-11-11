/**
 * 用户中心：快捷调用、我的反馈、账号设置
 *
 * 从页面内联脚本抽出，逻辑未改动；HTML 只保留结构。
 */
document.addEventListener('DOMContentLoaded', function () {
  'use strict';

  const { api, Toast, util, Session, renderThread } = window.RP;
  const $ = (id) => document.getElementById(id);
  const BASE = util.baseUrl();

  const state = {
    categories: [],
    style: 'url',
    user: null,
    previewUrl: '',
    blobUrl: '',
  };

  const TITLES = {
    quick: ['快捷调用', '生成可直接使用的图片链接'],
    feedback: ['我的反馈', '提交问题并跟踪处理进度'],
    profile: ['账号信息', '查看当前登录账号'],
  };

  const STATUS = {
    pending: { label: '待处理', cls: 'badge--warn' },
    processing: { label: '处理中', cls: 'badge--accent' },
    resolved: { label: '已解决', cls: 'badge--success' },
    closed: { label: '已关闭', cls: 'badge--muted' },
  };

  /* ------------------------------ 侧栏与视图 ------------------------------ */
  function showView(name) {
    if (name === 'profile') loadSessions();
    document.querySelectorAll('[data-view-panel]').forEach((panel) => {
      panel.classList.toggle('hidden', panel.dataset.viewPanel !== name);
    });
    document.querySelectorAll('.sidebar__item[data-view]').forEach((btn) => {
      btn.classList.toggle('is-active', btn.dataset.view === name);
    });
    const [title, sub] = TITLES[name] || ['', ''];
    $('page-title').textContent = title;
    $('page-sub').textContent = sub;
    closeSidebar();
    if (name === 'feedback') loadMyFeedbacks();
    if (name === 'profile') loadProfile();
    if (location.hash !== '#' + name) history.replaceState(null, '', '#' + name);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  document.querySelectorAll('.sidebar__item[data-view]').forEach((btn) => {
    btn.addEventListener('click', () => showView(btn.dataset.view));
  });

  function closeSidebar() {
    $('sidebar').classList.remove('is-open');
    document.querySelector('.sidebar-overlay').classList.remove('is-open');
  }

  document.querySelector('[data-sidebar-toggle]').addEventListener('click', () => {
    $('sidebar').classList.add('is-open');
    document.querySelector('.sidebar-overlay').classList.add('is-open');
  });
  document.querySelector('[data-sidebar-close]').addEventListener('click', closeSidebar);

  /* ------------------------------ 会话 ------------------------------ */
  async function initSession() {
    const user = await Session.verify();
    if (!user) {
      try { sessionStorage.setItem('redirect_after_login', location.pathname); } catch (e) { /* noop */ }
      window.location.href = '/login';
      return null;
    }
    state.user = user;
    Session.setLocal(user);
    const roleLabel = user.role === 'admin' ? '管理员' : (user.role === 'vip' ? 'VIP 用户' : '普通用户');
    $('side-username').textContent = user.username;
    $('side-role').textContent = roleLabel;
    $('avatar').textContent = (user.username || 'U').slice(0, 1).toUpperCase();
    $('hello-name').textContent = user.username;
    fillProfile(user);
    return user;
  }

  function doLogout() {
    util.confirm('退出登录', '确定要退出当前账号吗？', '退出').then((ok) => {
      if (ok) Session.logout('/');
    });
  }
  $('logout-btn').addEventListener('click', doLogout);

  /* ------------------------------ 账号资料 / 密码 ------------------------------ */
  const ROLE_TEXT = { admin: '管理员', vip: 'VIP 用户', user: '普通用户' };

  function fillProfile(user) {
    if (!user) return;
    $('p-username').value = user.username || '';
    $('p-email').value = user.email || '';
    $('p-id').textContent = user.id != null ? String(user.id) : '—';
    $('p-created').textContent = user.created_at ? util.formatDate(user.created_at) : '—';
    $('p-lastlogin').textContent = user.last_login ? util.formatDate(user.last_login) : '从未登录';

    const label = ROLE_TEXT[user.role] || user.role || '未知';
    $('p-role-badge').textContent = label;
    $('p-role-badge').className = 'badge ' + (user.role === 'admin' ? 'badge--primary' : 'badge--muted');
  }

  async function loadProfile() {
    try {
      const res = await api('/api/me');
      const user = res && res.data && res.data.user;
      if (user) { fillProfile(user); state.user = user; }
    } catch (e) {
      Toast.error(e.message || '资料加载失败');
    }
  }

  function showFieldError(id, message) {
    const el = $(id);
    el.textContent = message;
    el.classList.remove('hidden');
  }

  function clearFieldErrors() {
    document.querySelectorAll('.field-error').forEach((el) => {
      el.textContent = '';
      el.classList.add('hidden');
    });
  }

  // 保存基本资料
  $('profile-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    clearFieldErrors();

    const username = $('p-username').value.trim();
    const email = $('p-email').value.trim();
    let ok = true;

    if (!/^[a-zA-Z0-9_]{3,16}$/.test(username)) {
      showFieldError('p-username-error', '用户名需为 3-16 位字母、数字或下划线');
      ok = false;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      showFieldError('p-email-error', '请输入有效的邮箱地址');
      ok = false;
    }
    if (!ok) return;

    const btn = $('profile-save');
    btn.disabled = true;
    try {
      const res = await api('/api/me', { method: 'PUT', body: { username, email } });
      const user = res && res.data && res.data.user;
      if (user) {
        fillProfile(user);
        state.user = user;
        Session.setLocal(user);
        $('side-username').textContent = user.username;
        $('hello-name').textContent = user.username;
        $('avatar').textContent = (user.username || 'U').slice(0, 1).toUpperCase();
      }
      Toast.success('资料已更新');
    } catch (err) {
      const msg = err.message || '保存失败';
      if (err.status === 400 && msg.includes('用户名')) showFieldError('p-username-error', msg);
      else if (err.status === 400 && msg.includes('邮箱')) showFieldError('p-email-error', msg);
      else Toast.error(msg);
    } finally {
      btn.disabled = false;
    }
  });

  // 修改密码
  $('password-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    clearFieldErrors();

    const current = $('pwd-current').value;
    const next = $('pwd-new').value;
    const confirm = $('pwd-confirm').value;
    let ok = true;

    if (!current) { showFieldError('pwd-current-error', '请输入当前密码'); ok = false; }
    if (next.length < 6) { showFieldError('pwd-new-error', '新密码至少 6 位'); ok = false; }
    if (next && next === current) { showFieldError('pwd-new-error', '新密码不能与当前密码相同'); ok = false; }
    if (confirm !== next) { showFieldError('pwd-confirm-error', '两次输入的新密码不一致'); ok = false; }
    if (!ok) return;

    const btn = $('password-save');
    btn.disabled = true;
    try {
      await api('/api/me/password', {
        method: 'PUT',
        body: { current_password: current, new_password: next },
      });
      $('password-form').reset();
      Toast.success('密码已修改，其它设备的登录已失效');
    } catch (err) {
      const msg = err.message || '修改失败';
      if (msg.includes('当前密码')) showFieldError('pwd-current-error', msg);
      else if (msg.includes('新密码')) showFieldError('pwd-new-error', msg);
      else Toast.error(msg);
    } finally {
      btn.disabled = false;
    }
  });

  /* ------------------------------ 分类 ------------------------------ */
  async function loadCategories() {
    const all = [];
    let page = 1;
    let total = 1;
    do {
      const res = await api(`/api/categories?page=${page}`);
      if (res && Array.isArray(res.category_list)) all.push(...res.category_list);
      total = (res && res.total_pages) || 1;
      page += 1;
    } while (page <= total && page <= 50);

    state.categories = all;

    // 分类只作为「快捷调用」的下拉选项，不再单独做一个浏览页
    const select = $('category-select');
    select.innerHTML = '<option value="">全部（全局随机）</option>' + all.map((c) =>
      `<option value="${util.escapeHtml(c.name)}">${util.escapeHtml(c.name)}（${c.image_count || 0}）</option>`
    ).join('');
  }

  /* ------------------------------ 代码生成 ------------------------------ */
  function buildUrl() {
    const category = $('category-select').value;
    return category
      ? `${BASE}/random?type=${encodeURIComponent(category)}`
      : `${BASE}/random`;
  }

  function updateCode() {
    const url = buildUrl();
    const templates = {
      url: url,
      html: `<img src="${url}" alt="随机图片">`,
      markdown: `![随机图片](${url})`,
      js: `const res = await fetch('${url}');\nconst blob = await res.blob();\ndocument.querySelector('#cover').src = URL.createObjectURL(blob);`,
      python: `import requests\n\nres = requests.get('${url}', timeout=15)\nif res.status_code == 200:\n    open('random.jpg', 'wb').write(res.content)`,
    };
    $('code-output').textContent = templates[state.style] || url;
    $('open-preview').href = url;
  }

  $('category-select').addEventListener('change', updateCode);

  document.querySelectorAll('#code-style .tab').forEach((tab) => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('#code-style .tab').forEach((t) => t.classList.remove('is-active'));
      tab.classList.add('is-active');
      state.style = tab.dataset.style;
      updateCode();
    });
  });

  $('copy-code').addEventListener('click', async () => {
    const ok = await util.copy($('code-output').textContent);
    Toast[ok ? 'success' : 'error'](ok ? '已复制到剪贴板' : '复制失败，请手动选择');
  });

  /* ------------------------------ 预览 ------------------------------ */
  async function loadPreview() {
    const url = buildUrl();
    state.previewUrl = url;
    $('preview-empty').innerHTML = '<div class="spinner spinner--lg"></div><p class="small">正在获取图片…</p>';
    $('preview-empty').classList.remove('hidden');
    const oldImg = $('preview-stage').querySelector('img');
    if (oldImg) oldImg.remove();

    try {
      const res = await fetch(url, { credentials: 'same-origin', cache: 'no-store' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      if (state.blobUrl) URL.revokeObjectURL(state.blobUrl);
      state.blobUrl = URL.createObjectURL(blob);

      const img = new Image();
      img.alt = '随机图片预览';
      img.onload = () => {
        $('preview-empty').classList.add('hidden');
        img.style.opacity = '0';
        $('preview-stage').appendChild(img);
        requestAnimationFrame(() => { img.style.opacity = '1'; });
        $('preview-meta').innerHTML = `
          <span><i class="fa-solid fa-ruler-combined"></i>${img.naturalWidth} × ${img.naturalHeight}</span>
          <span><i class="fa-solid fa-file-lines"></i>${util.formatBytes(blob.size)}</span>
          <span><i class="fa-solid fa-tag"></i>${util.escapeHtml($('category-select').value || '全局随机')}</span>`;
      };
      img.onerror = () => {
        $('preview-empty').innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i><p class="small">图片渲染失败</p>';
      };
      img.src = state.blobUrl;
    } catch (e) {
      $('preview-empty').innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i><p class="small">获取失败，请稍后重试</p>';
      $('preview-meta').innerHTML = '<span>加载失败</span>';
    }
  }

  $('preview-btn').addEventListener('click', loadPreview);
  $('refresh-preview').addEventListener('click', loadPreview);

  /* ------------------------------ 我的反馈 ------------------------------ */
  async function loadMyFeedbacks() {
    const list = $('fb-list');
    try {
      const res = await api('/api/my/feedbacks');
      const feedbacks = (res && res.data && res.data.feedbacks) || [];
      $('fb-total').textContent = `共 ${feedbacks.length} 条`;
      $('fb-count-badge').textContent = feedbacks.length;

      if (!feedbacks.length) {
        list.innerHTML = '<div class="empty"><i class="fa-regular fa-comment-dots"></i><p>还没有提交过反馈</p></div>';
        return;
      }

      list.innerHTML = feedbacks.map((fb) => {
        const st = STATUS[fb.status] || { label: fb.status, cls: 'badge--muted' };
        const messages = fb.messages || [];

        // 老数据（对话表建立之前）没有 messages，退回显示原始内容
        const body = messages.length
          ? renderThread(fb)
          : `<div class="fb-item__content">${util.escapeHtml(fb.content)}</div>`;

        // 只有「处理中」允许继续回复；待处理要等管理员先回应
        let footer = '';
        if (fb.status === 'processing') {
          footer = `
            <form class="fb-reply-form" data-feedback="${fb.id}">
              <div class="input-group grow">
                <i class="fa-solid fa-reply"></i>
                <input class="input input--sm" maxlength="900" placeholder="继续补充说明…">
              </div>
              <button class="btn btn--primary btn--sm" type="submit"><i class="fa-solid fa-paper-plane"></i>发送</button>
            </form>`;
        } else if (fb.status === 'pending') {
          footer = `<p class="fb-hint"><i class="fa-regular fa-clock"></i>已提交，等待管理员受理；受理后可继续沟通。</p>`;
        } else if (fb.status === 'resolved') {
          footer = `<p class="fb-hint"><i class="fa-solid fa-circle-check"></i>问题已解决，本条反馈已归档。若仍有疑问请重新提交一条反馈。</p>`;
        } else if (fb.status === 'closed') {
          const who = fb.closed_by === 'user' ? '你已关闭该反馈' : '管理员已关闭该反馈';
          footer = `<p class="fb-hint"><i class="fa-solid fa-box-archive"></i>${who}，无法继续回复。</p>`;
        }

        const canClose = fb.status === 'pending' || fb.status === 'processing';
        const closeBtn = canClose
          ? `<button class="btn btn--ghost btn--sm" data-fb-close="${fb.id}">
               <i class="fa-solid fa-box-archive"></i>关闭反馈
             </button>`
          : '';

        return `<article class="fb-item">
          <div class="fb-item__head">
            <div class="row gap-2 wrap">
              <span class="badge ${st.cls}">${st.label}</span>
              <span class="tiny dim">#${fb.id} · ${util.formatDate(fb.created_at)}</span>
              ${messages.length > 1 ? `<span class="tiny dim">· ${messages.length} 条对话</span>` : ''}
            </div>
            ${closeBtn}
          </div>
          ${body}
          ${footer}
        </article>`;
      }).join('');

      // 用户自行关闭反馈
      list.querySelectorAll('[data-fb-close]').forEach((btn) => {
        btn.addEventListener('click', async () => {
          const ok = await util.confirm('关闭反馈', '关闭后本条反馈将归档，且无法继续回复。确定吗？', '关闭');
          if (!ok) return;
          btn.disabled = true;
          try {
            await api(`/api/my/feedbacks/${btn.dataset.fbClose}/status`, {
              method: 'PUT',
              body: { status: 'closed' },
            });
            Toast.success('反馈已关闭');
            loadMyFeedbacks();
          } catch (err) {
            Toast.error(err.message || '关闭失败');
            btn.disabled = false;
          }
        });
      });

      // 内联回复：发送后状态自动变成「处理中」
      list.querySelectorAll('.fb-reply-form').forEach((form) => {
        form.addEventListener('submit', async (e) => {
          e.preventDefault();
          const input = form.querySelector('input');
          const content = input.value.trim();
          if (content.length < 2) { Toast.warn('请至少输入 2 个字'); input.focus(); return; }

          const btn = form.querySelector('button');
          btn.disabled = true;
          try {
            await api(`/api/my/feedbacks/${form.dataset.feedback}/messages`, {
              method: 'POST',
              body: { content },
            });
            Toast.success('已发送，反馈已回到处理中');
            loadMyFeedbacks();
          } catch (err) {
            Toast.error(err.message || '发送失败');
            btn.disabled = false;
          }
        });
      });
    } catch (e) {
      list.innerHTML = `<div class="empty"><i class="fa-solid fa-triangle-exclamation"></i><p>${util.escapeHtml(e.message)}</p></div>`;
    }
  }

  const feedbackContent = $('feedback-content');
  feedbackContent.addEventListener('input', () => {
    $('char-count').textContent = `${feedbackContent.value.length} / 900`;
  });

  $('feedback-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const content = feedbackContent.value.trim();
    if (content.length < 5) {
      Toast.warn('请至少输入 5 个字');
      feedbackContent.focus();
      return;
    }
    const btn = $('feedback-submit');
    btn.disabled = true;
    btn.innerHTML = '<div class="spinner"></div>提交中…';
    try {
      await api('/api/feedbacks', {
        method: 'POST',
        body: { content: `[${$('feedback-type').value}] ${content}` },
      });
      feedbackContent.value = '';
      $('char-count').textContent = '0 / 900';
      Toast.success('反馈已提交');
      loadMyFeedbacks();
    } catch (err) {
      if (err.status === 401) {
        Toast.error('登录状态已失效，请重新登录');
        setTimeout(() => { window.location.href = '/login'; }, 900);
      } else {
        Toast.error(err.message || '提交失败');
      }
    } finally {
      btn.disabled = false;
      btn.innerHTML = '<i class="fa-solid fa-paper-plane"></i>提交反馈';
    }
  });

  /* ------------------------------ 站点信息 ------------------------------ */
  (async function loadSiteInfo() {
    try {
      const res = await api('/api/system/info');
      const d = (res && res.data) || {};
      if (d.site_name) {
        document.title = `用户中心 · ${d.site_name}`;
        document.querySelectorAll('[data-site-name]').forEach((el) => { el.textContent = d.site_name; });
      }
      if (d.favicon_url) $('favicon').href = d.favicon_url;
    } catch (e) { /* noop */ }
  })();

  /* ------------------------------ 启动 ------------------------------ */
  (async function init() {
    const user = await initSession();
    if (!user) return;
    loadProfile();
    updateCode();
    try {
      await loadCategories();
      updateCode();
    } catch (e) {
      Toast.error('分类加载失败，可稍后重试');
    }
    loadPreview();
    loadMyFeedbacks();
    const initial = location.hash.replace('#', '');
    if (initial && TITLES[initial]) showView(initial);
  })();

  /* ------------------------------ 登录设备 ------------------------------ */
  function fmtTime(iso) {
    if (!iso) return '—';
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return '—';
    const pad = (n) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }

  async function loadSessions() {
    const host = $('session-list');
    if (!host) return;
    try {
      const res = await api('/api/me/sessions');
      const items = (res && res.data && res.data.sessions) || [];
      if (!items.length) {
        host.innerHTML = '<div class="empty"><p>暂无登录记录</p></div>';
        return;
      }
      host.innerHTML = items.map((it) => `
        <div class="session-row${it.is_current ? ' is-current' : ''}">
          <div class="session-row__icon"><i class="fa-solid fa-${it.os === 'Android' || it.os === 'iOS' ? 'mobile-screen' : 'desktop'}"></i></div>
          <div class="session-row__main">
            <div class="session-row__title">
              ${util.escapeHtml([it.browser, it.os].filter(Boolean).join(" · "))}
              ${it.is_current ? '<span class="badge badge--success">当前设备</span>' : ''}
            </div>
            <div class="session-row__meta">
              ${it.ip ? `IP ${util.escapeHtml(it.ip)} · ` : ''}最近活跃 ${fmtTime(it.last_seen)} · 登录于 ${fmtTime(it.created_at)}
            </div>
          </div>
          <button class="btn btn--ghost btn--sm" data-revoke="${util.escapeHtml(it.id)}">
            ${it.is_current ? '退出' : '下线'}
          </button>
        </div>`).join('');
    } catch (e) {
      host.innerHTML = `<div class="empty"><p>${util.escapeHtml(e.message || '加载失败')}</p></div>`;
    }
  }

  document.addEventListener('click', async (e) => {
    const btn = e.target.closest('[data-revoke]');
    if (!btn) return;
    const ok = await util.confirm('退出该设备', '这个设备上的登录会立即失效，确定继续？', '退出');
    if (!ok) return;
    try {
      const res = await api('/api/me/sessions/' + btn.dataset.revoke, { method: 'DELETE' });
      Toast.success('已退出该设备');
      if (res && res.data && res.data.is_current) {
        setTimeout(() => { window.location.href = '/login'; }, 600);
        return;
      }
      loadSessions();
    } catch (err) {
      Toast.error(err.message || '操作失败');
    }
  });

  const revokeOthers = $('session-revoke-others');
  if (revokeOthers) {
    revokeOthers.addEventListener('click', async () => {
      const ok = await util.confirm('退出其它设备', '除当前设备外，其它登录全部下线。确定继续？', '全部退出');
      if (!ok) return;
      try {
        const res = await api('/api/me/sessions/revoke-others', { method: 'POST' });
        Toast.success((res && res.msg) || '已退出其它设备');
        loadSessions();
      } catch (err) {
        Toast.error(err.message || '操作失败');
      }
    });
  }

  window.addEventListener('hashchange', () => {
    const name = location.hash.replace('#', '');
    if (name && TITLES[name]) showView(name);
  });
});
