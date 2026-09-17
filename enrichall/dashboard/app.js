const PROVIDERS = ['apollo', 'hunter', 'snov', 'rocketreach', 'prospeo', 'dropcontact'];

const state = {
  token: localStorage.getItem('enrichall_token') || '',
  user: JSON.parse(localStorage.getItem('enrichall_user') || 'null'),
  route: location.hash.slice(1) || (localStorage.getItem('enrichall_token') ? '/' : '/login')
};

const app = document.getElementById('app');

function api(path, options = {}) {
  return fetch(path, {
    ...options,
    headers: {
      ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...(state.token ? { Authorization: `Bearer ${state.token}` } : {}),
      ...(options.headers || {})
    }
  }).then(async res => {
    const isJson = res.headers.get('content-type')?.includes('application/json');
    const body = isJson ? await res.json() : await res.text();
    if (!res.ok) throw new Error(body?.error || body || `Request failed: ${res.status}`);
    return body;
  });
}

function navigate(route) {
  state.route = route;
  location.hash = route;
  render();
}

window.addEventListener('hashchange', () => {
  state.route = location.hash.slice(1) || '/';
  render();
});

function shell(content) {
  app.innerHTML = `
    <div class="app-shell">
      <aside class="sidebar">
        <div class="brand">
          <div class="brand-mark">E</div>
          <div>
            <p class="brand-title">Enrichall</p>
            <p class="brand-subtitle">Recruiter enrichment waterfall</p>
          </div>
        </div>
        <nav class="nav">
          ${navButton('/', 'Overview')}
          ${navButton('/providers', 'Providers')}
          ${navButton('/enrich', 'Single lookup')}
          ${navButton('/batch', 'CSV batch')}
          ${navButton('/history', 'History')}
        </nav>
      </aside>
      <main class="main">
        <div class="topbar">
          <div>
            <h1 class="page-title">${pageTitle()}</h1>
            <p class="page-kicker">Bring your own API keys. Enrichall handles the waterfall.</p>
          </div>
          <button class="user-pill" id="logoutBtn">${state.user?.email || 'Signed in'} · Logout</button>
        </div>
        ${content}
      </main>
    </div>
  `;
  document.getElementById('logoutBtn').onclick = logout;
}

function navButton(route, label) {
  return `<button class="${state.route === route ? 'active' : ''}" data-route="${route}" onclick="window.enrichallNavigate('${route}')">${label}</button>`;
}

window.enrichallNavigate = navigate;

function pageTitle() {
  return {
    '/': 'Dashboard',
    '/providers': 'Providers',
    '/enrich': 'Single lookup',
    '/batch': 'CSV batch',
    '/history': 'History'
  }[state.route] || 'Dashboard';
}

function authPage(mode = 'login') {
  const isLogin = mode === 'login';
  app.innerHTML = `
    <div class="auth-wrap">
      <div class="card auth-card">
        <div class="brand">
          <div class="brand-mark">E</div>
          <div>
            <p class="brand-title">Enrichall</p>
            <p class="brand-subtitle">${isLogin ? 'Welcome back' : 'Create your recruiter workspace'}</p>
          </div>
        </div>
        <form class="form" id="authForm">
          <input class="input" name="email" type="email" placeholder="Email" required />
          <input class="input" name="password" type="password" placeholder="Password" minlength="6" required />
          <button class="button">${isLogin ? 'Login' : 'Create account'}</button>
        </form>
        <p class="notice">
          ${isLogin ? 'No account?' : 'Already have an account?'}
          <button class="link-button" id="switchAuth">${isLogin ? 'Sign up' : 'Login'}</button>
        </p>
        <p class="notice" id="authNotice"></p>
      </div>
    </div>
  `;

  document.getElementById('switchAuth').onclick = () => navigate(isLogin ? '/signup' : '/login');
  document.getElementById('authForm').onsubmit = async event => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      const data = await api(`/api/auth/${isLogin ? 'login' : 'signup'}`, {
        method: 'POST',
        body: JSON.stringify({
          email: form.get('email'),
          password: form.get('password')
        })
      });
      if (!data.session?.access_token) {
        document.getElementById('authNotice').textContent = 'Check your email to confirm signup, then login.';
        return;
      }
      state.token = data.session.access_token;
      state.user = data.user;
      localStorage.setItem('enrichall_token', state.token);
      localStorage.setItem('enrichall_user', JSON.stringify(state.user));
      navigate('/');
    } catch (err) {
      document.getElementById('authNotice').textContent = err.message;
    }
  };
}

