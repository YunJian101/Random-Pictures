/**
 * 登录 / 注册页
 *
 * 从页面内联脚本抽出，逻辑未改动；HTML 只保留结构。
 */
document.addEventListener('DOMContentLoaded', function () {
  'use strict';

  const { api, Toast, util } = window.RP;
  const $ = (id) => document.getElementById(id);

  /* ------------------------------ 站点信息 ------------------------------ */
  (async function loadSiteInfo() {
    try {
      const res = await api('/api/system/info');
      const d = (res && res.data) || {};
      if (d.site_name) {
        document.title = `登录 · ${d.site_name}`;
        document.querySelectorAll('[data-site-name]').forEach((el) => { el.textContent = d.site_name; });
      }
      if (d.favicon_url) $('favicon').href = d.favicon_url;
    } catch (e) { /* 静默：站点信息不影响登录 */ }
  })();

  $('year').textContent = new Date().getFullYear();

  /* ------------------------------ 标签切换 ------------------------------ */
  const tabLogin = $('tab-login');
  const tabRegister = $('tab-register');
  const formLogin = $('login-form');
  const formRegister = $('register-form');
  const authFoot = $('auth-foot');

  function switchTab(mode) {
    const isLogin = mode === 'login';
    tabLogin.classList.toggle('is-active', isLogin);
    tabRegister.classList.toggle('is-active', !isLogin);
    formLogin.classList.toggle('hidden', !isLogin);
    formRegister.classList.toggle('hidden', isLogin);
    authFoot.classList.toggle('hidden', !isLogin);

    $('auth-title').textContent = isLogin ? '欢迎回来' : '创建账号';
    $('auth-subtitle').textContent = isLogin
      ? '登录你的账号以继续管理图片与反馈'
      : '注册后即可提交反馈、查看处理进度';

    clearAllErrors();
    const first = isLogin ? $('login-account') : $('register-username');
    if (first) setTimeout(() => first.focus(), 60);
  }

  tabLogin.addEventListener('click', () => switchTab('login'));
  tabRegister.addEventListener('click', () => switchTab('register'));
  $('go-register').addEventListener('click', () => switchTab('register'));

  /* ------------------------------ 错误提示 ------------------------------ */
  function showError(id, message) {
    const el = $(id);
    if (!el) return;
    el.textContent = message;
    el.classList.remove('hidden');
  }

  function clearError(id) {
    const el = $(id);
    if (!el) return;
    el.textContent = '';
    el.classList.add('hidden');
  }

  function clearAllErrors() {
    document.querySelectorAll('.field-error').forEach((el) => {
      el.textContent = '';
      el.classList.add('hidden');
    });
  }

  // 输入时清除该字段的错误
  document.querySelectorAll('input').forEach((input) => {
    input.addEventListener('input', () => clearError(`${input.id}-error`));
  });

  /* ------------------------------ 密码强度 ------------------------------ */
  const pwdInput = $('register-password');
  const strengthFill = $('strength-fill');
  const strengthText = $('strength-text');

  pwdInput.addEventListener('input', () => {
    const pwd = pwdInput.value;
    let score = 0;
    if (pwd.length >= 6) score += 1;
    if (pwd.length >= 10) score += 1;
    if (/[a-zA-Z]/.test(pwd) && /[0-9]/.test(pwd)) score += 1;
    if (/[^a-zA-Z0-9]/.test(pwd)) score += 1;

    const levels = [
      { width: '0%', color: 'var(--surface-3)', text: '密码强度' },
      { width: '28%', color: 'var(--danger)', text: '偏弱' },
      { width: '56%', color: 'var(--warn)', text: '一般' },
      { width: '80%', color: 'var(--accent)', text: '较强' },
      { width: '100%', color: 'var(--success)', text: '很强' },
    ];
    const level = levels[Math.min(score, 4)];
    strengthFill.style.width = level.width;
    strengthFill.style.background = level.color;
    strengthText.textContent = pwd ? level.text : '密码强度';
  });

  /* ------------------------------ 提交态 ------------------------------ */
  function setLoading(btn, loading, label) {
    btn.disabled = loading;
    btn.innerHTML = loading ? '<div class="spinner" style="border-top-color:#fff;border-color:rgba(255,255,255,.35);border-top-color:#fff"></div>处理中…' : label;
  }

  /* ------------------------------ 登录 ------------------------------ */
  formLogin.addEventListener('submit', async (e) => {
    e.preventDefault();
    clearAllErrors();

    const account = $('login-account').value.trim();
    const password = $('login-password').value;
    let ok = true;

    if (!account) { showError('login-account-error', '请输入用户名或邮箱'); ok = false; }
    if (password.length < 6) { showError('login-password-error', '密码至少 6 位'); ok = false; }
    if (!ok) return;

    const btn = $('login-submit');
    setLoading(btn, true);

    try {
      const res = await api('/api/login', {
        method: 'POST',
        body: { account, password, remember: $('remember-me').checked },
      });
      const user = res && res.data && res.data.user;
      window.RP.Session.setLocal(user);
      Toast.success(`欢迎回来，${user ? user.username : account}`);

      let redirect = '/';
      try {
        const pending = sessionStorage.getItem('redirect_after_login');
        if (pending) { redirect = pending; sessionStorage.removeItem('redirect_after_login'); }
        else if (user && user.role === 'admin') redirect = '/admin-panel';
        else if (user && user.role !== 'admin') redirect = '/';
      } catch (err) { /* noop */ }

      setTimeout(() => { window.location.href = redirect; }, 420);
    } catch (err) {
      setLoading(btn, false, '登录');
      if (err.status === 401) showError('login-password-error', err.message || '账号或密码不正确');
      else if (err.status === 422) showError('login-account-error', '请输入有效的账号与密码');
      else Toast.error(err.message || '登录失败，请稍后重试');
    }
  });

  /* ------------------------------ 注册 ------------------------------ */
  formRegister.addEventListener('submit', async (e) => {
    e.preventDefault();
    clearAllErrors();

    const username = $('register-username').value.trim();
    const email = $('register-email').value.trim();
    const password = $('register-password').value;
    const confirm = $('register-confirm').value;
    let ok = true;

    if (!/^[a-zA-Z0-9_]{3,16}$/.test(username)) {
      showError('register-username-error', '用户名需为 3-16 位字母、数字或下划线');
      ok = false;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      showError('register-email-error', '请输入有效的邮箱地址');
      ok = false;
    }
    if (password.length < 6) {
      showError('register-password-error', '密码至少 6 位');
      ok = false;
    }
    if (confirm !== password) {
      showError('register-confirm-error', '两次输入的密码不一致');
      ok = false;
    }
    if (!ok) return;

    const btn = $('register-submit');
    setLoading(btn, true);

    try {
      const res = await api('/api/register', {
        method: 'POST',
        body: { username, email, password },
      });
      const isAdmin = res && res.data && res.data.role === 'admin';
      window.RP.Toast.success(isAdmin ? '注册成功，你已成为管理员' : '注册成功，请登录');
      setTimeout(() => {
        $('login-account').value = username;
        $('login-password').value = '';
        switchTab('login');
      }, 600);
    } catch (err) {
      setLoading(btn, false, '创建账号');
      const msg = err.message || '注册失败，请稍后重试';
      if (msg.includes('用户名')) showError('register-username-error', msg);
      else if (msg.includes('邮箱')) showError('register-email-error', msg);
      else Toast.error(msg);
    }
  });

  /* ------------------------------ 其它 ------------------------------ */
  $('forgot-link').addEventListener('click', () => {
    Toast.info('请联系站点管理员重置密码');
  });

  // 已登录用户直接跳走，避免重复登录
  (async function redirectIfLoggedIn() {
    const user = await window.RP.Session.verify();
    if (!user) return;
    window.location.href = user.role === 'admin' ? '/admin-panel' : '/';
  })();
});
