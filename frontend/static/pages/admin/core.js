/**
 * 管理后台 · 核心壳层
 *
 * 侧栏切换、会话校验、分页控件、视图注册表。
 * 依赖方向固定为「视图 → core」，不会出现循环引用。
 */

const { api, Toast, Modal, util, Session, countUp, renderThread } = window.RP;
export { api, Toast, Modal, util, Session, countUp, renderThread };

export const $ = (id) => document.getElementById(id);

export const TITLES = {
  overview: ['数据总览', '站点运行情况一览'],
  images: ['图片管理', '上传、整理与批量维护图片资源'],
  categories: ['分类管理', '分类是 /random?type= 的参数来源'],
  users: ['用户管理', '账号、角色与封禁状态'],
  feedbacks: ['反馈管理', '查看并回复用户反馈'],
  audit: ['审核日志', '谁在什么时候对什么做了什么'],
  settings: ['系统设置', '站点信息与功能开关'],
  update: ['版本更新', '检查新版本、查看备份与回滚'],
};

export const STATUS = {
  pending: { label: '待处理', cls: 'badge--warn' },
  processing: { label: '处理中', cls: 'badge--accent' },
  resolved: { label: '已解决', cls: 'badge--success' },
  closed: { label: '已关闭', cls: 'badge--muted' },
};

export const state = {
  view: 'overview',
  categories: [],
  images: { page: 1, totalPages: 1, total: 0, category: '', keyword: '', sort: 'created_desc', selected: new Set(), items: [] },
  users: [],
  feedbacks: [],
  loaded: {},
};

/* ============================== 侧栏 ============================== */
const VIEW_LOADERS = {};

/** 视图模块在入口处注册自己的加载函数，core 不反向 import 视图 */
export function registerView(name, loader) {
  VIEW_LOADERS[name] = loader;
}

export function showView(name) {
  state.view = name;
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
  window.scrollTo({ top: 0, behavior: 'smooth' });

  if (location.hash !== '#' + name) {
    history.replaceState(null, '', '#' + name);
  }
  const loader = VIEW_LOADERS[name];
  if (loader) loader();
}

document.querySelectorAll('.sidebar__item[data-view]').forEach((btn) => {
  btn.addEventListener('click', () => showView(btn.dataset.view));
});
document.querySelectorAll('[data-go]').forEach((btn) => {
  btn.addEventListener('click', () => showView(btn.dataset.go));
});

export function closeSidebar() {
  $('sidebar').classList.remove('is-open');
  document.querySelector('.sidebar-overlay').classList.remove('is-open');
}
document.querySelector('[data-sidebar-toggle]').addEventListener('click', () => {
  $('sidebar').classList.add('is-open');
  document.querySelector('.sidebar-overlay').classList.add('is-open');
});
document.querySelector('[data-sidebar-close]').addEventListener('click', closeSidebar);

$('refresh-btn').addEventListener('click', () => showView(state.view));

/* ============================== 会话 ============================== */
export async function initSession() {
  const user = await Session.verify();
  if (!user) {
    try { sessionStorage.setItem('redirect_after_login', '/admin-panel'); } catch (e) { /* noop */ }
    window.location.href = '/login';
    return null;
  }
  if (user.role !== 'admin') {
    Toast.error('当前账号没有管理员权限');
    setTimeout(() => { window.location.href = '/user-panel'; }, 900);
    return null;
  }
  Session.setLocal(user);
  $('side-username').textContent = user.username;
  $('avatar').textContent = (user.username || 'A').slice(0, 1).toUpperCase();
  $('hello-name').textContent = user.username;
  return user;
}

$('logout-btn').addEventListener('click', async () => {
  const ok = await util.confirm('退出登录', '确定要退出当前账号吗？', '退出');
  if (ok) Session.logout('/');
});

/* ============================== 分页 ============================== */
export function renderPagination(host, current, total, onGo) {
  host.innerHTML = '';
  const mk = (html, page, disabled, active) => {
    const btn = document.createElement('button');
    btn.className = 'pagination__btn';
    btn.innerHTML = html;
    btn.disabled = !!disabled;
    if (active) { btn.style.borderColor = 'var(--primary)'; btn.style.color = 'var(--primary)'; }
    if (!disabled && !active) btn.addEventListener('click', () => onGo(page));
    return btn;
  };
  host.appendChild(mk('<i class="fa-solid fa-chevron-left"></i>', current - 1, current <= 1));
  const pages = [1, current - 1, current, current + 1, total]
    .filter((p) => p >= 1 && p <= total)
    .filter((p, i, arr) => arr.indexOf(p) === i)
    .sort((a, b) => a - b);
  let prev = 0;
  pages.forEach((p) => {
    if (prev && p - prev > 1) {
      const dots = document.createElement('span');
      dots.className = 'pagination__btn';
      dots.style.cursor = 'default';
      dots.textContent = '…';
      host.appendChild(dots);
    }
    host.appendChild(mk(String(p), p, false, p === current));
    prev = p;
  });
  host.appendChild(mk('<i class="fa-solid fa-chevron-right"></i>', current + 1, current >= total));
}

