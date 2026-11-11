/**
 * 管理后台 · 总览：KPI、分布图、最近动态
 */

import { $, state, api, Toast, util, countUp } from './core.js';
import { fillCategorySelects } from './categories.js';

/* ============================== 总览 ============================== */
export async function loadOverview() {
  try {
    const [statsRes, catsRes] = await Promise.all([
      api('/api/admin/stats'),
      api('/api/admin/categories'),
    ]);
    const s = (statsRes && statsRes.data) || {};
    const images = s.images || {};
    const categories = s.categories || {};
    const users = s.users || {};
    const feedbacks = s.feedbacks || {};

    countUp($('kpi-images'), images.total || 0, { suffix: '张' });
    $('kpi-images-foot').innerHTML = `<i class="fa-solid fa-hard-drive"></i>占用 ${util.formatBytes(images.total_size || 0)}`;
    countUp($('kpi-categories'), categories.total || 0, { suffix: '个' });
    $('kpi-categories-foot').innerHTML = `<i class="fa-solid fa-eye"></i>累计访问 ${(images.views || 0).toLocaleString('zh-CN')}`;
    countUp($('kpi-users'), users.total || 0, { suffix: '人' });
    $('kpi-users-foot').innerHTML = users.banned
      ? `<i class="fa-solid fa-ban" style="color:var(--danger)"></i>已封禁 ${users.banned} 人`
      : '<i class="fa-solid fa-circle-check" style="color:var(--success)"></i>暂无封禁';
    countUp($('kpi-feedbacks'), feedbacks.pending || 0, { suffix: '条' });
    $('kpi-feedbacks-foot').innerHTML = `共 ${feedbacks.total || 0} 条反馈`;

    const pending = feedbacks.pending || 0;
    const badge = $('nav-fb-badge');
    badge.textContent = pending;
    badge.classList.toggle('hidden', pending === 0);
    // 安全事件：近 24 小时的越权/限流/非法请求。有就在侧栏亮红点，没有就不打扰
    const security = s.security || {};
    const secCount = security.last_24h || 0;
    const auditBadge = $('nav-audit-badge');
    if (auditBadge) {
      auditBadge.textContent = secCount > 99 ? '99+' : String(secCount);
      auditBadge.classList.toggle('hidden', secCount === 0);
    }

    const parts = [];
    parts.push(pending ? `有 ${pending} 条反馈待处理` : '暂无待处理反馈');
    parts.push(`图片库共 ${(images.total || 0).toLocaleString('zh-CN')} 张`);
    if (secCount > 0) parts.push(`近 24 小时 ${secCount} 起异常请求`);
    $('overview-hint').textContent = parts.join('，') + '。';

    state.categories = (catsRes && catsRes.data && catsRes.data.categories) || [];
    fillCategorySelects();

    const cats = state.categories
      .filter((c) => (c.image_count || 0) > 0)
      .sort((a, b) => b.image_count - a.image_count);
    const totalImages = Math.max(1, images.total || cats.reduce((sum, c) => sum + c.image_count, 0) || 0);
    const top = cats.slice(0, 3);
    const others = cats.slice(3).reduce((sum, c) => sum + c.image_count, 0);
    const segments = top.map((c, i) => ({
      label: c.name,
      value: c.image_count,
      color: ['var(--primary)', 'color-mix(in srgb, var(--primary) 55%, var(--accent))', 'var(--accent)'][i],
    }));
    if (others > 0) segments.push({ label: '其他分类', value: others, color: 'var(--surface-3)' });

    const donut = $('overview-donut');
    let acc = 0;
    segments.forEach((seg, i) => {
      acc += (seg.value / totalImages) * 100;
      donut.style.setProperty(`--p${i + 1}`, `${Math.min(100, acc).toFixed(2)}%`);
    });
    for (let i = segments.length; i < 4; i += 1) donut.style.setProperty(`--p${i + 1}`, '0%');
    countUp($('donut-total'), images.total || 0);
    $('overview-legend').innerHTML = segments.length
      ? segments.map((seg) => `<div class="legend__item">
          <span class="legend__dot" style="background:${seg.color}"></span>
          <span class="truncate">${util.escapeHtml(seg.label)}</span>
          <span class="legend__value">${seg.value.toLocaleString('zh-CN')}</span>
        </div>`).join('')
      : '<span class="tiny dim">暂无分类数据</span>';
  } catch (e) {
    Toast.error(e.message || '总览数据加载失败');
  }
}

