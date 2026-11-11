/**
 * 前端模块图自检
 * ==============
 *
 * 目的：在没有浏览器的环境（CI / 本地随手跑）里确认管理后台的 ES 模块
 * 「导入导出对得上、顶层代码不报错」。用最小的 DOM / window 桩把
 * core.js 的顶层逻辑跑一遍，能抓到这几类问题：
 *
 *   - 导入了不存在的成员（浏览器里是 SyntaxError，整页白屏）
 *   - 模块之间循环引用导致的初始化未完成
 *   - 顶层代码引用了不存在的 DOM 节点方法
 *
 * 用法：node scripts/check-frontend-modules.mjs
 */

const stubs = () => ({
  addEventListener() {},
  removeEventListener() {},
  classList: { add() {}, remove() {}, toggle() {}, contains: () => false },
  style: {},
  dataset: {},
  children: [],
  value: '',
  textContent: '',
  innerHTML: '',
  checked: false,
  appendChild() {},
  removeChild() {},
  remove() {},
  setAttribute() {},
  getAttribute: () => null,
  focus() {},
  blur() {},
  closest: () => null,
  querySelector: () => stubs(),
  querySelectorAll: () => [],
  insertAdjacentHTML() {},
});

const el = stubs;

globalThis.document = {
  getElementById: () => el(),
  querySelector: () => el(),
  querySelectorAll: () => [],
  createElement: () => el(),
  addEventListener() {},
  documentElement: el(),
  body: el(),
  head: el(),
};

const location = { hash: '', href: '', pathname: '/admin-panel', search: '' };

globalThis.window = {
  RP: {
    api: async () => ({ code: 200, data: {} }),
    ApiError: class extends Error {},
    Toast: { error() {}, success() {}, info() {}, warn() {} },
    Modal: { open() {}, close() {}, confirm: async () => false },
    util: {
      confirm: async () => false,
      escapeHtml: (s) => String(s ?? ''),
      debounce: (fn) => fn,
      formatDate: () => '',
      formatSize: () => '',
    },
    Session: {
      verify: async () => null,
      setLocal() {},
      getLocal: () => null,
      logout() {},
    },
    Dropdown: { enhance() {}, enhanceAll() {}, watchDynamic() {} },
    Motion: { reduced: () => true },
    Theme: { init() {}, toggle() {} },
    countUp() {},
    renderThread() {},
  },
  addEventListener() {},
  removeEventListener() {},
  matchMedia: () => ({ matches: false, addEventListener() {} }),
  scrollTo() {},
  location,
  history: { replaceState() {}, pushState() {} },
  localStorage: { getItem: () => null, setItem() {}, removeItem() {} },
  sessionStorage: { getItem: () => null, setItem() {}, removeItem() {} },
  getComputedStyle: () => ({ getPropertyValue: () => '' }),
};

globalThis.location = location;
globalThis.history = window.history;
globalThis.localStorage = window.localStorage;
globalThis.sessionStorage = window.sessionStorage;
globalThis.requestAnimationFrame = (fn) => setTimeout(() => fn(Date.now()), 0);
globalThis.cancelAnimationFrame = () => {};
globalThis.fetch = async () => ({ ok: true, json: async () => ({}) });

const MODULES = [
  'core.js',
  'overview.js',
  'categories.js',
  'images.js',
  'users.js',
  'feedbacks.js',
  'settings.js',
  'audit.js',
  'update.js',
  'index.js',
];

const base = new URL('../frontend/static/pages/admin/', import.meta.url);
let failed = 0;

for (const name of MODULES) {
  try {
    await import(new URL(name, base).href);
    console.log(`  \u2713 ${name}`);
  } catch (err) {
    failed += 1;
    console.error(`  \u2717 ${name}: ${err.message}`);
  }
}

if (failed) {
  console.error(`\n${failed} 个模块加载失败`);
  process.exit(1);
}
console.log('\n\u5168\u90e8\u6a21\u5757\u52a0\u8f7d\u6b63\u5e38');
