/**
 * 管理后台 · 入口
 *
 * 只做三件事：把各视图的加载函数注册进 core、绑定 hashchange、跑一次初始化。
 */
import { $, TITLES, initSession, registerView, showView, state } from './core.js';
import { loadOverview } from './overview.js';
import { loadCategories } from './categories.js';
import { loadImages } from './images.js';
import { loadUsers } from './users.js';
import { loadFeedbacks } from './feedbacks.js';
import { loadConfig } from './settings.js';
import { loadAudit } from './audit.js';
import { loadVersion } from './update.js';

registerView('overview', loadOverview);
registerView('categories', loadCategories);
registerView('images', loadImages);
registerView('users', loadUsers);
registerView('feedbacks', loadFeedbacks);
registerView('settings', loadConfig);
registerView('audit', loadAudit);
registerView('update', loadVersion);

/* ============================== 启动 ============================== */
window.addEventListener('hashchange', () => {
  const name = location.hash.replace('#', '');
  if (name && TITLES[name]) showView(name);
});

(async function init() {
  const user = await initSession();
  if (!user) return;
  const initial = location.hash.replace('#', '');
  if (initial && TITLES[initial]) {
    showView(initial);
  } else {
    await loadOverview();
  }
})();
