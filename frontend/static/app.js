/**
 * Random Pictures · 公共脚本
 * 统一处理：主题、提示、弹窗、请求、格式化
 */
(function () {
  'use strict';

  const PREFIX = 'rp';
  const root = document.documentElement;

  /* ------------------------------ 主题 ------------------------------ */
  const Theme = {
    key: 'theme',
    current() {
      return root.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
    },
    apply(theme, persist = true) {
      const commit = () => {
        root.setAttribute('data-theme', theme);
        if (persist) {
          try { localStorage.setItem(this.key, theme); } catch (e) { /* 忽略隐私模式异常 */ }
        }
        document.querySelectorAll('[data-theme-icon]').forEach((el) => {
          el.className = theme === 'dark' ? 'fa-solid fa-sun' : 'fa-solid fa-moon';
        });
        document.dispatchEvent(new CustomEvent('themechange', { detail: theme }));
      };

      // 支持 View Transitions 时做一个从点击处扩散的圆形过渡，否则直接切换
      if (!Motion.reduced() && typeof document.startViewTransition === 'function') {
        try {
          document.startViewTransition(commit);
          return;
        } catch (e) { /* 降级 */ }
      }
      commit();
    },
    toggle(originEl) {
      const next = this.current() === 'dark' ? 'light' : 'dark';

      if (originEl && originEl.getBoundingClientRect) {
        const rect = originEl.getBoundingClientRect();
        root.style.setProperty('--vt-x', Math.round(rect.left + rect.width / 2) + 'px');
        root.style.setProperty('--vt-y', Math.round(rect.top + rect.height / 2) + 'px');
      }

      this.apply(next);
      Toast.show(next === 'dark' ? '已切换到夜间模式' : '已切换到日间模式', 'info');
    },
    init() {
      let saved = null;
      try { saved = localStorage.getItem(this.key); } catch (e) { /* noop */ }
      if (!saved) {
        saved = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
      }
      this.apply(saved, false);
      document.querySelectorAll('[data-theme-toggle]').forEach((btn) => {
        btn.addEventListener('click', (e) => this.toggle(e.currentTarget));
      });
    },
  };

  /* ------------------------------ 提示 ------------------------------ */
  const Toast = {
    host: null,
    ensure() {
      if (!this.host) {
        this.host = document.createElement('div');
        this.host.className = 'toast-host';
        this.host.setAttribute('role', 'status');
        this.host.setAttribute('aria-live', 'polite');
        document.body.appendChild(this.host);
      }
      return this.host;
    },
    show(message, type = 'ok', duration = 2600) {
      if (!message) return;
      const map = { ok: 'fa-circle-check', err: 'fa-circle-exclamation', info: 'fa-circle-info', warn: 'fa-triangle-exclamation' };
      const el = document.createElement('div');
      el.className = `toast toast--${type}`;
      el.innerHTML = `<i class="fa-solid ${map[type] || map.ok}"></i><span></span>`;
      el.querySelector('span').textContent = message;
      this.ensure().appendChild(el);
      requestAnimationFrame(() => el.classList.add('is-in'));
      setTimeout(() => {
        el.classList.remove('is-in');
        setTimeout(() => el.remove(), 260);
      }, duration);
    },
    success: (m) => Toast.show(m, 'ok'),
    error: (m) => Toast.show(m, 'err', 3600),
    info: (m) => Toast.show(m, 'info'),
    warn: (m) => Toast.show(m, 'warn', 3200),
  };

  /* ------------------------------ 弹窗 ------------------------------ */
  const Modal = {
    open(id) {
      const el = typeof id === 'string' ? document.getElementById(id) : id;
      if (!el) return;
      el.classList.add('is-open');
      el.setAttribute('aria-hidden', 'false');
      document.body.style.overflow = 'hidden';
      const focusable = el.querySelector('input, select, textarea, button');
      if (focusable) setTimeout(() => focusable.focus(), 120);
    },
    close(id) {
      const el = typeof id === 'string' ? document.getElementById(id) : id;
      if (!el) return;
      el.classList.remove('is-open');
      el.setAttribute('aria-hidden', 'true');
      if (!document.querySelector('.modal.is-open')) document.body.style.overflow = '';
    },
    closeAll() {
      document.querySelectorAll('.modal.is-open').forEach((el) => {
        el.classList.remove('is-open');
        el.setAttribute('aria-hidden', 'true');
      });
      document.body.style.overflow = '';
    },
    /** 绑定统一的关闭行为：点遮罩 / 点 [data-modal-close] / Esc */
    bind() {
      document.addEventListener('click', (e) => {
        if (e.target.classList && e.target.classList.contains('modal')) {
          Modal.close(e.target);
        }
        const closer = e.target.closest && e.target.closest('[data-modal-close]');
        if (closer) {
          const target = closer.getAttribute('data-modal-close');
          Modal.close(target || closer.closest('.modal'));
        }
      });
      document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') Modal.closeAll();
      });
    },
    /** 结果弹窗：成功 / 失败 */
    result(ok, title, text) {
      let el = document.getElementById('rp-result');
      if (!el) {
        el = document.createElement('div');
        el.id = 'rp-result';
        el.className = 'modal';
        el.setAttribute('aria-hidden', 'true');
        el.innerHTML = `
          <div class="modal__dialog modal__dialog--sm" role="dialog" aria-modal="true">
            <div class="modal__body">
              <div class="result">
                <div class="result__icon" data-icon-wrap><i class="fa-solid fa-check"></i></div>
                <div class="result__title" data-title></div>
                <p class="result__text" data-text></p>
              </div>
            </div>
            <div class="modal__foot" style="justify-content:center">
              <button class="btn btn--primary" data-modal-close>知道了</button>
            </div>
          </div>`;
        document.body.appendChild(el);
      }
      const wrap = el.querySelector('[data-icon-wrap]');
      wrap.className = `result__icon ${ok ? 'result__icon--ok' : 'result__icon--err'}`;
      wrap.innerHTML = `<i class="fa-solid ${ok ? 'fa-check' : 'fa-xmark'}"></i>`;
      el.querySelector('[data-title]').textContent = title || (ok ? '操作成功' : '操作失败');
      el.querySelector('[data-text]').textContent = text || '';
      Modal.open(el);
    },
  };

  /* ------------------------------ 请求 ------------------------------ */
  class ApiError extends Error {
    constructor(message, status, payload) {
      super(message);
      this.name = 'ApiError';
      this.status = status;
      this.payload = payload;
    }
  }

  /**
   * 统一请求封装
   * - 自动带 cookie
   * - 自动解析 JSON
   * - 401 跳登录、403 提示无权限
   */
  async function api(url, options = {}) {
    const opts = Object.assign({ credentials: 'same-origin', headers: {} }, options);
    if (opts.body && !(opts.body instanceof FormData)) {
      opts.headers['Content-Type'] = 'application/json';
      if (typeof opts.body !== 'string') opts.body = JSON.stringify(opts.body);
    }
    let res;
    try {
      res = await fetch(url, opts);
    } catch (e) {
      throw new ApiError('网络连接失败，请检查网络后重试', 0, null);
    }
    let payload = null;
    const ct = res.headers.get('content-type') || '';
    if (ct.includes('application/json')) {
      try { payload = await res.json(); } catch (e) { payload = null; }
    }
    if (res.status === 401) {
      throw new ApiError((payload && payload.msg) || '登录状态已失效，请重新登录', 401, payload);
    }
    if (res.status === 403) {
      throw new ApiError((payload && payload.msg) || '没有操作权限', 403, payload);
    }
    if (!res.ok) {
      const msg = (payload && (payload.msg || payload.detail)) || `请求失败（HTTP ${res.status}）`;
      throw new ApiError(typeof msg === 'string' ? msg : '请求失败', res.status, payload);
    }
    return payload;
  }

  /* ------------------------------ 工具 ------------------------------ */
  const util = {
    baseUrl() {
      return `${window.location.protocol}//${window.location.host}`;
    },
    escapeHtml(str) {
      return String(str == null ? '' : str).replace(/[&<>"']/g, (c) => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
      }[c]));
    },
    debounce(fn, wait = 260) {
      let timer = null;
      return function (...args) {
        clearTimeout(timer);
        timer = setTimeout(() => fn.apply(this, args), wait);
      };
    },
    formatBytes(bytes) {
      const n = Number(bytes) || 0;
      if (n <= 0) return '0 B';
      const units = ['B', 'KB', 'MB', 'GB', 'TB'];
      const i = Math.min(Math.floor(Math.log(n) / Math.log(1024)), units.length - 1);
      return `${(n / Math.pow(1024, i)).toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
    },
    formatDate(value, withTime = true) {
      if (!value) return '-';
      const d = new Date(value);
      if (Number.isNaN(d.getTime())) return String(value);
      const pad = (v) => String(v).padStart(2, '0');
      const date = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
      if (!withTime) return date;
      return `${date} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
    },
    /** 复制文本，失败时回退到 execCommand */
    async copy(text) {
      try {
        if (navigator.clipboard && window.isSecureContext) {
          await navigator.clipboard.writeText(text);
          return true;
        }
        throw new Error('clipboard unavailable');
      } catch (e) {
        try {
          const ta = document.createElement('textarea');
          ta.value = text;
          ta.style.position = 'fixed';
          ta.style.opacity = '0';
          document.body.appendChild(ta);
          ta.select();
          const ok = document.execCommand('copy');
          ta.remove();
          return ok;
        } catch (err) {
          return false;
        }
      }
    },
    /** 简单的确认框替代（原生 confirm 可访问性更好，样式统一用 Modal + Promise） */
    confirm(title, text, confirmLabel = '确定') {
      return new Promise((resolve) => {
        let el = document.getElementById('rp-confirm');
        if (!el) {
          el = document.createElement('div');
          el.id = 'rp-confirm';
          el.className = 'modal';
          el.setAttribute('aria-hidden', 'true');
          el.innerHTML = `
            <div class="modal__dialog modal__dialog--sm" role="dialog" aria-modal="true">
              <div class="modal__body">
                <div class="result">
                  <div class="result__icon result__icon--err"><i class="fa-solid fa-triangle-exclamation"></i></div>
                  <div class="result__title" data-title></div>
                  <p class="result__text" data-text></p>
                </div>
              </div>
              <div class="modal__foot">
                <button class="btn btn--outline" data-no>取消</button>
                <button class="btn btn--danger" data-yes></button>
              </div>
            </div>`;
          document.body.appendChild(el);
        }
        el.querySelector('[data-title]').textContent = title || '确认操作';
        el.querySelector('[data-text]').textContent = text || '';
        const yes = el.querySelector('[data-yes]');
        yes.textContent = confirmLabel;

        const finish = (value) => {
          Modal.close(el);
          yes.onclick = null;
          el.querySelector('[data-no]').onclick = null;
          resolve(value);
        };
        yes.onclick = () => finish(true);
        el.querySelector('[data-no]').onclick = () => finish(false);
        Modal.open(el);
      });
    },
  };

  /* ------------------------------ 会话 ------------------------------ */
  const Session = {
    async verify() {
      try {
        const data = await api('/api/auth/verify');
        return data && data.data ? data.data.user : null;
      } catch (e) {
        return null;
      }
    },
    setLocal(user) {
      try {
        localStorage.setItem('auth_status', JSON.stringify({
          isLoggedIn: !!user,
          username: user ? user.username : null,
          role: user ? user.role : null,
          timestamp: Date.now(),
        }));
      } catch (e) { /* noop */ }
    },
    async logout(redirect = '/') {
      try { await api('/api/logout', { method: 'POST' }); } catch (e) { /* 即使失败也清本地状态 */ }
      this.setLocal(null);
      window.location.href = redirect;
    },
  };

  /* ------------------------------ 密码显隐 ------------------------------ */
  // 用一个委托监听统一处理，避免每个含密码框的页面各写一份
  document.addEventListener('click', (e) => {
    const btn = e.target.closest && e.target.closest('[data-toggle-password]');
    if (!btn) return;
    const input = document.getElementById(btn.dataset.togglePassword);
    if (!input) return;

    const show = input.type === 'password';
    input.type = show ? 'text' : 'password';
    const icon = btn.querySelector('i');
    if (icon) icon.className = show ? 'fa-solid fa-eye' : 'fa-solid fa-eye-slash';
    btn.setAttribute('aria-label', show ? '隐藏密码' : '显示密码');
  });

  /* ------------------------------ 导航 ------------------------------ */
  function initNav() {
    const btn = document.querySelector('[data-nav-toggle]');
    const menu = document.querySelector('[data-nav-menu]');
    if (btn && menu) {
      btn.addEventListener('click', () => {
        const open = menu.classList.toggle('is-open');
        btn.setAttribute('aria-expanded', String(open));
        btn.innerHTML = open ? '<i class="fa-solid fa-xmark"></i>' : '<i class="fa-solid fa-bars"></i>';
      });
      menu.addEventListener('click', (e) => {
        if (e.target.closest('a, button')) {
          menu.classList.remove('is-open');
          btn.setAttribute('aria-expanded', 'false');
          btn.innerHTML = '<i class="fa-solid fa-bars"></i>';
        }
      });
    }
  }

  /* ------------------------------ 反馈对话渲染 ------------------------------ */
  /** 把单条反馈的 messages 渲染成对话气泡（用户 / 管理员两种样式） */
  function renderThread(feedback, options = {}) {
    const { scroll = false } = options;
    const messages = (feedback && feedback.messages) || [];
    if (!messages.length) return '';

    const items = messages.map((m) => {
      const isAdmin = m.author === 'admin';
      const name = m.author_name || (isAdmin ? '管理员' : '用户');
      const initial = String(name).trim().slice(0, 1).toUpperCase() || (isAdmin ? '管' : '用');
      return `
        <div class="msg${isAdmin ? ' msg--admin' : ''}">
          <div class="msg__avatar">${util.escapeHtml(initial)}</div>
          <div class="msg__body">
            <div class="msg__meta">
              <b>${util.escapeHtml(name)}</b>
              <span>${util.formatDate(m.created_at)}</span>
            </div>
            <div class="msg__text">${util.escapeHtml(m.content)}</div>
          </div>
        </div>`;
    }).join('');

    return `<div class="thread${scroll ? ' thread--scroll' : ''}">${items}</div>`;
  }

  /* ------------------------------ 动效工具 ------------------------------ */
  const Motion = {
    /** 用户是否要求减弱动效（系统级无障碍设置） */
    reduced() {
      return Boolean(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
    },
    /**
     * 数字滚动到目标值
     * @param {HTMLElement} el  容器（内部会生成 .countup 节点）
     * @param {number} target   目标数值
     * @param {{suffix?: string, duration?: number, formatter?: Function}} opts
     */
    countUp(el, target, opts = {}) {
      if (!el) return;
      const { suffix = '', duration = 720, formatter } = opts;
      const to = Number(target) || 0;
      const fmt = formatter || ((v) => Math.round(v).toLocaleString('zh-CN'));

      let num = el.querySelector('.countup');
      if (!num) {
        el.innerHTML = '<span class="countup"></span>' + (suffix ? `<small>${suffix}</small>` : '');
        num = el.querySelector('.countup');
      }

      if (Motion.reduced() || to === 0) {
        num.textContent = fmt(to);
        return;
      }

      // 用首帧的 rAF 时间戳做基准：performance.now() 与 rAF 时间戳在某些环境
      // （无头浏览器 / 虚拟时钟）基准不同，混用会算出负进度。
      let started = null;
      let done = false;

      const finalize = () => {
        if (done) return;
        done = true;
        num.textContent = fmt(to);
      };

      // 兜底：标签页在后台时 rAF 会被节流甚至暂停，靠计时器保证最终值正确
      const fallback = setTimeout(finalize, duration + 250);

      const step = (now) => {
        if (done) return;
        if (started === null) started = now;
        const progress = Math.min(1, Math.max(0, (now - started) / duration));
        const eased = 1 - Math.pow(1 - progress, 3);   // easeOutCubic
        num.textContent = fmt(to * eased);
        if (progress < 1) requestAnimationFrame(step);
        else { clearTimeout(fallback); finalize(); }
      };
      requestAnimationFrame(step);
    },
  };

  /* ------------------------------ 自定义下拉框 ------------------------------ */
  /**
   * 把原生 <select class="select"> 换成果壳。
   * 关键点：原生 select 仍留在 DOM 里（视觉隐藏），所以
   *   select.value / select.selectedIndex / select.dispatchEvent('change')
   * 这些既有写法全部不用改。
   */
  const Dropdown = (function () {
    const instances = new Map();
    let openInst = null;
    let pop = null;

    function ensurePop() {
      if (!pop) {
        pop = document.createElement('div');
        pop.className = 'dd__pop';
        pop.setAttribute('role', 'listbox');
        pop.hidden = true;
        document.body.appendChild(pop);
      }
      return pop;
    }

    function close() {
      if (!openInst) return;
      openInst.wrap.classList.remove('is-open');
      openInst.trigger.setAttribute('aria-expanded', 'false');
      const p = ensurePop();
      p.hidden = true;
      p.innerHTML = '';
      openInst = null;
    }

    function place(inst) {
      const p = ensurePop();
      const rect = inst.trigger.getBoundingClientRect();
      p.style.width = rect.width + 'px';
      p.style.left = Math.round(rect.left) + 'px';
      p.style.top = '0px';
      p.hidden = false;

      const height = p.offsetHeight;
      const below = window.innerHeight - rect.bottom;
      const top = (below < height + 12 && rect.top > height + 12)
        ? rect.top - height - 6
        : rect.bottom + 6;
      p.style.top = Math.round(top) + 'px';
    }

    function build(inst) {
      const p = ensurePop();
      const select = inst.select;
      p.innerHTML = '';

      if (!select.options.length) {
        p.innerHTML = '<div class="dd__empty">暂无可选项</div>';
        return;
      }

      Array.prototype.forEach.call(select.options, (opt, index) => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'dd__opt'
          + (index === select.selectedIndex ? ' is-selected' : '')
          + (opt.disabled ? ' is-disabled' : '');
        btn.disabled = opt.disabled;
        btn.setAttribute('role', 'option');
        btn.setAttribute('aria-selected', String(index === select.selectedIndex));
        btn.innerHTML = '<span class="dd__opt-label"></span><i class="fa-solid fa-check"></i>';
        btn.querySelector('.dd__opt-label').textContent = (opt.textContent || '').trim();
        btn.addEventListener('click', () => pick(inst, index));
        p.appendChild(btn);
      });
    }

    function pick(inst, index) {
      const select = inst.select;
      if (select.selectedIndex !== index) {
        select.selectedIndex = index;
        select.dispatchEvent(new Event('change', { bubbles: true }));
      }
      inst.refresh();
      close();
      inst.trigger.focus();
    }

    function open(inst) {
      if (openInst === inst) { close(); return; }
      close();
      openInst = inst;
      inst.wrap.classList.add('is-open');
      inst.trigger.setAttribute('aria-expanded', 'true');
      build(inst);
      place(inst);
      const current = pop.querySelector('.dd__opt.is-selected');
      if (current) current.scrollIntoView({ block: 'nearest' });
    }

    function enhance(select) {
      if (!select || select.dataset.dd === '1' || select.closest('.dd')) return null;

      const wrap = document.createElement('div');
      wrap.className = 'dd' + (select.classList.contains('select--sm') ? ' dd--sm' : '');
      // 沿用调用方设置的内联宽度（后台工具条里有 style="width:150px"）
      if (select.style.width) {
        wrap.style.width = select.style.width;
        select.style.width = '';
      }

      const trigger = document.createElement('button');
      trigger.type = 'button';
      trigger.className = 'dd__trigger';
      trigger.setAttribute('aria-haspopup', 'listbox');
      trigger.setAttribute('aria-expanded', 'false');
      trigger.innerHTML = '<span class="dd__value"></span><i class="fa-solid fa-chevron-down dd__chevron"></i>';

      select.parentNode.insertBefore(wrap, select);
      wrap.appendChild(select);
      wrap.appendChild(trigger);
      select.classList.add('dd__native');
      select.dataset.dd = '1';
      select.setAttribute('tabindex', '-1');

      const inst = {
        select,
        wrap,
        trigger,
        valueEl: trigger.querySelector('.dd__value'),
        refresh: null,
      };

      inst.refresh = function () {
        const opt = select.options[select.selectedIndex];
        inst.valueEl.textContent = opt ? (opt.textContent || '').trim() : '请选择';
        inst.valueEl.classList.toggle('is-placeholder', !opt || select.value === '');
        wrap.classList.toggle('is-disabled', !!select.disabled);
      };
      inst.refresh();

      trigger.addEventListener('click', (e) => {
        e.preventDefault();
        if (select.disabled) return;
        open(inst);
      });
      trigger.addEventListener('keydown', (e) => {
        if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
          e.preventDefault();
          open(inst);
        }
      });

      // 选项被外部 JS 重新填充时同步文案
      new MutationObserver(() => inst.refresh()).observe(select, { childList: true, subtree: true });

      instances.set(select, inst);
      return inst;
    }

    document.addEventListener('click', (e) => {
      if (!openInst) return;
      if (e.target.closest && (e.target.closest('.dd') || e.target.closest('.dd__pop'))) return;
      close();
    });
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') close();
    });
    window.addEventListener('resize', close);
    // 页面滚动时收起；但在弹层内部滚动选项列表不算
    window.addEventListener('scroll', (e) => {
      const t = e.target;
      if (t && t.closest && t.closest('.dd__pop')) return;
      close();
    }, true);

    // 列表重渲染、弹窗追加内容时会有新的 <select> 插入，
    // 靠一次性 enhanceAll() 会漏掉，这里用 MutationObserver 兜住。
    let watching = false;
    function watchDynamic() {
      if (watching || typeof MutationObserver === 'undefined') return;
      watching = true;

      let queued = false;
      const observer = new MutationObserver(() => {
        if (queued) return;
        queued = true;
        requestAnimationFrame(() => {
          queued = false;
          // 先做一次廉价判断，避免每次 DOM 变动都做全量查询
          if (!document.querySelector('select.select:not([data-dd])')) return;
          api.enhanceAll();
        });
      });
      observer.observe(document.body, { childList: true, subtree: true });
    }

    const api = {
      enhance,
      enhanceAll(root) {
        (root || document).querySelectorAll('select.select:not([data-dd])').forEach(enhance);
      },
      close,
      refreshAll() { instances.forEach((inst) => inst.refresh()); },
      watchDynamic,
    };

    return api;
  })();

  /* ------------------------------ 自定义日期选择 ------------------------------ */
  /**
   * 把原生 <input type="date"> 换成自定义日历。
   *
   * 和下拉框同一套思路：原生 input 保留在 DOM 里（视觉隐藏），只作为「值的容器」，
   * 所以既有的 input.value / dispatchEvent('change') 写法完全不用改。
   *
   * 原生日期控件丑且各浏览器长得不一样，也没法跟随主题走；自己画一个能保证
   * 明暗主题、圆角、间距和整站一致。
   */
  const DatePicker = (function () {
    const WEEK = ['日', '一', '二', '三', '四', '五', '六'];
    const instances = new Map();
    let pop = null;
    let current = null;

    const pad = (n) => String(n).padStart(2, '0');

    function toKey(d) {
      return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
    }

    function parseKey(v) {
      if (!v) return null;
      const parts = String(v).split('-').map(Number);
      if (parts.length !== 3 || parts.some((n) => Number.isNaN(n))) return null;
      return new Date(parts[0], parts[1] - 1, parts[2]);
    }

    function today() {
      const d = new Date();
      return new Date(d.getFullYear(), d.getMonth(), d.getDate());
    }

    function sameDay(a, b) {
      return !!a && !!b && a.getFullYear() === b.getFullYear()
        && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
    }

    function ensurePop() {
      if (pop) return pop;

      pop = document.createElement('div');
      pop.className = 'dp__pop';
      pop.setAttribute('role', 'dialog');
      pop.innerHTML = `
        <div class="dp__head">
          <button type="button" class="dp__nav" data-nav="-1" aria-label="上个月"><i class="fa-solid fa-chevron-left"></i></button>
          <button type="button" class="dp__title" data-nav="0"></button>
          <button type="button" class="dp__nav" data-nav="1" aria-label="下个月"><i class="fa-solid fa-chevron-right"></i></button>
        </div>
        <div class="dp__week">${WEEK.map((w) => `<span>${w}</span>`).join('')}</div>
        <div class="dp__grid" data-grid></div>
        <div class="dp__foot">
          <button type="button" class="dp__act" data-act="today">今天</button>
          <button type="button" class="dp__act dp__act--muted" data-act="clear">清除</button>
        </div>`;
      document.body.appendChild(pop);

      pop.addEventListener('click', (e) => {
        const nav = e.target.closest('[data-nav]');
        if (nav && current) {
          const step = Number(nav.dataset.nav);
          if (step === 0) {
            // 点标题回到当月
            const t = today();
            current.view = new Date(t.getFullYear(), t.getMonth(), 1);
          } else {
            current.view = new Date(current.view.getFullYear(), current.view.getMonth() + step, 1);
          }
          render();
          return;
        }

        const act = e.target.closest('[data-act]');
        if (act && current) {
          if (act.dataset.act === 'today') commit(today());
          if (act.dataset.act === 'clear') commit(null);
          return;
        }

        const cell = e.target.closest('[data-day]');
        if (cell && !cell.classList.contains('is-disabled')) {
          commit(parseKey(cell.dataset.day));
        }
      });

      return pop;
    }

    function isDisabled(date) {
      if (!current) return false;
      const { input } = current;
      const min = parseKey(input.min);
      const max = parseKey(input.max);
      if (min && date < min) return true;
      if (max && date > max) return true;
      return false;
    }

    function render() {
      if (!current || !pop) return;
      const { view, selected } = current;
      const year = view.getFullYear();
      const month = view.getMonth();

      pop.querySelector('.dp__title').textContent = `${year} 年 ${month + 1} 月`;

      const first = new Date(year, month, 1);
      const startOffset = first.getDay();
      const start = new Date(year, month, 1 - startOffset);

      const cells = [];
      const now = today();
      for (let i = 0; i < 42; i += 1) {
        const d = new Date(start.getFullYear(), start.getMonth(), start.getDate() + i);
        const classes = ['dp__day'];
        if (d.getMonth() !== month) classes.push('is-out');
        if (sameDay(d, now)) classes.push('is-today');
        if (sameDay(d, selected)) classes.push('is-selected');
        if (isDisabled(d)) classes.push('is-disabled');
        cells.push(`<button type="button" class="${classes.join(' ')}" data-day="${toKey(d)}">${d.getDate()}</button>`);
      }
      pop.querySelector('[data-grid]').innerHTML = cells.join('');
    }

    function place() {
      if (!current || !pop) return;
      const rect = current.trigger.getBoundingClientRect();
      const h = pop.offsetHeight || 320;
      const w = pop.offsetWidth || 280;

      let top = rect.bottom + 8;
      if (top + h > window.innerHeight - 8 && rect.top - h - 8 > 8) top = rect.top - h - 8;
      // 上下都放不下（小窗口）时贴底，至少别让底部按钮被切掉
      top = Math.max(8, Math.min(top, window.innerHeight - h - 8));

      let left = rect.left;
      if (left + w > window.innerWidth - 8) left = Math.max(8, window.innerWidth - w - 8);

      pop.style.top = `${Math.round(top)}px`;
      pop.style.left = `${Math.round(left)}px`;
    }

    function open(inst) {
      ensurePop();
      current = inst;
      const selected = parseKey(inst.input.value);
      const base = selected || today();
      inst.view = new Date(base.getFullYear(), base.getMonth(), 1);
      inst.selected = selected;

      pop.classList.add('is-open');
      render();
      // 先放到可见位置再量尺寸，避免第一次打开时位置跳一下
      pop.style.top = '-9999px';
      pop.style.left = '-9999px';
      place();
      current.trigger.classList.add('is-open');
      current.wrap.classList.add('is-open');
    }

    function close() {
      if (!pop) return;
      pop.classList.remove('is-open');
      if (current) {
        current.trigger.classList.remove('is-open');
        current.wrap.classList.remove('is-open');
      }
      current = null;
    }

    function commit(date) {
      if (!current) return;
      const { input, label } = current;
      input.value = date ? toKey(date) : '';
      label.textContent = date ? toKey(date) : (input.dataset.placeholder || '选择日期');
      label.classList.toggle('is-empty', !date);

      input.dispatchEvent(new Event('input', { bubbles: true }));
      input.dispatchEvent(new Event('change', { bubbles: true }));
      close();
    }

    function sync(inst) {
      const d = parseKey(inst.input.value);
      inst.label.textContent = d ? toKey(d) : (inst.input.dataset.placeholder || '选择日期');
      inst.label.classList.toggle('is-empty', !d);
    }

    function enhance(input) {
      if (!input || input.dataset.dp === '1') return null;
      input.dataset.dp = '1';

      const wrap = document.createElement('div');
      wrap.className = 'dp' + (input.classList.contains('input--sm') ? ' dp--sm' : '');
      if (input.style.width) wrap.style.width = input.style.width;

      input.classList.add('dp__native');
      input.parentNode.insertBefore(wrap, input);
      wrap.appendChild(input);

      const trigger = document.createElement('button');
      trigger.type = 'button';
      trigger.className = 'dp__trigger';
      trigger.innerHTML = '<i class="fa-regular fa-calendar"></i><span class="dp__label"></span>';

      const label = trigger.querySelector('.dp__label');
      wrap.appendChild(trigger);

      const inst = { input, wrap, trigger, label, view: null, selected: null };
      instances.set(input, inst);
      sync(inst);

      // 原生 input 自己也可能被程序改值（重置筛选），这里跟着同步显示
      input.addEventListener('change', () => sync(inst));

      trigger.addEventListener('click', () => {
        if (current && current.input === input) close();
        else open(inst);
      });

      input.addEventListener('focus', () => open(inst));
      return inst;
    }

    document.addEventListener('click', (e) => {
      if (!current) return;
      const t = e.target;
      if (t.closest && (t.closest('.dp__pop') || t.closest('.dp'))) return;
      close();
    }, true);

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') close();
    });

    window.addEventListener('resize', () => { if (current) close(); });
    window.addEventListener('scroll', () => { if (current) close(); }, true);

    let watching = false;
    function watchDynamic() {
      if (watching || typeof MutationObserver === 'undefined') return;
      watching = true;

      let queued = false;
      const observer = new MutationObserver(() => {
        if (queued) return;
        queued = true;
        requestAnimationFrame(() => {
          queued = false;
          if (!document.querySelector('input[type="date"]:not([data-dp])')) return;
          api.enhanceAll();
        });
      });
      observer.observe(document.body, { childList: true, subtree: true });
    }

    const api = {
      enhance,
      enhanceAll(root) {
        (root || document).querySelectorAll('input[type="date"]:not([data-dp])').forEach(enhance);
      },
      close,
      watchDynamic,
      refreshAll() { instances.forEach(sync); },
    };

    return api;
  })();

  /* ------------------------------ 启动 ------------------------------ */
  Theme.init();

  document.addEventListener('DOMContentLoaded', () => {
    Modal.bind();
    initNav();
    Dropdown.enhanceAll();
    Dropdown.watchDynamic();
    DatePicker.enhanceAll();
    DatePicker.watchDynamic();
  });

  window.RP = { Theme, Toast, Modal, api, ApiError, util, Session, Dropdown, DatePicker, Motion, countUp: Motion.countUp, renderThread, PREFIX };
})();