function logout() {
  localStorage.removeItem('enrichall_token');
  localStorage.removeItem('enrichall_user');
  state.token = '';
  state.user = null;
  navigate('/login');
}

async function dashboardPage() {
  shell(`<div class="grid grid-3" id="statsGrid">${statSkeleton()}</div>`);
  try {
    const stats = await api('/api/stats');
    document.getElementById('statsGrid').innerHTML = `
      ${statCard('Lookups today', stats.lookupsToday)}
      ${statCard('Total enriched', stats.totalEnriched)}
      ${statCard('Cache hit rate', `${stats.cacheHitRate}%`)}
    `;
  } catch (err) {
    document.getElementById('statsGrid').innerHTML = `<div class="card">Unable to load stats: ${err.message}</div>`;
  }
}

function statSkeleton() {
  return `${statCard('Lookups today', '...')}${statCard('Total enriched', '...')}${statCard('Cache hit rate', '...')}`;
}

function statCard(label, value) {
  return `<div class="card"><div class="muted">${label}</div><div class="stat-value">${value}</div></div>`;
}

async function providersPage() {
  shell(`<div class="grid grid-2" id="providersGrid"></div>`);
  let configured = [];
  try {
    configured = (await api('/api/providers')).providers || [];
  } catch {}
  const map = Object.fromEntries(configured.map(p => [p.provider, p]));
  document.getElementById('providersGrid').innerHTML = PROVIDERS.map((provider, index) => `
    <div class="card provider-card">
      <div class="provider-head">
        <h3 class="provider-name">${provider}</h3>
        <span class="status-pill">${map[provider]?.is_active ? 'Active' : 'Not configured'}</span>
      </div>
      <input class="input" id="${provider}Key" type="password" placeholder="${provider === 'snov' ? 'clientId:clientSecret' : 'API key'}" />
      <input class="input" id="${provider}Priority" type="number" value="${map[provider]?.priority ?? index}" min="0" />
      <div class="grid grid-2">
        <button class="button" onclick="saveProvider('${provider}')">Save</button>
        <button class="button secondary" onclick="testProvider('${provider}')">Test</button>
      </div>
      <p class="notice" id="${provider}Notice"></p>
    </div>
  `).join('');
}

window.saveProvider = async provider => {
  const notice = document.getElementById(`${provider}Notice`);
  try {
    await api('/api/providers', {
      method: 'POST',
      body: JSON.stringify({
        provider,
        apiKey: document.getElementById(`${provider}Key`).value,
        priority: Number(document.getElementById(`${provider}Priority`).value || 0),
        isActive: true
      })
    });
    notice.textContent = 'Saved.';
  } catch (err) {
    notice.textContent = err.message;
  }
};

window.testProvider = async provider => {
  const notice = document.getElementById(`${provider}Notice`);
  try {
    await api('/api/providers/test', {
      method: 'POST',
      body: JSON.stringify({
        provider,
        apiKey: document.getElementById(`${provider}Key`).value
      })
    });
    notice.textContent = 'Key works.';
  } catch (err) {
    notice.textContent = err.message;
  }
};

