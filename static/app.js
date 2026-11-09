const state = { user: null, data: null, page: 'overview', query: '', category: 'all', locationFilter: 'all', stockFilter: 'all', requestFilter: 'all', movementQuery: '', movementType: 'all', overviewActivityType: 'all' };
const app = document.getElementById('app');
const modalRoot = document.getElementById('modal-root');
const toastRoot = document.getElementById('toast-root');
const esc = (s='') => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const moneyless = n => Number(n || 0).toLocaleString();
const fmtDate = s => s ? new Date(s).toLocaleString([], {dateStyle:'medium', timeStyle:'short'}) : '—';
const fmtRelativeDate = s => {
  if (!s) return '—';
  const d = new Date(s);
  const now = new Date();
  const isToday = d.toDateString() === now.toDateString();
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  const isYesterday = d.toDateString() === yesterday.toDateString();
  const timeStr = d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
  if (isToday) return `Today, ${timeStr}`;
  if (isYesterday) return `Yesterday, ${timeStr}`;
  return d.toLocaleDateString([], { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
};

async function api(path, options={}) {
  const res = await fetch(path, {credentials:'same-origin', headers:{'Content-Type':'application/json', ...(options.headers||{})}, ...options});
  const data = await res.json().catch(()=>({}));
  if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
  return data;
}
function toast(message, error=false) {
  toastRoot.innerHTML = `<div class="toast ${error?'error':''}">${esc(message)}</div>`;
  setTimeout(()=>toastRoot.innerHTML='', 3300);
}
async function refresh() {
  const payload = await api('/api/bootstrap');
  state.user = payload.user; state.data = payload.data;
  render();
}
function initials(name) { return String(name||'?').split(/\s+/).slice(0,2).map(x=>x[0]||'').join('').toUpperCase(); }

function renderLogin(setup=false) {
  app.innerHTML = `<div class="login-wrap">
    <section class="login-aside"><div class="brand"><div class="brand-mark">S</div><div><div class="brand-title" style="color:white">Stockroom</div><div class="brand-sub" style="color:#c7ddd2">Inventory, made clear</div></div></div>
      <div class="login-copy"><span class="pill green" style="background:#ffffff20;color:#f3fff8">OFFICE STOCK SYSTEM</span><h1>Know what’s in stock.<br>Know where it is.</h1><p>A single place to find materials, record movements, and keep purchase requests moving.</p></div>
      <div class="login-foot">Local office access · Built for phone and desktop</div></section>
    <section class="login-panel"><div class="login-card"><div class="brand-mark">S</div>
      <h2>${setup?'Set up your stockroom':'Welcome back'}</h2><p class="muted">${setup?'Create the stock person account to get started.':'Sign in with your company account.'}</p>
      <div class="alert-box warning">This V1 runs on the office network. Don’t use a password you use for other services.</div>
      <form id="auth-form">
        ${setup?`<div class="form-row"><label>Your name</label><input class="field" name="name" required autocomplete="name" placeholder="e.g. Anil Kumar"></div>`:''}
        <div class="form-row"><label>Company email</label><input class="field" name="email" type="email" required autocomplete="username" placeholder="name@company.com"></div>
        <div class="form-row"><label>Password</label><input class="field" name="password" type="password" required minlength="8" autocomplete="${setup?'new-password':'current-password'}" placeholder="At least 8 characters"></div>
        ${setup?`<div class="form-row"><label>Confirm password</label><input class="field" name="confirm" type="password" required minlength="8" autocomplete="new-password" placeholder="Enter it again"></div>`:''}
        <button class="btn btn-primary btn-block" type="submit">${setup?'Create stock person account':'Sign in'} <span>→</span></button>
      </form>
    </div></section></div>`;
  document.getElementById('auth-form').addEventListener('submit', async e=>{
    e.preventDefault(); const fd = new FormData(e.currentTarget); const payload = Object.fromEntries(fd.entries());
    if (setup && payload.password !== payload.confirm) return toast('Passwords do not match', true);
    delete payload.confirm;
    try { await api(setup?'/api/setup':'/api/login',{method:'POST',body:JSON.stringify(payload)}); await refresh(); }
    catch(err){ toast(err.message,true); }
  });
}

const navItems = [
  ['overview','▦','Overview'], ['inventory','◫','Inventory'], ['movements','⇄','Activity'], ['requests','⌑','Purchases'], ['settings','⚙','Setup']
];
const titleMap = {overview:'Overview',inventory:'Inventory',movements:'Stock activity',requests:'Purchase requests',settings:'Setup & people'};
function navButton([key,icon,label]) {
  const pending = key==='requests' ? state.data.overview.open_requests : key==='movements' ? state.data.overview.pending_transactions : 0;
  return `<button class="nav-btn ${state.page===key?'active':''}" data-page="${key}"><span class="nav-icon">${icon}</span><span>${label}</span>${pending?`<span class="nav-count">${pending}</span>`:''}</button>`;
}
function render() {
  if (!state.user || !state.data) return;
  const user = state.user;
  const employeeNav = navItems.filter(x => {
    if (x[0] === 'settings' && user.role !== 'stock') return false;
    if (x[0] === 'movements' && user.role !== 'stock') return false;
    return true;
  });
  app.innerHTML = `<div class="app-layout"><aside class="sidebar">
      <div class="brand"><div class="brand-mark">S</div><div><div class="brand-title">Stockroom</div><div class="brand-sub">Inventory workspace</div></div></div>
      <div class="nav-label">Workspace</div><nav class="nav-list">${employeeNav.map(navButton).join('')}</nav>
      <div class="sidebar-bottom"><div class="status-line"><span class="dot"></span>Office server connected</div>
        <div class="profile"><div class="avatar">${initials(user.name)}</div><div><div class="profile-name">${esc(user.name)}</div><div class="profile-role">${user.role==='stock'?'Stock person':'Employee'}</div></div><button class="profile-menu" id="logout" title="Sign out">↪</button></div></div>
    </aside><section class="main"><header class="topbar"><div><div class="crumb">Stockroom / ${esc(titleMap[state.page])}</div><div class="top-title">${esc(titleMap[state.page])}</div></div><div class="top-actions"><button type="button" class="connection" data-action="share-wifi" title="Click to share Wi-Fi link and scan QR code"><i></i><span class="connection-label">Wi-Fi link</span></button><button type="button" class="avatar-btn" data-action="profile-menu" title="Account & options"><div class="avatar">${initials(user.name)}</div></button></div></header>
      <main class="content">${renderPage()}</main></section>
    <nav class="mobile-nav">${employeeNav.map(navButton).join('')}</nav></div>`;
  app.querySelectorAll('[data-page]').forEach(b=>b.addEventListener('click',()=>{state.page=b.dataset.page;render();}));
  document.getElementById('logout').addEventListener('click',async()=>{await api('/api/logout',{method:'POST',body:'{}'});state.user=null;state.data=null;renderLogin(false);});
  bindPageEvents();
}
function renderPage() {
  switch(state.page){
    case 'inventory': return renderInventory();
    case 'movements': return (state.user.role === 'stock' ? renderMovements() : renderOverview());
    case 'requests': return renderRequests();
    case 'settings': return (state.user.role === 'stock' ? renderSettings() : renderOverview());
    default: return renderOverview();
  }
}
function head(title, desc, action='') { return `<div class="page-head"><div><h1>${title}</h1><p>${desc}</p></div>${action}</div>`; }

function renderOverview(){
  const o = state.data.overview, data = state.data;
  const isStock = state.user.role === 'stock';

  if (!isStock) {
    // EMPLOYEE OVERVIEW: Individual workspace and personal history
    const myAllList = getLinkedActivityList(state.user.id, 'all');
    const myActiveList = myAllList.filter(s => s.isActive);
    const myFeed = getLinkedActivityList(state.user.id, state.overviewActivityType);
    const myLoans = data.loans.filter(l => l.borrower_id === state.user.id && (l.remaining_qty === undefined || l.remaining_qty > 0));

    return `${head(`Good ${greeting()}, ${esc(state.user.name.split(" ")[0])}`, 'Your personal stockroom workspace and activity history.')}
      <div class="metric-grid">
        ${metric('Items with me', myLoans.length, 'Currently at your desk', '◇', myLoans.length ? 'tone-blue' : '')}
        ${metric('Open requests', o.my_open_requests || 0, 'Purchase & issue orders', '⌑')}
        ${metric('Items taken', o.my_items_taken || 0, 'Total issued for work', '↗')}
        ${metric('Pending actions', o.my_pending_actions || 0, 'Waiting for verification', '◷', o.my_pending_actions ? 'alert' : '')}
      </div>

      <section class="card"><div class="card-head"><div><div class="card-title">Items currently with me</div><div class="card-subtitle">Taken from stock and not yet returned or closed</div></div><span class="pill ${myLoans.length?'blue':'gray'}">${myLoans.length}</span></div><div class="card-body">
        ${myLoans.length ? myLoans.map(l => `
          <div class="list-row">
            <div class="item-dot">◇</div>
            <div class="row-main">
              <div class="row-name">${esc(l.item_name)}</div>
              <div class="row-meta"><strong style="color:var(--navy);font-size:12px;">${l.remaining_qty} Nos</strong> with you${l.consumed_qty ? ` · <span style="color:#2563eb">${l.consumed_qty} Nos marked used</span>` : ''} · ${esc(l.location_path || l.location_code)} · ${esc(l.project_name || 'General')}</div>
            </div>
            <div class="row-actions">
              ${l.status === 'return_pending' ? `<span class="pill amber">Return pending check</span>` : `
                <button class="btn btn-secondary btn-small" data-return-loan="${l.id}" title="Return to stockroom shelf">Return</button>
                <button class="btn btn-primary btn-small" data-consume-loan="${l.id}" title="Close as used in project">Mark used</button>
              `}
            </div>
          </div>
        `).join('') : `
          <div class="empty"><strong>No items currently with you</strong>When you take items from inventory, they will appear here until you return them or mark them as used.</div>
        `}
      </div></section>

      <section class="card" style="margin-top:16px"><div class="card-head"><div><div class="card-title">My activity history</div><div class="card-subtitle">Connected lifecycles of items you have taken, returned, and used</div></div><span class="pill gray">${myAllList.length} item${myAllList.length === 1 ? '' : 's'}</span></div><div class="card-body">
      ${myAllList.length ? `
        <div class="segmented-filters" style="margin-bottom:12px;">
          <button type="button" class="filter-chip ${state.overviewActivityType==='all'?'active':''}" data-overview-mtype="all">All (${myAllList.length})</button>
          <button type="button" class="filter-chip ${state.overviewActivityType==='active'?'active':''}" data-overview-mtype="active">With me (${myActiveList.length})</button>
          <button type="button" class="filter-chip ${state.overviewActivityType==='return'?'active':''}" data-overview-mtype="return">↻ Returned</button>
          <button type="button" class="filter-chip ${state.overviewActivityType==='consumed'?'active':''}" data-overview-mtype="consumed">✓ Used in project</button>
        </div>
        ${myFeed.length ? `<div class="activity-feed">${myFeed.slice(0, 10).map(renderLinkedActivityCard).join('')}</div>` : `<div class="empty"><strong>No activity matching this filter</strong>Try clicking "All".</div>`}
      ` : `<div class="empty"><div class="empty-icon">◫</div><strong>No activity recorded yet</strong>When you take an item, return stock, or submit a request, it will appear here.</div>`}
      </div></section>`;
  }

  // STOCK PERSON OVERVIEW: Full company stock picture
  const low = data.items.filter(i => i.low_stock).slice(0, 5);
  const allLinked = getLinkedActivityList(null, 'all');
  const staffActive = allLinked.filter(s => s.isActive);
  const stockFeed = getLinkedActivityList(null, state.overviewActivityType);
  const staffLoans = data.loans.filter(l => (l.remaining_qty === undefined || l.remaining_qty > 0));

  return `${head(`Good ${greeting()}, ${esc(state.user.name.split(" ")[0])}`, 'Here’s the latest picture of your stockroom.')}
    <div class="metric-grid">
      ${metric('Inventory items', o.item_count, 'Distinct items', '▧')}
      ${metric('Units in stock', o.units, 'Across all locations', '◫')}
      ${metric('Items with staff', staffLoans.length, 'Currently with employees', '◇', staffLoans.length ? 'tone-blue' : '')}
      ${metric('Needs attention', o.pending_transactions + o.open_requests, 'Returns, requests & receipts', '◷', o.pending_transactions + o.open_requests ? 'alert' : '')}
    </div>
    ${o.needs_count ? `<div class="notice warning">${o.needs_count} item${o.needs_count === 1 ? '' : 's'} need a physical count before their quantity can be trusted. <button class="btn btn-small btn-secondary" data-page="inventory">Review inventory</button></div>` : ''}

    <section class="card"><div class="card-head"><div><div class="card-title">Items currently with staff</div><div class="card-subtitle">Items out of the stockroom and who holds them</div></div><span class="pill ${staffLoans.length?'blue':'gray'}">${staffLoans.length}</span></div><div class="card-body">
      ${staffLoans.length ? staffLoans.map(l => `
        <div class="list-row">
          <div class="item-dot">◇</div>
          <div class="row-main">
            <div class="row-name">${esc(l.item_name)}</div>
            <div class="row-meta"><strong style="color:var(--navy);font-size:12px;">${l.remaining_qty} Nos</strong> with <strong>${esc(l.borrower)}</strong> · ${esc(l.location_path || l.location_code)} · ${esc(l.project_name || 'General')}</div>
          </div>
          <div class="row-actions">
            ${l.status === 'return_pending' ? `<span class="pill amber">Return pending</span>` : ''}
            ${(() => {
              const pendingTx = l.status === 'return_pending' ? data.transactions.find(t => t.kind === 'return' && t.status === 'pending' && t.related_request_id === -l.id) : null;
              return pendingTx ? `<button class="btn btn-primary btn-small" data-confirm-tx="${pendingTx.id}" title="Confirm receipt into stock">Accept return</button>` : '';
            })()}
            <button class="btn btn-secondary btn-small" data-return-loan="${l.id}" title="Return back to shelf">Return</button>
            <button class="btn btn-soft btn-small" data-consume-loan="${l.id}" title="Mark as used (cannot be returned)">Mark used</button>
          </div>
        </div>
      `).join('') : `
        <div class="empty"><strong>All items in stockroom</strong>No items are currently checked out to staff.</div>
      `}
    </div></section>

    <section class="card" style="margin-top:16px"><div class="card-head"><div><div class="card-title">Recent stock activity</div><div class="card-subtitle">Connected lifecycles across all staff & incoming receipts</div></div><button class="btn btn-secondary btn-small" data-page="movements">View all activity →</button></div><div class="card-body">
      <div class="segmented-filters" style="margin-bottom:12px;">
        <button type="button" class="filter-chip ${state.overviewActivityType==='all'?'active':''}" data-overview-mtype="all">All (${allLinked.length})</button>
        <button type="button" class="filter-chip ${state.overviewActivityType==='active'?'active':''}" data-overview-mtype="active">With staff (${staffActive.length})</button>
        <button type="button" class="filter-chip ${state.overviewActivityType==='return'?'active':''}" data-overview-mtype="return">↻ Returned</button>
        <button type="button" class="filter-chip ${state.overviewActivityType==='consumed'?'active':''}" data-overview-mtype="consumed">✓ Used in project</button>
        <button type="button" class="filter-chip ${state.overviewActivityType==='inward'?'active':''}" data-overview-mtype="inward">↙ Stock received</button>
      </div>
      ${stockFeed.length ? `<div class="activity-feed">${stockFeed.slice(0, 8).map(renderLinkedActivityCard).join('')}</div>` : `<div class="empty"><strong>No activity matching this filter</strong>Try clicking "All" to view recent movements.</div>`}
    </div></section>`;
}
function getLinkedActivityList(scopeUserId = null, filterType = 'all', searchQuery = '') {
  const data = state.data;
  if (!data) return [];
  const query = (searchQuery || '').trim().toLowerCase();
  const checkouts = (data.checkouts || data.loans || []);
  const allTxs = data.transactions || [];
  const allReqs = data.requests || [];
  const items = [];

  // 1. Process Checkouts (Lifecycles of items taken from stock)
  checkouts.forEach(c => {
    if (scopeUserId && c.borrower_id !== scopeUserId && c.user_id !== scopeUserId) {
      return;
    }

    const relatedTxs = allTxs.filter(t => t.related_request_id === -c.id);
    const returns = relatedTxs.filter(t => t.kind === 'return');
    const consumed = relatedTxs.filter(t => t.kind === 'consumed');
    const issueTx = relatedTxs.find(t => t.kind === 'issue');

    const totalQty = c.quantity || 1;
    const remainingQty = c.remaining_qty !== undefined ? c.remaining_qty : (c.status === 'returned' ? 0 : totalQty);
    const consumedQty = c.consumed_qty || 0;
    const isActive = remainingQty > 0;

    // Implied return check for historical loans
    const recordedReturns = returns.reduce((sum, r) => sum + r.quantity, 0);
    const impliedReturned = Math.max(0, totalQty - remainingQty - consumedQty - recordedReturns);
    if (impliedReturned > 0) {
      returns.push({
        id: `implied-ret-${c.id}`,
        kind: 'return',
        quantity: impliedReturned,
        created_at: c.returned_at || c.issued_at,
        status: 'confirmed',
        purpose: 'Returned to shelf',
        location_path: c.location_path || c.location_code
      });
    }

    // Implied consumed check for historical loans
    const recordedConsumed = consumed.reduce((sum, k) => sum + k.quantity, 0);
    const impliedConsumed = Math.max(0, consumedQty - recordedConsumed);
    if (impliedConsumed > 0) {
      consumed.push({
        id: `implied-con-${c.id}`,
        kind: 'consumed',
        quantity: impliedConsumed,
        created_at: c.returned_at || c.issued_at,
        status: 'confirmed',
        purpose: 'Used in project'
      });
    }

    // Determine latest activity timestamp
    const allDates = [
      c.issued_at,
      c.returned_at,
      ...returns.map(r => r.created_at),
      ...consumed.map(k => k.created_at)
    ].filter(Boolean);
    const latestAt = allDates.length ? allDates.sort().reverse()[0] : c.issued_at;

    // Filter type check
    let matchesType = false;
    if (filterType === 'all') {
      matchesType = true;
    } else if (filterType === 'active' || filterType === 'with_me' || filterType === 'with_staff') {
      matchesType = isActive;
    } else if (filterType === 'issue' || filterType === 'taken') {
      matchesType = true;
    } else if (filterType === 'return') {
      matchesType = returns.length > 0 || (totalQty - remainingQty - consumedQty) > 0;
    } else if (filterType === 'consumed') {
      matchesType = consumed.length > 0 || consumedQty > 0;
    } else if (filterType === 'inward') {
      matchesType = false;
    }

    if (!matchesType) return;

    // Search query check
    if (query) {
      const searchBlob = [
        c.item_name,
        c.item_code,
        c.category,
        c.borrower,
        c.location_path,
        c.location_code,
        c.project_name,
        issueTx?.purpose,
        ...returns.map(r => `${r.purpose || ''} ${r.condition_note || ''}`),
        ...consumed.map(k => `${k.purpose || ''} ${k.condition_note || ''}`)
      ].filter(Boolean).join(' ').toLowerCase();

      if (!searchBlob.includes(query)) return;
    }

    items.push({
      storyType: 'checkout',
      id: c.id,
      item_name: c.item_name,
      item_code: c.item_code,
      category: c.category,
      unit: c.unit || 'Nos',
      location_path: c.location_path || c.location_code,
      borrower: c.borrower,
      borrower_id: c.borrower_id,
      project_name: c.project_name,
      totalQty,
      remainingQty,
      consumedQty,
      isActive,
      status: c.status,
      issued_at: c.issued_at,
      initial_note: (issueTx?.purpose || '').replace(/\[(Already taken|Kindly issue)\]\s*/gi, '').trim(),
      returns,
      consumed,
      latestAt
    });
  });

  // 2. Process Inward stock receipts (from Purchase Orders or new inventory)
  allTxs.filter(t => t.kind === 'inward').forEach(t => {
    if (scopeUserId && t.user_id !== scopeUserId && t.issued_to_id !== scopeUserId) {
      return;
    }

    const matchesType = (filterType === 'all' || filterType === 'inward');
    if (!matchesType) return;

    const linkedReq = t.related_request_id ? allReqs.find(r => r.id === t.related_request_id) : null;
    const reqLine = linkedReq ? (linkedReq.lines || []).find(l => l.item_id === t.item_id || l.item_name === t.item_name) : null;

    if (query) {
      const searchBlob = [
        t.item_name,
        t.location_path,
        t.location_code,
        t.user_name,
        t.purpose,
        linkedReq?.ref,
        linkedReq?.requester,
        linkedReq?.project_name,
        reqLine?.vendor
      ].filter(Boolean).join(' ').toLowerCase();

      if (!searchBlob.includes(query)) return;
    }

    items.push({
      storyType: 'inward',
      id: `inward-${t.id}`,
      tx_id: t.id,
      item_name: t.item_name,
      location_path: t.location_path || t.location_code,
      quantity: t.quantity,
      user_name: t.user_name,
      purpose: (t.purpose || '').replace(/\[Return unused\]\s*/gi, '').trim(),
      linked_request: linkedReq,
      vendor: reqLine?.vendor,
      product_url: reqLine?.product_url,
      created_at: t.created_at,
      latestAt: t.created_at
    });
  });

  // 3. Process Pending Issue Requests (waiting for stock handover)
  allTxs.filter(t => t.kind === 'issue' && t.status === 'pending').forEach(t => {
    if (scopeUserId && t.user_id !== scopeUserId && t.issued_to_id !== scopeUserId) {
      return;
    }

    const matchesType = (filterType === 'all' || filterType === 'active' || filterType === 'issue');
    if (!matchesType) return;

    if (query) {
      const searchBlob = [
        t.item_name,
        t.location_path,
        t.location_code,
        t.user_name,
        t.issued_to_name,
        t.purpose,
        t.project_name
      ].filter(Boolean).join(' ').toLowerCase();

      if (!searchBlob.includes(query)) return;
    }

    items.push({
      storyType: 'pending_issue',
      id: `pending-${t.id}`,
      tx_id: t.id,
      item_name: t.item_name,
      quantity: t.quantity,
      location_path: t.location_path || t.location_code,
      user_name: t.user_name,
      issued_to_name: t.issued_to_name,
      project_name: t.project_name,
      purpose: (t.purpose || '').replace(/\[Kindly issue\]\s*/gi, '').trim(),
      created_at: t.created_at,
      latestAt: t.created_at
    });
  });

  items.sort((a, b) => new Date(b.latestAt || 0).getTime() - new Date(a.latestAt || 0).getTime());
  return items;
}

function renderLinkedActivityCard(story) {
  if (story.storyType === 'checkout') {
    const isStock = state.user.role === 'stock';
    const canAction = story.isActive && (isStock || story.borrower_id === state.user.id);

    const statusBadge = story.isActive
      ? `<span class="pill blue" style="font-size:10px;">⏳ ${story.remainingQty} ${esc(story.unit)} with ${esc(story.borrower)}</span>`
      : `<span class="pill green" style="font-size:10px;">✓ All resolved</span>`;

    return `
      <div class="activity-card linked-card ${story.isActive ? 'is-active' : 'is-completed'}">
        <div class="activity-icon ${story.isActive ? 'issue' : 'return'}">
          <span>${story.isActive ? '◇' : '✓'}</span>
        </div>
        <div class="activity-body">
          <div class="activity-header">
            <div class="activity-item-title">
              <strong>${esc(story.item_name)}</strong>
              <span class="activity-qty">${story.totalQty} ${esc(story.unit)} taken</span>
              ${statusBadge}
            </div>
            <div class="activity-time" title="${esc(story.latestAt)}">${fmtRelativeDate(story.latestAt)}</div>
          </div>

          <div class="activity-meta">
            <span>Taken by <strong>${esc(story.borrower)}</strong></span>
            <span class="activity-sep">·</span>
            <span class="activity-loc">${esc(story.location_path)}</span>
            ${story.project_name ? `<span class="activity-sep">·</span><span class="activity-project">${esc(story.project_name)}</span>` : ''}
          </div>

          <!-- Connected Visual Lifecycle Link -->
          <div class="activity-chain">
            <!-- 1. Taken step -->
            <div class="chain-step taken">
              <div class="chain-title">
                <span class="chain-tag taken">↗ Taken</span>
                <strong>${story.totalQty} ${esc(story.unit)}</strong>
                <span class="chain-time">${fmtRelativeDate(story.issued_at)}</span>
              </div>
              ${story.initial_note ? `<div class="chain-note">“${esc(story.initial_note)}”</div>` : ''}
            </div>

            <!-- 2. Return steps -->
            ${story.returns.map(ret => {
              const cleanNote = (ret.purpose || ret.condition_note || '').replace(/\[(Already taken|Kindly issue|Return unused)\]\s*/gi, '').trim();
              return `
                <div class="chain-step returned">
                  <div class="chain-title">
                    <span class="chain-tag returned">↻ Returned</span>
                    <strong>${ret.quantity} ${esc(story.unit)}</strong> back to shelf
                    <span class="chain-time">${fmtRelativeDate(ret.created_at)}</span>
                    ${ret.status === 'pending' ? `<span class="pill amber" style="font-size:10px;">Waiting for stock check</span>` : ''}
                  </div>
                  ${cleanNote && cleanNote !== 'Returned to shelf' && cleanNote !== 'Returned from work' ? `<div class="chain-note">“${esc(cleanNote)}”</div>` : ''}
                  ${ret.status === 'pending' && isStock && !String(ret.id).startsWith('implied') ? `
                    <div class="chain-actions">
                      <button class="btn btn-primary btn-small" data-confirm-tx="${ret.id}">Accept return into stock</button>
                    </div>
                  ` : ''}
                </div>
              `;
            }).join('')}

            <!-- 3. Consumed / Used steps -->
            ${story.consumed.map(con => {
              const cleanNote = (con.purpose || con.condition_note || '').replace(/\[(Already taken|Kindly issue|Return unused)\]\s*/gi, '').trim();
              return `
                <div class="chain-step used">
                  <div class="chain-title">
                    <span class="chain-tag used">✓ Used in project</span>
                    <strong>${con.quantity} ${esc(story.unit)}</strong>
                    <span class="chain-time">${fmtRelativeDate(con.created_at)}</span>
                  </div>
                  ${cleanNote ? `<div class="chain-note">“${esc(cleanNote)}”</div>` : ''}
                </div>
              `;
            }).join('')}

            <!-- 4. Active held balance -->
            ${story.isActive ? `
              <div class="chain-step active">
                <div class="chain-title">
                  <span class="chain-tag active">⏳ Still with ${esc(story.borrower)}</span>
                  <strong>${story.remainingQty} ${esc(story.unit)}</strong> remaining
                </div>
                ${canAction ? `
                  <div class="chain-actions">
                    <button class="btn btn-secondary btn-small" data-return-loan="${story.id}" title="Return back to shelf">↻ Return to shelf</button>
                    <button class="btn btn-soft btn-small" data-consume-loan="${story.id}" title="Mark as used (cannot be returned)">✓ Mark used</button>
                  </div>
                ` : ''}
              </div>
            ` : ''}
          </div>
        </div>
      </div>
    `;
  }

  if (story.storyType === 'inward') {
    return `
      <div class="activity-card inward-card">
        <div class="activity-icon inward">
          <span>↙</span>
        </div>
        <div class="activity-body">
          <div class="activity-header">
            <div class="activity-item-title">
              <strong>${esc(story.item_name)}</strong>
              <span class="activity-qty" style="background:#dcfce7;color:#15803d;">+${story.quantity} Nos received</span>
              <span class="pill green" style="font-size:10px;">Stock received</span>
            </div>
            <div class="activity-time" title="${esc(story.created_at)}">${fmtRelativeDate(story.created_at)}</div>
          </div>
          <div class="activity-meta">
            <span>Stored at <strong>${esc(story.location_path)}</strong> by <strong>${esc(story.user_name)}</strong></span>
            ${story.purpose ? `<span class="activity-sep">·</span><span>${esc(story.purpose)}</span>` : ''}
          </div>
          ${story.linked_request ? `
            <div class="linked-pr-box">
              <div class="linked-pr-head">
                <span class="pill blue" style="font-size:10px;font-weight:700;">${esc(story.linked_request.ref)}</span>
                <span>Requested by <strong>${esc(story.linked_request.requester)}</strong>${story.linked_request.project_name ? ` · ${esc(story.linked_request.project_name)}` : ''}</span>
              </div>
              ${story.vendor ? `<div class="linked-pr-meta">Vendor: <strong>${esc(story.vendor)}</strong>${story.product_url ? ` · <a href="${esc(story.product_url)}" target="_blank" rel="noopener">Product link ↗</a>` : ''}</div>` : ''}
            </div>
          ` : ''}
        </div>
      </div>
    `;
  }

  if (story.storyType === 'pending_issue') {
    return `
      <div class="activity-card pending-card">
        <div class="activity-icon issue">
          <span>↗</span>
        </div>
        <div class="activity-body">
          <div class="activity-header">
            <div class="activity-item-title">
              <strong>${esc(story.item_name)}</strong>
              <span class="activity-qty">${story.quantity} Nos</span>
              <span class="pill amber" style="font-size:10px;">Issue requested</span>
            </div>
            <div class="activity-time" title="${esc(story.created_at)}">${fmtRelativeDate(story.created_at)}</div>
          </div>
          <div class="activity-meta">
            <span>Requested by <strong>${esc(story.user_name)}</strong>${story.issued_to_name && story.issued_to_name !== story.user_name ? ` for <strong>${esc(story.issued_to_name)}</strong>` : ''}</span>
            <span class="activity-sep">·</span>
            <span class="activity-loc">${esc(story.location_path)}</span>
            ${story.project_name ? `<span class="activity-sep">·</span><span class="activity-project">${esc(story.project_name)}</span>` : ''}
          </div>
          ${story.purpose ? `<div class="activity-note">“${esc(story.purpose)}”</div>` : ''}
          ${state.user.role === 'stock' ? `
            <div class="chain-actions" style="margin-top:8px;">
              <button class="btn btn-primary btn-small" data-confirm-tx="${story.tx_id}">Issue / Hand over</button>
              <button class="btn btn-danger btn-small" data-reject-tx="${story.tx_id}">Reject</button>
            </div>
          ` : ''}
        </div>
      </div>
    `;
  }

  return '';
}
function renderActivityCard(t){
  return renderLinkedActivityCard(t);
}
function greeting(){const h=new Date().getHours();return h<12?'morning':h<18?'afternoon':'evening';}
function metric(label,value,caption,icon,tone=''){return `<div class="metric-card ${tone}"><div class="metric-top"><span class="metric-label">${label}</span><span class="metric-icon">${icon}</span></div><div class="metric-value">${moneyless(value)}</div><div class="metric-caption">${caption}</div></div>`;}
function statusPill(status){const cls={confirmed:'green',approved:'green',ordered:'blue',received:'green',partially_received:'amber',pending:'amber',rejected:'red',return_pending:'amber',issued:'blue'}[status]||'gray';const label={partially_received:'Part received',return_pending:'Return pending'}[status]||status.replaceAll('_',' ');return `<span class="pill ${cls}">${esc(label)}</span>`;}
function getHighRack(path){
  if (!path) return 'No location';
  const parts = path.split(' / ').map(p => p.trim());
  if (parts.length > 1 && parts[0].toLowerCase().includes('stock room')) {
    return parts[1];
  }
  return parts[0] || 'No location';
}

function locationText(item){
  return item.locations?.length ?
    item.locations.map(l=>`<span class="loc-tag">${esc(l.path||l.name)} · ${l.quantity}${l.needs_count?' · [Needs count]':''}</span>`).join('') :
    `<span class="cell-sub">No confirmed location</span>`;
}

function renderInventory(){
  const isStock = state.user.role === 'stock';
  const categories = [...new Set(state.data.items.map(i => i.category))].sort();
  const query = (state.query || '').trim().toLowerCase();

  // Extract all high-level racks / cupboards (IoT Rack-A, White Cupboard, etc.)
  const highRacks = [...new Set(
    state.data.locations
      .map(l => l.high_rack || getHighRack(l.path))
      .filter(r => r && r !== 'Stock Room' && r !== 'Unknown location' && r !== 'No location')
  )].sort();

  const stockFilterLabels = {
    'needs_count': 'Needs count (not mentioned qty)',
    'uncategorized': 'Not categorized',
    'no_location': 'No location assigned',
    'low_stock': 'Low stock',
    'out_of_stock': 'Out of stock'
  };

  let allMatches = state.data.items.filter(i => {
    // 1. Category filter
    if (state.category !== 'all' && i.category !== state.category) return false;

    // 2. High Rack / Location filter
    if (state.locationFilter !== 'all') {
      if (state.locationFilter === 'unassigned') {
        if (i.locations && i.locations.length > 0) return false;
      } else {
        const itemRacks = (i.locations || []).map(l => l.high_rack || getHighRack(l.path));
        if (!itemRacks.includes(state.locationFilter)) return false;
      }
    }

    // 3. Stock person attention filter
    if (isStock && state.stockFilter !== 'all') {
      if (state.stockFilter === 'needs_count') {
        const needsCount = i.needs_count || (i.locations && i.locations.some(l => l.needs_count));
        if (!needsCount) return false;
      } else if (state.stockFilter === 'uncategorized') {
        const uncategorized = !i.category || i.category === 'Uncategorized';
        if (!uncategorized) return false;
      } else if (state.stockFilter === 'no_location') {
        if (i.locations && i.locations.length > 0) return false;
      } else if (state.stockFilter === 'low_stock') {
        if (!i.low_stock) return false;
      } else if (state.stockFilter === 'out_of_stock') {
        if (i.total_qty !== 0 || i.needs_count) return false;
      }
    }

    // 4. Search query
    if (!query) return true;
    const haystack = `${i.name} ${i.item_code} ${i.category} ${i.part_number || ''} ${(i.locations||[]).map(l => (l.path||'') + ' ' + (l.high_rack||'') + ' ' + (l.code||'') + ' ' + (l.name||'')).join(' ')}`.toLowerCase();
    return haystack.includes(query);
  });

  const totalMatches = allMatches.length;
  const rows = allMatches.slice(0, 50);
  const action = isStock ? `<button class="btn btn-primary" data-action="add-item">＋ Add item</button>` : '';

  const hasAnyFilter = query || state.category !== 'all' || state.locationFilter !== 'all' || (isStock && state.stockFilter !== 'all');

  return `${head('Inventory', isStock ? 'Search what’s in stock, filter by rack or review items needing attention.' : 'Find materials, filter by category or shelf rack, and take or request items.', action)}
    <div class="toolbar">
      <div class="search-box">
        <span class="search-icon">⌕</span>
        <input class="field" id="inventory-search" placeholder="Search item name, code, category, part # or shelf…" value="${esc(state.query)}" autocomplete="off">
        ${state.query ? `<button type="button" class="search-clear-btn" id="clear-inventory-search" title="Clear search">✕</button>` : ''}
      </div>
      <div class="toolbar-actions">
        <select class="select filter-select" id="category-filter" title="Filter by category">
          <option value="all">All categories</option>
          ${categories.map(c => `<option ${state.category === c ? 'selected' : ''} value="${esc(c)}">${esc(c)}</option>`).join('')}
        </select>
        <select class="select filter-select" id="location-filter" title="Filter by high rack / cupboard">
          <option value="all">All locations (rack-wise)</option>
          ${highRacks.map(r => `<option ${state.locationFilter === r ? 'selected' : ''} value="${esc(r)}">${esc(r)}</option>`).join('')}
          <option ${state.locationFilter === 'unassigned' ? 'selected' : ''} value="unassigned">📍 No location assigned</option>
        </select>
        ${isStock ? `
          <select class="select filter-select" id="stock-filter" title="Stock person review filters">
            <option value="all">All status</option>
            <option ${state.stockFilter === 'needs_count' ? 'selected' : ''} value="needs_count">⚠️ Not mentioned qty (${state.data.overview.needs_count || 0})</option>
            <option ${state.stockFilter === 'uncategorized' ? 'selected' : ''} value="uncategorized">🏷️ Not categorized</option>
            <option ${state.stockFilter === 'no_location' ? 'selected' : ''} value="no_location">📍 No location assigned</option>
            <option ${state.stockFilter === 'low_stock' ? 'selected' : ''} value="low_stock">📉 Low stock (${state.data.overview.low_stock || 0})</option>
            <option ${state.stockFilter === 'out_of_stock' ? 'selected' : ''} value="out_of_stock">❌ Out of stock (${state.data.overview.out_of_stock || 0})</option>
          </select>
        ` : ''}
        <button class="btn btn-secondary" id="download-stock">↓ Export CSV</button>
      </div>
    </div>

    <div class="search-feedback">
      ${query ?
        `<span>Found <strong>${totalMatches}</strong> matching item${totalMatches === 1 ? '' : 's'}${totalMatches > 50 ? ' (showing top 50 for fast browsing)' : ''}</span>` :
        `<span>Showing first ${Math.min(50, totalMatches)} of <strong>${moneyless(totalMatches)}</strong> matching items.</span>`
      }
      <div class="filter-pills" style="display:inline-flex;gap:6px;align-items:center;margin-left:8px;flex-wrap:wrap;">
        ${state.category !== 'all' ? `<span class="pill green">Category: ${esc(state.category)} <button type="button" class="pill-remove" data-clear="category" title="Clear category">✕</button></span>` : ''}
        ${state.locationFilter !== 'all' ? `<span class="pill blue">Rack: ${esc(state.locationFilter === 'unassigned' ? 'No location' : state.locationFilter)} <button type="button" class="pill-remove" data-clear="locationFilter" title="Clear location">✕</button></span>` : ''}
        ${isStock && state.stockFilter !== 'all' ? `<span class="pill amber">Status: ${esc(stockFilterLabels[state.stockFilter] || state.stockFilter)} <button type="button" class="pill-remove" data-clear="stockFilter" title="Clear filter">✕</button></span>` : ''}
        ${hasAnyFilter ? `<button type="button" class="btn btn-soft btn-small" id="clear-all-filters" style="font-size:11px;padding:3px 8px;">Clear all</button>` : ''}
      </div>
    </div>

    <section class="card">
      <div class="table-wrap">
        ${rows.length ? `
          <table class="data-table responsive-table">
            <thead>
              <tr>
                <th>Item</th>
                <th>Category</th>
                <th>Quantity</th>
                <th>Storage location</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              ${rows.map(i => `
                <tr>
                  <td>
                    <div class="cell-title">${esc(i.name)}</div>
                    <div class="cell-sub">${esc(i.item_code)}${i.part_number ? ` · Part: ${esc(i.part_number)}` : ''}${i.kind === 'asset' ? ' · ↻ Reusable tool' : ''}</div>
                  </td>
                  <td data-label="Category">${esc(i.category)}</td>
                  <td data-label="Quantity">
                    <span class="qty">${moneyless(i.total_qty)}</span>
                    <span class="cell-sub" style="margin-left:4px">${esc(i.unit)}${i.needs_count ? ' · count needed' : ''}</span>
                  </td>
                  <td data-label="Location"><div class="location-tags">${locationText(i)}</div></td>
                  <td data-label="Status">
                    ${i.needs_count ? '<span class="pill amber">Needs count</span>' :
                      i.low_stock ? '<span class="pill amber">Low stock</span>' :
                      i.total_qty === 0 ? '<span class="pill red">Out of stock</span>' :
                      '<span class="pill green">In stock</span>'}
                  </td>
                  <td>
                    <div class="row-actions">
                      ${isStock ? `
                        <button class="btn btn-secondary btn-small" data-action="edit-item" data-item="${i.id}">Edit</button>
                        <button class="btn ${i.needs_count || i.locations.some(l => l.needs_count) ? 'btn-soft' : 'btn-outline'} btn-small" data-action="count-item" data-item="${i.id}" title="${i.needs_count ? 'Enter physical count' : 'Verify / update count'}">Count</button>
                      ` : `
                        <button class="btn btn-primary btn-small" data-action="employee-take" data-item="${i.id}">Take / Request</button>
                      `}
                    </div>
                  </td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        ` : `
          <div class="empty">
            <div class="empty-icon">⌕</div>
            <strong>No matching items found</strong>
            <p style="margin:4px 0 12px;font-size:12px;">Try checking your spelling or clearing filters.</p>
            <button class="btn btn-secondary btn-small" id="reset-search-empty-btn">Clear search & filters</button>
          </div>
        `}
      </div>
    </section>
  `;
}

function renderMovements(){
  if (state.user.role !== 'stock') return renderOverview();
  const pending = state.data.transactions.filter(t => t.status === 'pending');
  const allStories = getLinkedActivityList(null, 'all');
  const staffActive = allStories.filter(s => s.isActive);
  const stories = getLinkedActivityList(null, state.movementType, state.movementQuery);

  const action = `<button class="btn btn-primary" data-action="issue">＋ Issue stock</button>`;

  return `${head('Stock activity', 'Connected timeline of items taken, returned, and used across the team.', action)}

    ${pending.length ? `
      <section class="card attention-card" style="margin-bottom:18px;border-color:#f59e0b;background:#fffdf7;">
        <div class="card-head" style="background:#fffbeb;border-bottom:1px solid #fef3c7;">
          <div style="display:flex;align-items:center;gap:8px;">
            <span class="pill amber" style="font-size:11px;">⚠️ Needs your confirmation</span>
            <span style="font-size:12px;color:#92400e;font-weight:600;">${pending.length} pending request${pending.length === 1 ? '' : 's'}</span>
          </div>
        </div>
        <div class="card-body" style="padding:10px 16px;">
          ${pending.map(t => `
            <div class="list-row">
              <div class="item-dot" style="background:#fef3c7;color:#b45309;">${t.kind==='return'?'↻':t.kind==='issue'?'↗':'↙'}</div>
              <div class="row-main">
                <div class="row-name"><strong>${esc(t.item_name)}</strong> · <span style="color:var(--navy);font-weight:700;">${t.quantity} Nos</span></div>
                <div class="row-meta">${esc(t.location_path||t.location_code)} · <strong>${esc(t.user_name)}</strong>${t.issued_to_name && t.issued_to_name !== t.user_name ? ` for ${esc(t.issued_to_name)}` : ''}${t.purpose ? ` · <em>${esc(t.purpose)}</em>` : ''}</div>
              </div>
              <div class="row-actions">
                <button class="btn btn-primary btn-small" data-confirm-tx="${t.id}">${t.kind==='issue'?'Issue / Hand over':'Accept return'}</button>
                <button class="btn btn-danger btn-small" data-reject-tx="${t.id}">Reject</button>
              </div>
            </div>
          `).join('')}
        </div>
      </section>
    ` : ''}

    <div class="activity-filter-bar">
      <div class="search-box">
        <span class="search-icon">⌕</span>
        <input class="field" id="movement-search" placeholder="Search item, person, project, shelf or remarks…" value="${esc(state.movementQuery)}" autocomplete="off">
        ${state.movementQuery ? `<button type="button" class="search-clear-btn" id="clear-movement-search" title="Clear search">✕</button>` : ''}
      </div>
      <div class="segmented-filters">
        <button type="button" class="filter-chip ${state.movementType==='all'?'active':''}" data-mtype="all">All (${allStories.length})</button>
        <button type="button" class="filter-chip ${state.movementType==='active'?'active':''}" data-mtype="active">With staff (${staffActive.length})</button>
        <button type="button" class="filter-chip ${state.movementType==='return'?'active':''}" data-mtype="return">↻ Returned</button>
        <button type="button" class="filter-chip ${state.movementType==='consumed'?'active':''}" data-mtype="consumed">✓ Used in project</button>
        <button type="button" class="filter-chip ${state.movementType==='inward'?'active':''}" data-mtype="inward">↙ Stock received</button>
      </div>
    </div>

    <div class="search-feedback" style="margin-bottom:12px;">
      <span>Showing <strong>${stories.length}</strong> activity record${stories.length === 1 ? '' : 's'}${state.movementType !== 'all' || state.movementQuery ? ' (filtered)' : ''}</span>
      ${state.movementType !== 'all' || state.movementQuery ? `<button type="button" class="btn btn-soft btn-small" id="reset-activity-filters" style="font-size:11px;padding:3px 8px;">Reset filters</button>` : ''}
    </div>

    <div class="activity-feed">
      ${stories.length ? stories.map(renderLinkedActivityCard).join('') : `
        <div class="empty" style="background:#fff;border:1px solid var(--line);border-radius:12px;">
          <div class="empty-icon">⇄</div>
          <strong>No matching activity</strong>
          <p style="margin:4px 0 10px;font-size:12px;">Try selecting "All" or clearing your search term.</p>
          <button class="btn btn-secondary btn-small" id="empty-clear-activity-btn">Clear search & filters</button>
        </div>
      `}
    </div>
  `;
}
function renderRequests(){
  const requests=state.data.requests.filter(r=>state.requestFilter==='all'||r.status===state.requestFilter);
  const stock=state.user.role==='stock';
  return `${head('Purchase requests','Employees request items here; the stock person tracks the manager decision and sourcing.',`<button class="btn btn-primary" data-action="request">＋ New request</button>`)}
    <div class="toolbar"><select class="select filter-select" id="request-filter"><option value="all">All requests</option>${['pending','approved','rejected','ordered','partially_received','received'].map(s=>`<option value="${s}" ${state.requestFilter===s?'selected':''}>${s.replaceAll('_',' ')}</option>`).join('')}</select></div>
    <div class="card">${requests.length?requests.map(r=>`<article class="request-card"><div class="request-head"><div><span class="pill blue">${esc(r.ref)}</span><div class="cell-title" style="margin-top:8px">${esc(r.item_summary||'Purchase request')}</div><div class="cell-sub">${esc(r.requester)} · ${esc(r.project_name||'General/Internal')} · ${fmtDate(r.created_at)}</div></div><div class="request-status">${statusPill(r.status)}</div></div><div class="request-lines">${r.lines.map(l=>`<div class="request-line"><div><span>${esc(l.item_name)}</span>${l.vendor||l.product_url?`<div class="cell-sub">${l.vendor?`Vendor: ${esc(l.vendor)}`:''}${l.product_url?`${l.vendor?' · ':''}<a href="${esc(l.product_url)}" target="_blank" rel="noopener noreferrer">Product link</a>`:''}</div>`:''}</div><span>${l.received_quantity}/${l.quantity} received</span></div>`).join('')}</div>${r.purpose?`<div class="cell-sub">Purpose: ${esc(r.purpose)}</div>`:''}
      ${stock?`<div class="request-actions">${r.status==='pending'?`<button class="btn btn-soft btn-small" data-req-status="approved" data-id="${r.id}">Approve</button><button class="btn btn-danger btn-small" data-req-status="rejected" data-id="${r.id}">Reject</button>`:''}${r.status==='approved'?`<button class="btn btn-primary btn-small" data-req-status="ordered" data-id="${r.id}">Mark ordered</button><button class="btn btn-danger btn-small" data-req-status="rejected" data-id="${r.id}">Cancel order</button>`:''}${['ordered','partially_received'].includes(r.status)?`<button class="btn btn-primary btn-small" data-receive-req="${r.id}">Record received quantity</button>${r.status==='partially_received'?`<button class="btn btn-secondary btn-small" data-req-status="received" data-id="${r.id}" title="Mark completed and close remaining">Close remaining</button>`:''}<button class="btn btn-danger btn-small" data-req-status="rejected" data-id="${r.id}" title="Cancel order and close">Cancel order</button>`:''}<button class="btn btn-outline btn-small" data-delete-req="${r.id}" title="Completely clear this request" style="color:#ef4444;border-color:#fca5a5;">Clear request</button></div>`:(r.requester_id===state.user.id&&r.status==='pending'?`<div class="request-actions"><button class="btn btn-danger btn-small" data-req-status="rejected" data-id="${r.id}">Cancel request</button></div>`:'')}</article>`).join(''):`<div class="empty"><div class="empty-icon">⌑</div><strong>No purchase requests${state.requestFilter==='all'?' yet':` with status “${esc(state.requestFilter)}”`}</strong>New requests will show here for the stock person to track.</div>`}</div>`;
}
function locationTree(parentId=null){const children=state.data.locations.filter(l=>l.parent_id===parentId);if(!children.length)return '';return `<ul class="location-tree">${children.map(l=>{const nested=locationTree(l.id);return `<li>${nested?`<details open><summary>${esc(l.name)}</summary>${nested}</details>`:`<span>${esc(l.name)}</span>`}</li>`;}).join('')}</ul>`;}
function renderSettings(){
  if(state.user.role!=='stock')return `${head('Setup','This section is for the stock person.')}`;
  return `${head('Setup & people','Manage the stockroom lists and staff access.')}
    <div class="grid-two"><section class="card"><div class="card-head"><div><div class="card-title">Add inventory item</div><div class="card-subtitle">Stock changes should be recorded as movements.</div></div></div><div class="card-body"><button class="btn btn-primary" data-action="add-item">＋ Add item</button><button class="btn btn-secondary" data-action="add-location" style="margin-left:8px">＋ Add location</button></div></section>
      <section class="card"><div class="card-head"><div><div class="card-title">Projects</div><div class="card-subtitle">The employee selects a project or General/Internal.</div></div><button class="btn btn-secondary btn-small" data-action="add-project">＋ Project</button></div><div class="card-body">${state.data.projects.length?state.data.projects.map(p=>`<div class="list-row"><div class="item-dot">◇</div><div class="row-main"><div class="row-name">${esc(p.name)}</div></div></div>`).join(''):`<div class="empty"><strong>No projects yet</strong>General/Internal is available without setup.</div>`}</div></section></div>
    <section class="card" style="margin-top:16px"><div class="card-head"><div><div class="card-title">Storage locations</div><div class="card-subtitle">Nested folders show the complete stock location path.</div></div></div><div class="card-body">${locationTree()}</div></section>
    <section class="card" style="margin-top:16px"><div class="card-head"><div><div class="card-title">User accounts</div><div class="card-subtitle">All staff can view and issue stock. Only the stock person can confirm inward entries and manage requests.</div></div><button class="btn btn-primary btn-small" data-action="add-user">＋ Add user</button></div><div class="table-wrap"><table class="data-table responsive-table"><thead><tr><th>Name</th><th>Company email</th><th>Role</th><th style="width:80px"></th></tr></thead><tbody>${state.data.users.map(u=>`<tr><td><div class="cell-title">${esc(u.name)}</div></td><td data-label="Email">${esc(u.email)}</td><td data-label="Role">${u.role==='stock'?'<span class="pill green">Stock person</span>':'<span class="pill gray">Employee</span>'}</td><td><div class="row-actions"><button class="btn btn-secondary btn-small" data-action="edit-user" data-user="${u.id}">Edit</button></div></td></tr>`).join('')}</tbody></table></div></section>
    <section class="card" style="margin-top:16px"><div class="card-head"><div><div class="card-title">Data and backup</div><div class="card-subtitle">Download a stock overview CSV. Keep a separate backup of the office laptop data folder.</div></div><a class="btn btn-secondary btn-small" href="/api/export.csv">↓ Export stock CSV</a></div><div class="card-body"><div class="notice warning">The Google Sheets snapshot connection is not configured in this prototype. The CSV export can be reviewed now; automatic sheet refresh needs a destination sheet and its connection details.</div><div class="cell-sub">Database file: data/inventory.sqlite3 · Keep regular backups on a separate drive.</div></div></section>`;
}

function bindPageEvents(){
  document.querySelectorAll('[data-action]').forEach(b=>b.addEventListener('click',()=>openAction(b.dataset.action,b.dataset.item||b.dataset.user||'')));
  document.querySelectorAll('[data-page]').forEach(b=>b.addEventListener('click',()=>{state.page=b.dataset.page;render();}));
  document.querySelectorAll('[data-confirm-tx]').forEach(b=>b.addEventListener('click',async()=>{try{await api(`/api/transactions/${b.dataset.confirmTx}/confirm`,{method:'POST',body:'{}'});await refresh();toast('Stock movement confirmed');}catch(e){toast(e.message,true)}}));
  document.querySelectorAll('[data-reject-tx]').forEach(b=>b.addEventListener('click',async()=>{if(!confirm('Reject this pending movement?'))return;try{await api(`/api/transactions/${b.dataset.rejectTx}/reject`,{method:'POST',body:'{}'});await refresh();toast('Stock movement rejected');}catch(e){toast(e.message,true)}}));
  document.querySelectorAll('[data-return-loan]').forEach(b=>b.addEventListener('click',()=>openReturn(b.dataset.returnLoan)));
  document.querySelectorAll('[data-consume-loan]').forEach(b=>b.addEventListener('click',()=>openConsumeModal(b.dataset.consumeLoan)));
  document.querySelectorAll('[data-clear-loan]').forEach(b=>b.addEventListener('click',async()=>{
    if(!confirm('Clear this checked-out item? It will be marked as closed.')) return;
    try{
      await api(`/api/loans/${b.dataset.clearLoan}/clear`, {method:'POST', body:'{}'});
      await refresh();
      toast('Item checkout cleared');
    }catch(e){toast(e.message,true)}
  }));
  document.querySelectorAll('[data-req-status]').forEach(b=>b.addEventListener('click',async()=>{
    const status = b.dataset.reqStatus;
    if ((status === 'rejected' || status === 'received') && !confirm(`Are you sure you want to ${status==='rejected'?'cancel':'close'} this request?`)) return;
    try{
      await api(`/api/requests/${b.dataset.id}/status`,{method:'POST',body:JSON.stringify({status})});
      await refresh();
      toast('Request updated');
    }catch(e){toast(e.message,true)}
  }));
  document.querySelectorAll('[data-delete-req]').forEach(b=>b.addEventListener('click',async()=>{
    if(!confirm('Are you sure you want to completely clear and remove this purchase request?')) return;
    try{
      const res = await api(`/api/requests/${b.dataset.deleteReq}/delete`,{method:'POST',body:'{}'});
      await refresh();
      toast(res.message || 'Request cleared successfully');
    }catch(e){toast(e.message,true)}
  }));
  document.querySelectorAll('[data-receive-req]').forEach(b=>b.addEventListener('click',()=>openReceive(b.dataset.receiveReq)));

  const search = document.getElementById('inventory-search');
  if (search) {
    search.addEventListener('input', e => {
      state.query = e.target.value;
      const pos = e.target.selectionStart;
      render();
      const next = document.getElementById('inventory-search');
      if (next) {
        next.focus();
        next.setSelectionRange(pos, pos);
      }
    });
  }
  const clearSearch = document.getElementById('clear-inventory-search');
  if (clearSearch) {
    clearSearch.addEventListener('click', () => {
      state.query = '';
      render();
      document.getElementById('inventory-search')?.focus();
    });
  }
  document.querySelectorAll('[data-clear]').forEach(b => b.addEventListener('click', e => {
    e.stopPropagation();
    const what = b.dataset.clear;
    if (what === 'category') state.category = 'all';
    if (what === 'locationFilter') state.locationFilter = 'all';
    if (what === 'stockFilter') state.stockFilter = 'all';
    render();
  }));

  const clearAllFilters = document.getElementById('clear-all-filters');
  if (clearAllFilters) {
    clearAllFilters.addEventListener('click', () => {
      state.query = '';
      state.category = 'all';
      state.locationFilter = 'all';
      state.stockFilter = 'all';
      render();
    });
  }

  const resetEmpty = document.getElementById('reset-search-empty-btn');
  if (resetEmpty) {
    resetEmpty.addEventListener('click', () => {
      state.query = '';
      state.category = 'all';
      state.locationFilter = 'all';
      state.stockFilter = 'all';
      render();
    });
  }

  const movementSearch = document.getElementById('movement-search');
  if (movementSearch) movementSearch.addEventListener('input', e => {
    state.movementQuery = e.target.value;
    const pos = e.target.selectionStart;
    render();
    const next = document.getElementById('movement-search');
    if (next) { next.focus(); next.setSelectionRange(pos, pos); }
  });
  const clearMovementSearch = document.getElementById('clear-movement-search');
  if (clearMovementSearch) {
    clearMovementSearch.addEventListener('click', () => {
      state.movementQuery = '';
      render();
      document.getElementById('movement-search')?.focus();
    });
  }
  document.querySelectorAll('.filter-chip[data-mtype]').forEach(chip => {
    chip.addEventListener('click', () => {
      state.movementType = chip.dataset.mtype;
      render();
    });
  });
  document.querySelectorAll('.filter-chip[data-overview-mtype]').forEach(chip => {
    chip.addEventListener('click', () => {
      state.overviewActivityType = chip.dataset.overviewMtype;
      render();
    });
  });
  const resetActivity = document.getElementById('reset-activity-filters') || document.getElementById('empty-clear-activity-btn');
  if (resetActivity) {
    resetActivity.addEventListener('click', () => {
      state.movementQuery = '';
      state.movementType = 'all';
      render();
    });
  }
  const cat = document.getElementById('category-filter');
  if (cat) cat.addEventListener('change', e => { state.category = e.target.value; render(); });
  const loc = document.getElementById('location-filter');
  if (loc) loc.addEventListener('change', e => { state.locationFilter = e.target.value; render(); });
  const st = document.getElementById('stock-filter');
  if (st) st.addEventListener('change', e => { state.stockFilter = e.target.value; render(); });
  const req = document.getElementById('request-filter');
  if (req) req.addEventListener('change', e => { state.requestFilter = e.target.value; render(); });
  const dl = document.getElementById('download-stock');
  if (dl) dl.addEventListener('click', () => window.location.href = '/api/export.csv');
}

function opts(rows,placeholder,labelFn,selected=''){return `<option value="">${esc(placeholder)}</option>${rows.map(r=>`<option value="${r.id}" ${String(selected)===String(r.id)?'selected':''}>${esc(labelFn(r))}</option>`).join('')}`;}
function formModal(title,body,submitLabel,onSubmit,wide=false){
  modalRoot.innerHTML=`<div class="modal-backdrop"><div class="modal ${wide?'wide':''}" role="dialog" aria-modal="true"><div class="modal-head"><h2>${title}</h2><button class="modal-close" type="button">×</button></div><form id="modal-form"><div class="modal-body">${body}</div><div class="modal-foot"><button class="btn btn-secondary" type="button" data-cancel>Cancel</button><button class="btn btn-primary" type="submit">${submitLabel}</button></div></form></div></div>`;
  modalRoot.querySelector('.modal-close').onclick=closeModal;modalRoot.querySelector('[data-cancel]').onclick=closeModal;
  modalRoot.querySelector('.modal-backdrop').addEventListener('click',e=>{if(e.target.classList.contains('modal-backdrop'))closeModal()});
  modalRoot.querySelector('#modal-form').addEventListener('submit',async e=>{e.preventDefault();const submit=e.currentTarget.querySelector('[type=submit]');submit.disabled=true;try{await onSubmit(new FormData(e.currentTarget));closeModal();await refresh();toast('Saved successfully');}catch(err){toast(err.message,true);submit.disabled=false;}});
  setTimeout(()=>modalRoot.querySelector('input,select,textarea')?.focus(),30);
}
function closeModal(){modalRoot.innerHTML='';}
function infoModal(title,body,wide=false){
  modalRoot.innerHTML=`<div class="modal-backdrop"><div class="modal ${wide?'wide':''}" role="dialog" aria-modal="true"><div class="modal-head"><h2>${title}</h2><button class="modal-close" type="button">×</button></div><div class="modal-body">${body}</div><div class="modal-foot"><button class="btn btn-primary" type="button" data-cancel>Close</button></div></div></div>`;
  modalRoot.querySelector('.modal-close').onclick=closeModal;
  modalRoot.querySelector('[data-cancel]').onclick=closeModal;
  modalRoot.querySelector('.modal-backdrop').addEventListener('click',e=>{if(e.target.classList.contains('modal-backdrop'))closeModal();});
}

async function openWifiShare(){
  try {
    const net = await api('/api/network-info');
    const wifiUrl = net.primary_wifi_url || (window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1' ? window.location.origin + '/' : ('http://' + window.location.hostname + ':' + (net.port || 8080) + '/'));
    const body = `<div style="display:flex;flex-direction:column;gap:16px;">
      <div style="text-align:center;padding:6px 0 2px;">
        <div style="font-size:12px;color:var(--muted);margin-bottom:8px;">Scan with smartphone camera to open Stockroom:</div>
        <div id="qrcode-container" style="display:inline-block;padding:12px;background:#fff;border:1px solid var(--line);border-radius:12px;box-shadow:0 4px 14px rgba(0,0,0,0.06);min-width:180px;min-height:180px;"></div>
      </div>
      <div class="notice">
        <strong>Direct link for phones & colleagues on this Wi-Fi:</strong>
        <div style="display:flex;gap:8px;margin-top:8px;align-items:center;">
          <input class="field" id="wifi-share-url" value="${esc(wifiUrl)}" readonly style="font-weight:600;font-size:13px;color:#1d4ed8;background:#eff6ff;">
          <button class="btn btn-secondary" type="button" id="copy-wifi-btn" style="white-space:nowrap;">Copy link</button>
        </div>
      </div>
      <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:9px;padding:12px 14px;font-size:12px;line-height:1.6;color:#334155;">
        <strong style="display:block;margin-bottom:6px;font-size:12px;color:#0f172a;">Connecting checklist:</strong>
        <ul style="margin:0;padding-left:18px;">
          <li>All phones and computers must be connected to the <b>same Wi-Fi</b> network.</li>
          <li><b>If the page does not open:</b> Run <code>enable_wifi_access.bat</code> on this laptop once as Administrator to allow Windows Firewall access.</li>
        </ul>
      </div>
    </div>`;
    infoModal('Wi-Fi Access & QR Code', body);

    const qrTarget = document.getElementById('qrcode-container');
    if (qrTarget && typeof QRCode !== 'undefined') {
      new QRCode(qrTarget, {
        text: wifiUrl,
        width: 180,
        height: 180,
        colorDark: "#182a25",
        colorLight: "#ffffff",
        correctLevel: QRCode.CorrectLevel.M
      });
    } else if (qrTarget) {
      qrTarget.innerHTML = `<p style="padding:40px 10px;color:var(--muted);font-size:12px;">Open URL directly in mobile browser</p>`;
    }

    const copyBtn = document.getElementById('copy-wifi-btn');
    if (copyBtn) {
      copyBtn.onclick = () => {
        const input = document.getElementById('wifi-share-url');
        if (input) {
          navigator.clipboard.writeText(input.value).then(() => {
            copyBtn.textContent = 'Copied!';
            setTimeout(() => { copyBtn.textContent = 'Copy link'; }, 2000);
          }).catch(() => {
            input.select();
            document.execCommand('copy');
            copyBtn.textContent = 'Copied!';
            setTimeout(() => { copyBtn.textContent = 'Copy link'; }, 2000);
          });
        }
      };
    }
  } catch(e) {
    toast('Could not load Wi-Fi info: ' + e.message, true);
  }
}
function openProfileMenu(){
  const user=state.user;
  const isStock=user.role==='stock';
  const body=`<div style="display:flex;flex-direction:column;gap:16px;">
    <div style="display:flex;align-items:center;gap:14px;padding:6px 0;">
      <div class="avatar" style="width:48px;height:48px;font-size:18px;">${initials(user.name)}</div>
      <div>
        <div style="font-weight:700;font-size:16px;color:var(--ink);">${esc(user.name)}</div>
        <div style="font-size:13px;color:var(--muted);margin-top:2px;">${esc(user.email)}</div>
        <div style="margin-top:6px;"><span class="pill ${isStock?'green':'gray'}">${isStock?'Stock person':'Employee'}</span></div>
      </div>
    </div>
    <div style="display:flex;flex-direction:column;gap:8px;border-top:1px solid var(--line);padding-top:14px;">
      ${isStock?`<button class="btn btn-secondary btn-block" type="button" data-mobile-page="settings">⚙ Setup & staff accounts</button>`:''}
      <button class="btn btn-secondary btn-block" type="button" data-action="share-wifi">📶 Wi-Fi link & QR code</button>
      <button class="btn btn-danger btn-block" type="button" id="mobile-logout-btn">↪ Sign out</button>
    </div>
  </div>`;
  infoModal('Account',body);
  const logoutBtn=document.getElementById('mobile-logout-btn');
  if(logoutBtn){
    logoutBtn.onclick=async()=>{
      closeModal();
      await api('/api/logout',{method:'POST',body:'{}'});
      state.user=null;
      state.data=null;
      renderLogin(false);
    };
  }
  const settingsBtn=modalRoot.querySelector('[data-mobile-page="settings"]');
  if(settingsBtn){
    settingsBtn.onclick=()=>{
      closeModal();
      state.page='settings';
      render();
    };
  }
}

function openAction(type,itemId=''){
  if(type==='profile-menu')return openProfileMenu();
  if(type==='share-wifi')return openWifiShare();
  if(type==='employee-take')return openEmployeeTake(itemId);
  if(type==='return-unused')return openReturnUnusedStock();
  if(type==='issue'||type==='inward')return openMovement(type,itemId);
  if(type==='issue-asset')return openMovement('issue','',true);
  if(type==='request')return openPurchaseRequest();
  if(type==='count-item')return openCountItem(itemId);
  if(type==='edit-item')return openEditItem(itemId);
  if(type==='edit-user')return openEditUser(itemId);
  if(type==='add-item')return openAddItem();
  if(type==='add-location')return openAddLocation();
  if(type==='add-project')return openAddProject();
  if(type==='add-user')return openAddUser();
}

function openEmployeeTake(itemId){
  const item = state.data.items.find(x => String(x.id) === String(itemId));
  if (!item) return toast('Item not found', true);

  const availableLocations = item.locations.filter(l => l.quantity > 0 && !l.needs_count);
  const leafLocations = state.data.locations.filter(l => l.is_leaf);
  const projects = state.data.projects;
  const hasAvailableStock = item.total_qty > 0 && availableLocations.length > 0;

  const locSummary = item.locations.length ?
    item.locations.map(l => `<span class="loc-tag">${esc(l.path || l.name)}: <strong>${l.quantity} Nos</strong>${l.needs_count ? ' (needs count)' : ''}</span>`).join(' ') :
    '<span class="cell-sub">No confirmed location recorded</span>';

  const body = `
    <div style="background:#f1f7f4;border:1px solid #c7ddd2;border-radius:10px;padding:12px 14px;margin-bottom:16px;">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px;">
        <div>
          <div style="font-weight:700;font-size:16px;color:#173c35;">${esc(item.name)}</div>
          <div style="font-size:12px;color:var(--muted);margin-top:2px;">${esc(item.item_code)}${item.part_number ? ` · Part: ${esc(item.part_number)}` : ''} · ${esc(item.category)}</div>
        </div>
        <div>
          <span class="pill ${hasAvailableStock ? 'green' : 'red'}" style="font-size:12px;">${hasAvailableStock ? `${item.total_qty} Nos in stock` : 'Out of stock'}</span>
        </div>
      </div>
      <div style="font-size:12px;color:#334155;margin-top:10px;display:flex;flex-wrap:wrap;gap:6px;align-items:center;">
        <strong style="color:var(--ink);">Locations:</strong> ${locSummary}
      </div>
    </div>

    <div class="form-grid">
      <div class="form-row span-2">
        <label>Select action type</label>
        <div class="radio-card-group">
          <label class="radio-card ${!hasAvailableStock ? 'disabled' : ''}">
            <input type="radio" name="issue_type" value="already_taken" ${hasAvailableStock ? 'checked' : 'disabled'} style="margin-top:3px;">
            <div>
              <strong style="color:var(--ink);font-size:13px;">⚡ Already taken (Self-service grab)</strong>
              <div class="hint" style="margin:2px 0 0;">I have already physically picked this item from the shelf/box. Stock will deduct immediately.</div>
            </div>
          </label>
          <label class="radio-card">
            <input type="radio" name="issue_type" value="kindly_issue" ${!hasAvailableStock ? 'checked' : ''} style="margin-top:3px;">
            <div>
              <strong style="color:var(--ink);font-size:13px;">📋 Kindly issue (Request to stock person)</strong>
              <div class="hint" style="margin:2px 0 0;">Submit a request for the stock person to prepare and physically hand over this item to you.</div>
            </div>
          </label>
        </div>
      </div>

      <div class="form-row span-2">
        <label id="take-loc-label">${hasAvailableStock ? 'Storage location taken from' : 'Preferred storage location'}</label>
        <select class="select" name="location_id" id="take-location-select" required>
          ${hasAvailableStock ?
            availableLocations.map(l => `<option value="${l.id}">${esc(l.path || l.name)} (${l.quantity} Nos available)</option>`).join('') :
            leafLocations.map(l => `<option value="${l.id}">${esc(l.path || l.name)}</option>`).join('')
          }
        </select>
      </div>

      <div class="form-row">
        <label>Quantity (${esc(item.unit || 'Nos')})</label>
        <input class="field" name="quantity" type="number" min="1" step="1" value="1" required id="take-quantity-input">
        <div class="hint" id="take-qty-hint">${hasAvailableStock ? `Max available at selected location: ${availableLocations[0]?.quantity || 0}` : ''}</div>
      </div>

      <div class="form-row">
        <label>Project</label>
        <select class="select" name="project_id">
          <option value="">General/Internal</option>
          ${projects.map(p => `<option value="${p.id}">${esc(p.name)}</option>`).join('')}
        </select>
      </div>

      <div class="form-row span-2">
        <label>Purpose or notes (optional)</label>
        <textarea class="textarea" name="purpose" placeholder="e.g. IoT board prototyping, testing sensor circuit"></textarea>
      </div>
    </div>
  `;

  formModal(`Take or Request item`, body, hasAvailableStock ? 'Confirm taken' : 'Submit issue request', async fd => {
    const issueType = fd.get('issue_type') || 'already_taken';
    const payload = {
      kind: 'issue',
      issue_type: issueType,
      item_id: item.id,
      location_id: fd.get('location_id'),
      quantity: fd.get('quantity'),
      project_id: fd.get('project_id'),
      purpose: fd.get('purpose')
    };
    await api('/api/transactions', { method: 'POST', body: JSON.stringify(payload) });
  });

  const radios = modalRoot.querySelectorAll('input[name=issue_type]');
  const submitBtn = modalRoot.querySelector('#modal-form [type=submit]');
  const locSelect = document.getElementById('take-location-select');
  const locLabel = document.getElementById('take-loc-label');
  const qtyHint = document.getElementById('take-qty-hint');
  const qtyInput = document.getElementById('take-quantity-input');

  function updateTakeForm() {
    const selected = modalRoot.querySelector('input[name=issue_type]:checked')?.value;
    if (selected === 'already_taken') {
      if (submitBtn) submitBtn.textContent = 'Confirm taken';
      if (locLabel) locLabel.textContent = 'Storage location taken from';
      if (locSelect) locSelect.innerHTML = availableLocations.map(l => `<option value="${l.id}">${esc(l.path || l.name)} (${l.quantity} Nos available)</option>`).join('');
      const currentLoc = availableLocations.find(l => String(l.id) === String(locSelect?.value)) || availableLocations[0];
      if (currentLoc && qtyInput && qtyHint) {
        qtyInput.max = currentLoc.quantity;
        qtyHint.textContent = `Max available at selected location: ${currentLoc.quantity}`;
      }
    } else {
      if (submitBtn) submitBtn.textContent = 'Submit issue request';
      if (locLabel) locLabel.textContent = 'Preferred storage location';
      if (locSelect) locSelect.innerHTML = leafLocations.map(l => `<option value="${l.id}">${esc(l.path || l.name)}</option>`).join('');
      if (qtyInput) qtyInput.removeAttribute('max');
      if (qtyHint) qtyHint.textContent = 'Stock person will review and hand over.';
    }
  }

  radios.forEach(r => r.addEventListener('change', updateTakeForm));
  if (locSelect) {
    locSelect.addEventListener('change', () => {
      const selected = modalRoot.querySelector('input[name=issue_type]:checked')?.value;
      if (selected === 'already_taken') {
        const currentLoc = availableLocations.find(l => String(l.id) === String(locSelect.value));
        if (currentLoc && qtyInput && qtyHint) {
          qtyInput.max = currentLoc.quantity;
          qtyHint.textContent = `Max available at selected location: ${currentLoc.quantity}`;
        }
      }
    });
  }
}

function openReturnUnusedStock(){
  const items = state.data.items;
  const leafLocations = state.data.locations.filter(l => l.is_leaf);
  const projects = state.data.projects;

  const body = `
    <div class="notice">Return unused components or spare stock back to the stockroom. The stock person will confirm receipt into available inventory.</div>
    <div class="form-grid">
      <div class="form-row span-2">
        <label>Search item to return</label>
        <input class="field" id="return-item-search" type="search" placeholder="Type component name, code, or part #" autocomplete="off" required>
        <div class="hint" id="return-item-count">${items.length} items available in stockroom</div>
        <div class="search-results" id="return-item-results" role="listbox" hidden></div>
        <input type="hidden" name="item_id" id="return-item-id" required>
      </div>

      <div class="form-row">
        <label>Return to location</label>
        <select class="select" name="location_id" id="return-location-select" required>
          ${leafLocations.map(l => `<option value="${l.id}">${esc(l.path || l.name)}</option>`).join('')}
        </select>
      </div>

      <div class="form-row">
        <label>Quantity returned (Nos)</label>
        <input class="field" name="quantity" type="number" min="1" step="1" value="1" required>
      </div>

      <div class="form-row span-2">
        <label>Project returned from</label>
        <select class="select" name="project_id">
          <option value="">General/Internal</option>
          ${projects.map(p => `<option value="${p.id}">${esc(p.name)}</option>`).join('')}
        </select>
      </div>

      <div class="form-row span-2">
        <label>Note / reason for return</label>
        <textarea class="textarea" name="purpose" placeholder="e.g. Unused spare parts after testing"></textarea>
      </div>
    </div>
  `;

  formModal('Return unused stock', body, 'Submit return', async fd => {
    if (!fd.get('item_id')) throw new Error('Search and select an item to return');
    const payload = {
      kind: 'inward',
      item_id: fd.get('item_id'),
      location_id: fd.get('location_id'),
      quantity: fd.get('quantity'),
      project_id: fd.get('project_id'),
      purpose: `[Return unused] ${fd.get('purpose') || ''}`.trim()
    };
    await api('/api/transactions', { method: 'POST', body: JSON.stringify(payload) });
  });

  const search = document.getElementById('return-item-search');
  const results = document.getElementById('return-item-results');
  const idInput = document.getElementById('return-item-id');
  const locSelect = document.getElementById('return-location-select');

  function showMatches() {
    const q = search.value.trim().toLowerCase();
    const matches = q ? items.filter(i => `${i.name} ${i.item_code} ${i.category} ${i.part_number || ''}`.toLowerCase().includes(q)) : [];
    document.getElementById('return-item-count').textContent = q ? `${matches.length} matching item${matches.length === 1 ? '' : 's'}` : `${items.length} items available in stockroom`;
    results.innerHTML = matches.length ? matches.slice(0, 40).map(i => `<button type="button" class="search-result" role="option" data-return-item="${i.id}"><strong>${esc(i.name)}</strong><span>${esc(i.item_code)} · ${esc(i.category)} · ${i.total_qty} current stock</span></button>`).join('') : q ? '<div class="search-empty">No matching items</div>' : '';
    results.hidden = !q;
  }

  search.addEventListener('input', () => { idInput.value = ''; showMatches(); });
  search.addEventListener('focus', showMatches);
  results.addEventListener('click', e => {
    const opt = e.target.closest('[data-return-item]');
    if (!opt) return;
    const selected = items.find(i => String(i.id) === opt.dataset.returnItem);
    if (!selected) return;
    idInput.value = selected.id;
    search.value = `${selected.name} · ${selected.item_code}`;
    results.hidden = true;
    if (selected.locations.length && locSelect) {
      locSelect.value = selected.locations[0].id;
    }
  });
}

function openMovement(kind,itemId='',assetsOnly=false){
  const issue=kind==='issue';
  if(issue && state.user.role!=='stock') return toast('Only the stock person can record stock issues directly', true);
  const items=(issue?state.data.items.filter(i=>i.total_qty>0&&!i.needs_count||i.id==itemId):state.data.items).filter(i=>!assetsOnly||i.kind==='asset'), projects=state.data.projects, locations=state.data.locations;
  const employee=state.data.users.find(u=>u.id===state.user.id)||state.data.users[0];
  const people=state.data.users.map(u=>({...u,search_label:`${u.name} — ${u.email}`}));
  const selectedItem=items.find(i=>String(i.id)===String(itemId));
  const body=`<div class="form-grid"><div class="form-row span-2"><label>Search items</label><input class="field" id="move-item-search" type="search" placeholder="Search name, item code, category, or part number" value="${esc(selectedItem?`${selectedItem.name} · ${selectedItem.item_code}`:'')}" autocomplete="off" required><div class="hint" id="move-item-count">${items.length} items available</div><div class="search-results" id="move-item-results" role="listbox" hidden></div><input type="hidden" name="item_id" id="move-item" value="${esc(itemId)}"></div>
    <div class="form-row"><label>Location</label><select class="select" name="location_id" id="move-location" required><option value="">Choose location</option></select></div>
    <div class="form-row"><label>Quantity (Nos)</label><input class="field" type="number" name="quantity" min="1" step="1" required placeholder="e.g. 2"></div>
    ${issue?`<div class="form-row span-2"><label>Person receiving the item</label><input class="field" name="issued_to" id="issued-to" list="issued-to-list" value="${esc(employee?`${employee.name} — ${employee.email}`:'')}" placeholder="Search employee name or email" required><datalist id="issued-to-list">${people.map(p=>`<option value="${esc(p.search_label)}"></option>`).join('')}</datalist><div class="hint">Type a name or email and choose a matching employee.</div></div>`:''}
    ${issue?`<div class="form-row span-2"><label>Project</label><select class="select" name="project_id"><option value="">General/Internal</option>${projects.map(p=>`<option value="${p.id}">${esc(p.name)}</option>`).join('')}</select></div>`:''}
    <div class="form-row span-2"><label>${issue?'Purpose (optional)':'Reference or note (optional)'}</label><textarea class="textarea" name="purpose" placeholder="Add a short note if useful"></textarea></div></div>
    ${issue?`<div class="notice">Stock will reduce as soon as this issue is saved. The recorder, recipient, and project are added to movement history.</div>`:`<div class="notice">This inward entry will remain pending. The stock person must confirm it before the available quantity increases.</div>`}`;
  formModal(issue?'Record stock issue':'Record stock inward',body,issue?'Confirm issue':'Submit inward',async fd=>{if(!fd.get('item_id'))throw new Error('Search for an item and choose it from the results');const payload={kind,item_id:fd.get('item_id'),location_id:fd.get('location_id'),quantity:fd.get('quantity'),project_id:fd.get('project_id'),purpose:fd.get('purpose')};if(issue){const recipient=people.find(p=>p.search_label===fd.get('issued_to'));if(!recipient)throw new Error('Choose a person from the employee suggestions');payload.issued_to_id=recipient.id;}await api('/api/transactions',{method:'POST',body:JSON.stringify(payload)});});
  const itemSel=document.getElementById('move-item'),locSel=document.getElementById('move-location'),itemSearch=document.getElementById('move-item-search'),itemResults=document.getElementById('move-item-results');
  function loadLoc(){const i=state.data.items.find(x=>x.id==itemSel.value);let ls=state.data.locations.filter(l=>l.is_leaf);if(issue)ls=ls.filter(l=>i?.locations.some(x=>x.id===l.id&&x.quantity>0&&!x.needs_count));locSel.innerHTML=opts(ls,issue?'Choose where you took it from':'Choose the receiving location',l=>l.path||l.name);}
  function showItemMatches(){const query=itemSearch.value.trim().toLowerCase(),matches=query?items.filter(i=>`${i.name} ${i.item_code} ${i.category} ${i.part_number||''}`.toLowerCase().includes(query)):[];document.getElementById('move-item-count').textContent=query?`${matches.length} matching item${matches.length===1?'':'s'}`:`${items.length} items available`;itemResults.innerHTML=matches.length?matches.slice(0,40).map(i=>`<button type="button" class="search-result" role="option" data-move-item="${i.id}"><strong>${esc(i.name)}</strong><span>${esc(i.item_code)} · ${esc(i.category)} · ${i.total_qty} available</span></button>`).join(''):query?'<div class="search-empty">No matching items</div>':'';itemResults.hidden=!query;}
  itemSearch.addEventListener('input',()=>{itemSel.value='';loadLoc();showItemMatches();});
  itemResults.addEventListener('click',e=>{const option=e.target.closest('[data-move-item]');if(!option)return;const selected=items.find(i=>String(i.id)===option.dataset.moveItem);if(!selected)return;itemSel.value=selected.id;itemSearch.value=`${selected.name} · ${selected.item_code}`;itemResults.hidden=true;loadLoc();});
  itemSearch.addEventListener('focus',showItemMatches);itemSearch.addEventListener('keydown',e=>{if(e.key==='Escape')itemResults.hidden=true;});
  itemSel.addEventListener('change',loadLoc);if(itemId)loadLoc();
}

function openPurchaseRequest(){
  const body=`<div class="form-grid"><div class="form-row span-2"><label>Project</label><select class="select" name="project_id"><option value="">General/Internal</option>${state.data.projects.map(p=>`<option value="${p.id}">${esc(p.name)}</option>`).join('')}</select></div>
    <div class="form-row span-2"><label>Purpose</label><textarea class="textarea" name="purpose" placeholder="What is this needed for?"></textarea></div></div><div class="notice">Requested by <strong>${esc(state.user.name)}</strong>. Your account name is recorded with this request.</div><div id="request-lines"></div><button class="btn btn-secondary btn-small" type="button" id="add-request-line">＋ Add another item</button><div class="hint">Enter what you need, add a vendor or product link if you have one, and use inventory search only when the item is already listed.</div>`;
  formModal('New purchase request',body,'Submit request',async fd=>{
    const lines=[...modalRoot.querySelectorAll('.line-card')].map(row=>({item_id:row.querySelector('[name=item_id]').value||null,item_name:row.querySelector('[name=item_name]').value,vendor:row.querySelector('[name=vendor]').value,product_url:row.querySelector('[name=product_url]').value,quantity:row.querySelector('[name=quantity]').value}));
    await api('/api/requests',{method:'POST',body:JSON.stringify({project_id:fd.get('project_id'),purpose:fd.get('purpose'),lines})});
  },true);
  const container=document.getElementById('request-lines');
  function addLine(){
    const number=container.children.length+1;
    const div=document.createElement('div');div.className='line-card';
    div.innerHTML=`<div class="line-header"><span>Item ${number}</span>${number>1?'<button type="button" class="remove-line">Remove</button>':''}</div><div class="form-grid"><div class="form-row span-2"><label>Search inventory (optional)</label><input class="field request-item-search" type="search" placeholder="Search name, code, category, or part number" autocomplete="off"><div class="search-results request-item-results" role="listbox" hidden></div><input type="hidden" name="item_id" value=""></div><div class="form-row span-2"><label>Item name or description</label><input class="field" name="item_name" placeholder="Enter the item you need" required></div><div class="form-row"><label>Vendor (optional)</label><input class="field" name="vendor" placeholder="Vendor or store name"></div><div class="form-row"><label>Product link (optional)</label><input class="field" name="product_url" type="url" placeholder="https://..."></div><div class="form-row"><label>Quantity</label><input class="field" name="quantity" type="number" min="1" step="1" required></div></div>`;
    container.appendChild(div);
    div.querySelector('.remove-line')?.addEventListener('click',()=>div.remove());
    const search=div.querySelector('.request-item-search'),results=div.querySelector('.request-item-results'),idInput=div.querySelector('[name=item_id]'),nameInput=div.querySelector('[name=item_name]');
    search.addEventListener('input',()=>{
      if(idInput.value){idInput.value='';nameInput.value='';}
      const q=search.value.trim().toLowerCase();
      const matches=q?state.data.items.filter(i=>`${i.name} ${i.item_code} ${i.category} ${i.part_number||''}`.toLowerCase().includes(q)):[];
      results.innerHTML=matches.length?matches.slice(0,40).map(i=>`<button type="button" class="search-result" role="option" data-request-item="${i.id}"><strong>${esc(i.name)}</strong><span>${esc(i.item_code)} · ${esc(i.category)} · ${i.total_qty} in stock</span></button>`).join(''):q?'<div class="search-empty">No matching item. Enter it manually below.</div>':'';
      results.hidden=!q;
    });
    results.addEventListener('click',e=>{
      const option=e.target.closest('[data-request-item]');if(!option)return;
      const item=state.data.items.find(i=>String(i.id)===option.dataset.requestItem);if(!item)return;
      idInput.value=item.id;nameInput.value=item.name;search.value=`${item.name} · ${item.item_code}`;results.hidden=true;
    });
    search.addEventListener('keydown',e=>{if(e.key==='Escape')results.hidden=true;});
  }
  addLine();document.getElementById('add-request-line').addEventListener('click',addLine);
}

function openAddItem(){
  const cats = [...new Set(state.data.items.map(i=>i.category))].sort();
  const catList = `<datalist id="category-options">${cats.map(c=>`<option value="${esc(c)}">`).join('')}</datalist>`;
  const body=`<div class="form-grid"><div class="form-row span-2"><label>Item name</label><input class="field" name="name" required></div><div class="form-row"><label>Category</label><input class="field" name="category" list="category-options" placeholder="Select or type category">${catList}</div><div class="form-row"><label>Part number (optional)</label><input class="field" name="part_number"></div><div class="form-row"><label>Type</label><select class="select" name="kind"><option value="consumable">Consumable</option><option value="asset">Reusable asset</option></select></div><div class="form-row"><label>Minimum quantity (optional)</label><input class="field" name="min_qty" type="number" min="0" step="1" placeholder="Set a low-stock alert"></div><div class="form-row span-2"><label>Opening quantity</label><input class="field" name="quantity" type="number" min="0" step="1" value="0"><div class="hint">Use zero if the stock person will count it later. A nonzero opening balance is saved as a stock transaction.</div></div><div class="form-row span-2"><label>Storage location</label><select class="select" name="location_id"><option value="">Select if entering an opening quantity</option>${state.data.locations.filter(l=>l.is_leaf).map(l=>`<option value="${l.id}">${esc(l.path||l.name)}</option>`).join('')}</select></div></div>`;
  formModal('Add inventory item',body,'Save item',async fd=>{await api('/api/items',{method:'POST',body:JSON.stringify(Object.fromEntries(fd.entries()))});});
}
function openEditItem(itemId){
  const item=state.data.items.find(x=>x.id==itemId);if(!item)return;
  const leafLocations=state.data.locations.filter(l=>l.is_leaf);
  const locationRows=item.locations.map(l=>`<div class="form-row"><label>Move from: ${esc(l.path||l.name)} · ${l.quantity} Nos${l.needs_count?' · count needed':''}</label><select class="select" data-location-from="${l.id}" required>${opts(leafLocations,'Choose destination',x=>x.path||x.name,l.id)}</select></div>`).join('');
  const cats = [...new Set(state.data.items.map(i=>i.category))].sort();
  const catList = `<datalist id="category-options">${cats.map(c=>`<option value="${esc(c)}">`).join('')}</datalist>`;
  const body=`<div class="form-grid"><div class="form-row span-2"><label>Item name</label><input class="field" name="name" value="${esc(item.name)}" required></div><div class="form-row"><label>Category</label><input class="field" name="category" list="category-options" value="${esc(item.category)}">${catList}</div><div class="form-row"><label>Part number</label><input class="field" name="part_number" value="${esc(item.part_number||'')}"></div><div class="form-row"><label>Type</label><select class="select" name="kind"><option value="consumable" ${item.kind==='consumable'?'selected':''}>Consumable</option><option value="asset" ${item.kind==='asset'?'selected':''}>Reusable asset</option></select></div><div class="form-row"><label>Minimum quantity</label><input class="field" name="min_qty" type="number" min="0" step="1" value="${item.min_qty??''}" placeholder="Leave blank to disable alert"></div></div><div class="form-row" style="margin-top:18px"><strong>Storage locations</strong><div class="hint">${item.locations.length ? 'Choose a new location to move that location’s entire item balance. The quantity and count status are preserved.' : 'Assign an initial storage location for this item.'}</div></div>${locationRows||`<div class="form-row"><label>Assign storage location</label><select class="select" name="assign_location_id">${opts(leafLocations,'Choose location',x=>x.path||x.name)}</select></div>`}`;
  formModal('Edit inventory item',body,'Save changes',async fd=>{const payload=Object.fromEntries(fd.entries());payload.location_changes=[...modalRoot.querySelectorAll('[data-location-from]')].map(sel=>({from_id:sel.dataset.locationFrom,to_id:sel.value}));await api(`/api/items/${itemId}/edit`,{method:'POST',body:JSON.stringify(payload)});});
}
function openCountItem(itemId){
  const item=state.data.items.find(x=>x.id==itemId);if(!item)return;
  const leafLocations=state.data.locations.filter(l=>l.is_leaf);
  const uncounted=item.locations.filter(l=>l.needs_count);
  const defaultLocId=uncounted.length?uncounted[0].id:(item.locations[0]?.id||'');
  const body=`<div class="notice warning">Count the physical stock at a location. The recorded quantity will update the stock and confirm it.</div><div class="form-row"><label>Item</label><input class="field" value="${esc(item.name)}" disabled></div><div class="form-row"><label>Storage location</label><select class="select" name="location_id" required>${item.locations.length ? item.locations.map(l=>`<option value="${l.id}" ${l.id==defaultLocId?'selected':''}>${esc(l.path||l.name)} · current ${l.quantity}${l.needs_count?' · [Needs count]':''}</option>`).join('') : opts(leafLocations,'Choose storage location',l=>l.path||l.name)}</select></div><div class="form-row"><label>Physical quantity counted</label><input class="field" name="quantity" type="number" min="0" step="1" required placeholder="Enter counted physical units"></div><div class="form-row"><label>Reason / note</label><textarea class="textarea" name="reason" required placeholder="Physical count during setup / review"></textarea></div>`;
  formModal('Verify physical stock',body,'Save count',async fd=>api(`/api/items/${itemId}/count`,{method:'POST',body:JSON.stringify(Object.fromEntries(fd.entries()))}));
}
function openAddLocation(){const body=`<div class="form-row"><label>Inside</label><select class="select" name="parent_id">${opts(state.data.locations,'Stock Room (top level)',l=>l.path||l.name)}</select></div><div class="form-row"><label>New folder / location name</label><input class="field" name="name" required placeholder="e.g. Box 21"></div><div class="hint">Choose a parent to build paths such as Stock Room / IoT Rack-C / C-3 / Box-21.</div>`;formModal('Add storage location',body,'Save location',async fd=>api('/api/locations',{method:'POST',body:JSON.stringify(Object.fromEntries(fd.entries()))}));}
function openAddProject(){const body=`<div class="form-row"><label>Project name</label><input class="field" name="name" required placeholder="e.g. Water automation"></div>`;formModal('Add project',body,'Save project',async fd=>api('/api/projects',{method:'POST',body:JSON.stringify(Object.fromEntries(fd.entries()))}));}
function openAddUser(){const body=`<div class="form-grid"><div class="form-row span-2"><label>Employee name</label><input class="field" name="name" required></div><div class="form-row span-2"><label>Company email</label><input class="field" name="email" type="email" required></div><div class="form-row"><label>Role</label><select class="select" name="role"><option value="employee">Employee</option><option value="stock">Stock person</option></select></div><div class="form-row"><label>Temporary password</label><input class="field" name="password" type="password" minlength="8" required></div></div><div class="notice warning">Use a unique password. This office-only V1 uses HTTP, so don’t reuse a password from another service.</div>`;formModal('Add user',body,'Create account',async fd=>api('/api/users',{method:'POST',body:JSON.stringify(Object.fromEntries(fd.entries()))}));}
function openEditUser(userId){
  const user = state.data.users.find(u => String(u.id) === String(userId));
  if (!user) return toast('User not found', true);
  const isSelf = user.id === state.user.id;
  const body = `<div class="form-grid">
    <div class="form-row span-2"><label>Employee name</label><input class="field" name="name" value="${esc(user.name)}" required></div>
    <div class="form-row span-2"><label>Company email</label><input class="field" name="email" type="email" value="${esc(user.email)}" required></div>
    <div class="form-row span-2"><label>Role</label><select class="select" name="role"><option value="employee" ${user.role==='employee'?'selected':''}>Employee</option><option value="stock" ${user.role==='stock'?'selected':''}>Stock person</option></select></div>
    <div class="form-row span-2"><label>Reset password (optional)</label><input class="field" name="password" type="password" minlength="8" placeholder="Leave blank to keep current password"><div class="hint">Only enter a new password if you want to reset it for this person.</div></div>
  </div>
  ${!isSelf ? `
    <div style="margin-top:16px;padding-top:14px;border-top:1px solid var(--line);display:flex;justify-content:space-between;align-items:center;">
      <div><strong style="font-size:12px;color:var(--ink);">Deactivate account</strong><div class="hint" style="margin:2px 0 0;">Remove sign-in access for this user.</div></div>
      <button class="btn btn-danger btn-small" type="button" id="deactivate-user-btn">Deactivate user</button>
    </div>
  ` : ''}`;
  formModal('Edit user account', body, 'Save changes', async fd => {
    await api(`/api/users/${userId}/edit`, {
      method: 'POST',
      body: JSON.stringify(Object.fromEntries(fd.entries()))
    });
  });
  const deactBtn = document.getElementById('deactivate-user-btn');
  if (deactBtn) {
    deactBtn.onclick = async () => {
      if (!confirm(`Are you sure you want to deactivate ${user.name}'s account?`)) return;
      try {
        await api(`/api/users/${userId}`, { method: 'DELETE' });
        closeModal();
        await refresh();
        toast('User account deactivated');
      } catch (err) {
        toast(err.message, true);
      }
    };
  }
}
function openConsumeModal(loanId){
  const loan = (state.data.checkouts || state.data.loans || []).find(x => String(x.id) === String(loanId));
  if (!loan) return toast('Item not found', true);
  const remaining = loan.remaining_qty !== undefined ? loan.remaining_qty : loan.quantity;
  const projects = state.data.projects;

  const body = `
    <div style="background:#f1f7f4;border:1px solid #c7ddd2;border-radius:10px;padding:12px 14px;margin-bottom:16px;">
      <div style="font-weight:700;font-size:15px;color:#173c35;">${esc(loan.item_name)}</div>
      <div style="font-size:12px;color:var(--muted);margin-top:2px;">Currently with you: <strong>${remaining} Nos</strong> · Taken from: ${esc(loan.location_path || loan.location_code)}</div>
    </div>
    <div class="form-grid">
      <div class="form-row span-2">
        <label>Quantity used</label>
        <input class="field" name="quantity" type="number" min="1" max="${remaining}" step="1" value="${remaining}" required>
        <div class="hint">How many units were used up (max ${remaining})?</div>
      </div>
      <div class="form-row span-2">
        <label>Project</label>
        <select class="select" name="project_id">
          <option value="">General/Internal</option>
          ${projects.map(p => `<option value="${p.id}" ${String(loan.project_id) === String(p.id) ? 'selected' : ''}>${esc(p.name)}</option>`).join('')}
        </select>
      </div>
      <div class="form-row span-2">
        <label>Remarks / note (optional)</label>
        <textarea class="textarea" name="purpose" placeholder="e.g. Soldered onto PCB prototype, built into enclosure, damaged during test"></textarea>
      </div>
    </div>
    <div class="notice">This closes the item as used. It won't need to be returned.</div>
  `;

  formModal('Mark item as used', body, 'Confirm used', async fd => {
    const payload = {
      quantity: fd.get('quantity'),
      project_id: fd.get('project_id'),
      purpose: fd.get('purpose')
    };
    await api(`/api/loans/${loanId}/consume`, { method: 'POST', body: JSON.stringify(payload) });
  });
}

function openReturn(loanId){
  const loan = (state.data.checkouts || state.data.loans || []).find(x => String(x.id) === String(loanId));
  if (!loan) return toast('Item not found', true);
  const remaining = loan.remaining_qty !== undefined ? loan.remaining_qty : loan.quantity;
  const leafLocations = state.data.locations.filter(l => l.is_leaf);

  const body = `
    <div style="background:#f1f7f4;border:1px solid #c7ddd2;border-radius:10px;padding:12px 14px;margin-bottom:16px;">
      <div style="font-weight:700;font-size:15px;color:#173c35;">${esc(loan.item_name)}</div>
      <div style="font-size:12px;color:var(--muted);margin-top:2px;">Currently with you: <strong>${remaining} Nos</strong></div>
    </div>
    <div class="form-grid">
      <div class="form-row span-2">
        <label>Quantity returning to shelf</label>
        <input class="field" name="quantity" type="number" min="1" max="${remaining}" step="1" value="${remaining}" required>
        <div class="hint">You can return all or part of the quantity (max ${remaining}).</div>
      </div>
      <div class="form-row span-2">
        <label>Return to storage location</label>
        <select class="select" name="location_id" required>
          ${leafLocations.map(l => `<option value="${l.id}" ${String(loan.location_id) === String(l.id) ? 'selected' : ''}>${esc(l.path || l.name)}</option>`).join('')}
        </select>
      </div>
      <div class="form-row span-2">
        <label>Condition / note (optional)</label>
        <textarea class="textarea" name="condition" placeholder="Unused leftover components, or tool condition"></textarea>
      </div>
    </div>
    <div class="notice">The stock person will verify receipt on the shelf and confirm the return.</div>
  `;

  formModal('Return item to shelf', body, 'Submit return to shelf', async fd => {
    const payload = {
      quantity: fd.get('quantity'),
      location_id: fd.get('location_id'),
      condition: fd.get('condition')
    };
    await api(`/api/loans/${loanId}/return`, { method: 'POST', body: JSON.stringify(payload) });
  });
}
function openReceive(requestId){
  const req = state.data.requests.find(x => x.id == requestId);
  if (!req) return;
  const lines = req.lines.filter(l => l.received_quantity < l.quantity);
  if (!lines.length) return toast('All items in this request have already been received.');
  const cats = [...new Set(state.data.items.map(i => i.category))].sort();
  const catList = `<datalist id="receive-category-options">${cats.map(c => `<option value="${esc(c)}">`).join('')}</datalist>`;
  const firstLine = lines[0];
  const remainingQty = firstLine.quantity - firstLine.received_quantity;

  const body = `<div class="form-grid">
    <div class="form-row span-2">
      <label>Request item</label>
      <select class="select" name="line_id" id="receive-line" required>
        ${lines.map(l => `<option value="${l.id}" data-item-name="${esc(l.item_name)}" data-remaining="${l.quantity - l.received_quantity}">${esc(l.item_name)} · remaining ${l.quantity - l.received_quantity} of ${l.quantity}</option>`).join('')}
      </select>
    </div>
    <div class="form-row">
      <label>Received quantity</label>
      <input class="field" name="quantity" id="receive-qty-input" type="number" min="1" max="${remainingQty}" value="${remainingQty}" step="1" required>
      <div class="hint" id="receive-qty-hint">Remaining to receive: ${remainingQty}</div>
    </div>
    <div class="form-row">
      <label>Storage location</label>
      <select class="select" name="location_id" required>
        ${opts(state.data.locations.filter(l => l.is_leaf), 'Choose location', l => l.path || l.name)}
      </select>
    </div>
    <div class="form-row span-2">
      <label>Item name (in catalog)</label>
      <input class="field" name="name" id="receive-item-name" value="${esc(firstLine.item_name || '')}" required>
    </div>
    <div class="form-row span-2">
      <label>Category (for new item)</label>
      <input class="field" name="category" list="receive-category-options" placeholder="Select or type category">${catList}
    </div>
  </div>
  <div class="notice">Confirmed receipt increases stock immediately. If partial quantity is received, the request stays open.</div>`;

  formModal('Record goods received', body, 'Confirm receipt', async fd => {
    await api(`/api/requests/${requestId}/receive`, { method: 'POST', body: JSON.stringify(Object.fromEntries(fd.entries())) });
  });

  const selLine = document.getElementById('receive-line');
  if (selLine) {
    selLine.addEventListener('change', () => {
      const opt = selLine.selectedOptions[0];
      if (!opt) return;
      const rem = parseInt(opt.dataset.remaining, 10) || 1;
      const qtyInput = document.getElementById('receive-qty-input');
      const qtyHint = document.getElementById('receive-qty-hint');
      const nameInput = document.getElementById('receive-item-name');
      if (qtyInput) { qtyInput.max = rem; qtyInput.value = rem; }
      if (qtyHint) { qtyHint.textContent = `Remaining to receive: ${rem}`; }
      if (nameInput && opt.dataset.itemName) { nameInput.value = opt.dataset.itemName; }
    });
  }
}

(async function start(){
  try {
    const status=await api('/api/setup-status');
    if(status.setup_required){renderLogin(true);return;}
    const me=await api('/api/me');
    if(!me.user){renderLogin(false);return;}
    await refresh();
  } catch(e) { app.innerHTML=`<section class="loading-screen"><div class="brand-mark">!</div><strong>Could not connect to the stockroom</strong><p>${esc(e.message)}</p></section>`; }
})();