function enrichPage() {
  shell(`
    <div class="card">
      <form class="form" id="enrichForm">
        <input class="input" name="linkedinUrl" placeholder="LinkedIn URL" />
        <div class="grid grid-2">
          <input class="input" name="firstName" placeholder="First name" />
          <input class="input" name="lastName" placeholder="Last name" />
        </div>
        <div class="grid grid-2">
          <input class="input" name="company" placeholder="Company" />
          <input class="input" name="domain" placeholder="Domain" />
        </div>
        <button class="button">Find email</button>
      </form>
      <div id="enrichResult"></div>
    </div>
  `);

  document.getElementById('enrichForm').onsubmit = async event => {
    event.preventDefault();
    const form = Object.fromEntries(new FormData(event.currentTarget));
    const resultEl = document.getElementById('enrichResult');
    resultEl.innerHTML = `<div class="result empty">Searching waterfall...</div>`;
    try {
      const result = await api('/api/enrich', {
        method: 'POST',
        body: JSON.stringify(form)
      });
      resultEl.innerHTML = `
        <div class="result ${result.email ? '' : 'empty'}">
          <strong>${result.email || 'No email found'}</strong>
          <p class="muted">Source: ${result.source || 'none'} · Cache: ${result.cacheHit ? 'hit' : 'miss'}</p>
          <p class="muted">${(result.providersTried || []).map(p => `${p.provider}: ${p.status}`).join(' · ')}</p>
        </div>
      `;
    } catch (err) {
      resultEl.innerHTML = `<div class="result empty">${err.message}</div>`;
    }
  };
}

function batchPage() {
  shell(`
    <div class="card">
      <form class="form" id="batchForm">
        <input class="input" name="file" type="file" accept=".csv,text/csv" required />
        <button class="button">Upload CSV</button>
      </form>
      <div id="batchStatus" class="notice"></div>
    </div>
  `);

  document.getElementById('batchForm').onsubmit = async event => {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const statusEl = document.getElementById('batchStatus');
    statusEl.innerHTML = 'Uploading...';
    try {
      const { job } = await api('/api/enrich/batch', { method: 'POST', body: formData });
      pollJob(job.id, statusEl);
    } catch (err) {
      statusEl.textContent = err.message;
    }
  };
}

async function pollJob(jobId, el) {
  const interval = setInterval(async () => {
    try {
      const { job } = await api(`/api/jobs/${jobId}`);
      const pct = job.total_rows ? Math.round((job.processed_rows / job.total_rows) * 100) : 0;
      el.innerHTML = `
        <p>Status: ${job.status} · ${job.processed_rows}/${job.total_rows} · Found ${job.found_emails}</p>
        <div class="progress"><span style="width:${pct}%"></span></div>
        ${job.result_csv_url ? `<p><a class="button" href="/api/jobs/${job.id}/download">Download CSV</a></p>` : ''}
        ${job.error_message ? `<p>${job.error_message}</p>` : ''}
      `;
      if (['complete', 'failed'].includes(job.status)) clearInterval(interval);
    } catch (err) {
      el.textContent = err.message;
      clearInterval(interval);
    }
  }, 1500);
}

async function historyPage() {
  shell(`<div class="card"><table class="table" id="jobsTable"><tbody><tr><td>Loading...</td></tr></tbody></table></div>`);
  try {
    const { jobs } = await api('/api/jobs');
    document.getElementById('jobsTable').innerHTML = `
      <thead><tr><th>File</th><th>Status</th><th>Progress</th><th>Found</th><th>Download</th></tr></thead>
      <tbody>
        ${(jobs || []).map(job => `
          <tr>
            <td>${job.input_filename || '-'}</td>
            <td>${job.status}</td>
            <td>${job.processed_rows}/${job.total_rows}</td>
            <td>${job.found_emails}</td>
            <td>${job.result_csv_url ? `<a href="/api/jobs/${job.id}/download">CSV</a>` : '-'}</td>
          </tr>
        `).join('')}
      </tbody>
    `;
  } catch (err) {
    document.getElementById('jobsTable').innerHTML = `<tbody><tr><td>${err.message}</td></tr></tbody>`;
  }
}

function render() {
  if (state.route === '/login') return authPage('login');
  if (state.route === '/signup') return authPage('signup');
  if (!state.token) return navigate('/login');
  if (state.route === '/providers') return providersPage();
  if (state.route === '/enrich') return enrichPage();
  if (state.route === '/batch') return batchPage();
  if (state.route === '/history') return historyPage();
  return dashboardPage();
}

render();
