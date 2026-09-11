const API_BASE=(window.ATI_API_BASE||'').replace(/\/$/,'');
const state = {
  historyReady: false,
  lastAttendanceDates: {},
  view: 'home',
  cameraStream: null,
  cameraFacing: 'environment',
  currentExamId: null,
  cameraBusy: false,
};

const $ = (s, root = document) => root.querySelector(s);
const $$ = (s, root = document) => [...root.querySelectorAll(s)];
const today = () => { const d = new Date(); const tz = d.getTimezoneOffset(); return new Date(d.getTime() - tz*60000).toISOString().slice(0,10); };

function navigateTo(view, push=true){
  const target = view || 'home';
  if(push && state.historyReady && state.view !== target) history.pushState({view:target},'',`#${target}`);
  state.view=target;
  setView(target);
}
window.addEventListener('popstate',()=>{ const v=(location.hash||'#home').slice(1); setView(v in {home:1,students:1,scores:1,checker:1,attendance:1,analytics:1,reports:1,settings:1}?v:'home',false); });
window.addEventListener('beforeunload',()=>{ if(state.cameraStream) state.cameraStream.getTracks().forEach(t=>t.stop()); });
window.addEventListener('online',async()=>{await syncOfflineQueue();await setQueuedStatus();try{await render();}catch{}});
window.addEventListener('offline',()=>{setQueuedStatus();});
window.setInterval(()=>syncOfflineQueue(),15000);
window.addEventListener('visibilitychange',()=>{if(!document.hidden)syncOfflineQueue();});
document.addEventListener('click',e=>{
  const nav=e.target.closest('[data-view]');
  if(nav){ e.preventDefault(); navigateTo(nav.dataset.view,true); }
});

const ICONS = {
  home:'<path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1V10Z"/>',
  users:'<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>',
  user:'<circle cx="12" cy="7" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
  score:'<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M8 7h8M8 11h2M12 11h4M8 15h2M12 15h4M8 18h8"/>',
  scan:'<path d="M3 7V5a2 2 0 0 1 2-2h2M17 3h2a2 2 0 0 1 2 2v2M21 17v2a2 2 0 0 1-2 2h-2M7 21H5a2 2 0 0 1-2-2v-2"/><rect x="7" y="7" width="10" height="10" rx="2"/>',
  calendar:'<rect x="3" y="4" width="18" height="17" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
  chart:'<path d="M4 19V5M4 19h17"/><path d="m7 15 4-5 3 3 5-7"/>',
  file:'<path d="M6 3h8l4 4v14H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z"/><path d="M14 3v5h5M8 12h8M8 16h8"/>',
  settings:'<path d="M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z"/><path d="M19.4 15a1.8 1.8 0 0 0 .36 1.98l.06.06-1.42 1.42-.06-.06A1.8 1.8 0 0 0 16.36 18a1.8 1.8 0 0 0-1.09 1.62V20h-2v-.38A1.8 1.8 0 0 0 12.18 18a1.8 1.8 0 0 0-1.98.36l-.06.06-1.42-1.42.06-.06A1.8 1.8 0 0 0 9 15.36 1.8 1.8 0 0 0 7.38 14H7v-2h.38A1.8 1.8 0 0 0 9 10.92a1.8 1.8 0 0 0-.36-1.98l-.06-.06L10 7.46l.06.06A1.8 1.8 0 0 0 12.04 7 1.8 1.8 0 0 0 13.13 5.38V5h2v.38A1.8 1.8 0 0 0 16.22 7a1.8 1.8 0 0 0 1.98-.36l.06-.06 1.42 1.42-.06.06a1.8 1.8 0 0 0-.36 1.98A1.8 1.8 0 0 0 20.88 11H21v2h-.38A1.8 1.8 0 0 0 19.4 15Z"/>',
  plus:'<path d="M12 5v14M5 12h14"/>',
  edit:'<path d="m4 16 9.8-9.8a2.1 2.1 0 0 1 3 0l1 1a2.1 2.1 0 0 1 0 3L8 20H4v-4Z"/><path d="m13 7 4 4"/>',
  archive:'<path d="M4 7h16M6 7v13h12V7M9 11h6"/><rect x="3" y="4" width="18" height="3" rx="1"/>',
  close:'<path d="m6 6 12 12M18 6 6 18"/>',
  upload:'<path d="M12 16V4M7 9l5-5 5 5"/><path d="M5 20h14"/>',
  flip:'<path d="M7 7h8l-2-2M17 17H9l2 2"/><path d="M19 7v6a5 5 0 0 1-5 5M5 17v-6a5 5 0 0 1 5-5"/>',
  arrow:'<path d="M5 12h13M13 6l6 6-6 6"/>',
  check:'<path d="m5 12 4 4L19 6"/>',
  warning:'<path d="M12 4 3 20h18L12 4Z"/><path d="M12 9v5M12 17h.01"/>',
  calendarPrev:'<path d="m15 18-6-6 6-6"/>',
  calendarNext:'<path d="m9 18 6-6-6-6"/>',
  search:'<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/>',
  download:'<path d="M12 3v12M7 10l5 5 5-5M5 21h14"/>',
  spark:'<path d="m12 3 1.5 5.5L19 10l-5.5 1.5L12 17l-1.5-5.5L5 10l5.5-1.5L12 3Z"/>',
  logout:'<path d="M10 5H6a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h4"/><path d="M14 8l4 4-4 4M9 12h9"/>',
};
function icon(name, cls='') { return `<svg class="icon ${cls}" viewBox="0 0 24 24" aria-hidden="true">${ICONS[name]||ICONS.file}</svg>`; }
$$('[data-icon]').forEach(el => el.innerHTML = icon(el.dataset.icon));

function esc(value) { return String(value ?? '').replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m])); }
function initials(name='Student') { return name.trim().split(/\s+/).slice(0,2).map(x=>x[0]?.toUpperCase()||'').join('') || 'S'; }
function showToast(message, kind='') {
  const t = $('#toast'); t.textContent = String(message); t.className = `toast show ${kind}`;
  clearTimeout(showToast.timer); showToast.timer = setTimeout(() => t.className='toast', 3000);
}
function messageFromDetail(detail) {
  if (!detail) return 'Request failed.';
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map(x => typeof x === 'string' ? x : (x?.msg || JSON.stringify(x))).join('; ');
  if (typeof detail === 'object') return detail.msg || detail.message || JSON.stringify(detail);
  return String(detail);
}
function apiErrorMessage(err) { return messageFromDetail(err?.message) || 'Something went wrong.'; }

const OFFLINE_DB_NAME='ati-local-v7';
const OFFLINE_DB_VERSION=1;
const OFFLINE_ALLOWED_MUTATIONS=new Set(['/api/attendance','/api/attendance/bulk','/api/scores']);
let offlineSyncBusy=false;
function openOfflineDB(){return new Promise((resolve,reject)=>{if(!('indexedDB' in window))return reject(new Error('Offline storage is unavailable on this device.'));const req=indexedDB.open(OFFLINE_DB_NAME,OFFLINE_DB_VERSION);req.onupgradeneeded=()=>{const db=req.result;if(!db.objectStoreNames.contains('cache'))db.createObjectStore('cache');if(!db.objectStoreNames.contains('outbox')){const st=db.createObjectStore('outbox',{keyPath:'operation_id'});st.createIndex('created_at','created_at');}if(!db.objectStoreNames.contains('meta'))db.createObjectStore('meta');};req.onsuccess=()=>resolve(req.result);req.onerror=()=>reject(req.error||new Error('Offline storage failed'));});}
async function localPut(store,key,value){try{const db=await openOfflineDB();await new Promise((resolve,reject)=>{const tx=db.transaction(store,'readwrite');tx.objectStore(store).put(value,key);tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error);});db.close();}catch{}}
async function localGet(store,key){try{const db=await openOfflineDB();const v=await new Promise((resolve,reject)=>{const tx=db.transaction(store,'readonly');const req=tx.objectStore(store).get(key);req.onsuccess=()=>resolve(req.result);req.onerror=()=>reject(req.error);});db.close();return v;}catch{return undefined}}
async function clearOfflineData(){try{const db=await openOfflineDB();await new Promise((resolve,reject)=>{const tx=db.transaction(['cache','outbox','meta'],'readwrite');['cache','outbox','meta'].forEach(n=>tx.objectStore(n).clear());tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error);});db.close();}catch{}}
async function localCacheEntries(){try{const db=await openOfflineDB();const rows=await new Promise((resolve,reject)=>{const tx=db.transaction('cache','readonly');const st=tx.objectStore('cache');const req=st.openCursor();const out=[];req.onsuccess=()=>{const c=req.result;if(!c)return resolve(out);out.push([c.key,c.value]);c.continue();};req.onerror=()=>reject(req.error);});db.close();return rows;}catch{return[]}}
async function optimisticLocalUpdate(path,body){try{const entries=await localCacheEntries();for(const [key,val] of entries){if(typeof key!=='string'||!key.startsWith('/api/'))continue;if(path==='/api/attendance' && key.startsWith('/api/attendance?attendance')){const u=new URL(key,'https://offline.local');if(u.searchParams.get('attendance_date')===String(body.date)&&Array.isArray(val?.rows)){val.rows=val.rows.map(r=>r.student_id===body.student_id?{...r,status:body.status,recorded:true}:r);await localPut('cache',key,val);}}else if(path==='/api/attendance/bulk' && key.startsWith('/api/attendance?attendance')){const u=new URL(key,'https://offline.local');if(u.searchParams.get('attendance_date')===String(body.date)&&Array.isArray(val?.rows)){const ids=new Set((body.student_ids||[]).map(Number));val.rows=val.rows.map(r=>ids.has(Number(r.student_id))?{...r,status:body.status,recorded:true}:r);await localPut('cache',key,val);}}else if(path==='/api/scores' && key.startsWith('/api/scores?assessment_id=')){const u=new URL(key,'https://offline.local');if(u.searchParams.get('assessment_id')===String(body.assessment_id)&&Array.isArray(val)){val=val.map(r=>r.student_id===body.student_id?{...r,status:body.status,score:body.status==='zero'?0:(['entered'].includes(body.status)?body.score:null)}:r);await localPut('cache',key,val);}}}}catch{}}
async function localDelete(store,key){try{const db=await openOfflineDB();await new Promise((resolve,reject)=>{const tx=db.transaction(store,'readwrite');tx.objectStore(store).delete(key);tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error);});db.close();}catch{}}
async function localOutboxAll(){try{const db=await openOfflineDB();const rows=await new Promise((resolve,reject)=>{const tx=db.transaction('outbox','readonly');const req=tx.objectStore('outbox').getAll();req.onsuccess=()=>resolve(req.result||[]);req.onerror=()=>reject(req.error);});db.close();return rows.sort((a,b)=>a.created_at.localeCompare(b.created_at));}catch{return[]}}
async function setQueuedStatus(){const q=await localOutboxAll();const el=$('#connection-status');if(!el)return;if(!navigator.onLine){el.textContent=`Offline · ${q.length} change${q.length===1?'':'s'} waiting`;el.classList.add('offline');}else if(q.length){el.textContent=`Syncing · ${q.length} pending`;el.classList.add('offline');}else{el.textContent='';el.classList.remove('offline');}}
async function cacheKey(path){return path;}
async function queueMutation(path,method,body){const op={operation_id:`op-${crypto.randomUUID?crypto.randomUUID():Date.now()+'-'+Math.random().toString(16).slice(2)}`,method,path,body:typeof body==='string'&&body?JSON.parse(body):body,created_at:new Date().toISOString()};await localPut('outbox',op.operation_id,op);await optimisticLocalUpdate(path,op.body);await setQueuedStatus();return {queued:true,operation_id:op.operation_id};}
async function syncOfflineQueue(){if(offlineSyncBusy||!navigator.onLine)return;offlineSyncBusy=true;try{const ops=await localOutboxAll();if(!ops.length){await setQueuedStatus();return;}let i=0;while(i<ops.length&&navigator.onLine){const chunk=ops.slice(i,i+100);try{const r=await fetch(`${API_BASE}/api/sync`,{method:'POST',credentials:'include',headers:{'Content-Type':'application/json','X-CSRF-Token':cookieValue('ati_csrf')},body:JSON.stringify({operations:chunk.map(({operation_id,method,path,body})=>({operation_id,method,path,body}))})});if(!r.ok)break;const payload=await r.json();for(const result of payload.results||[]){if(['applied','already_applied','rejected'].includes(result.status))await localDelete('outbox',result.operation_id);}i+=chunk.length;await setQueuedStatus();}catch{break;}}}finally{offlineSyncBusy=false;}}
function cookieValue(name){const row=document.cookie.split('; ').find(x=>x.startsWith(name+'='));return row?decodeURIComponent(row.slice(name.length+1)):'';}
function titleFor(view) { return ({home:'Today',students:'Students',scores:'Assessments',checker:'AI Checker',attendance:'Attendance',analytics:'Analytics',reports:'Reports',settings:'Setup'}[view]) || 'Today'; }
function emptyState(title, body, actionText='', action='') {
  return `<div class="empty-state"><div class="empty-icon">${icon('users')}</div><h3>${esc(title)}</h3><p class="muted">${esc(body)}</p>${actionText?`<button class="primary" data-action="${esc(action)}">${esc(actionText)}</button>`:''}</div>`;
}
function modal(title, body, actions='') {
  const root=$('#modal-root');
  root.innerHTML=`<div class="modal" id="generic-modal"><div class="modal-backdrop" data-close-modal></div><div class="modal-card"><div class="modal-head"><div><div class="eyebrow">AI Teacher Intelligence</div><h3>${esc(title)}</h3></div><button class="icon-btn" data-close-modal aria-label="Close">${icon('close')}</button></div><div>${body}</div>${actions?`<div class="modal-actions">${actions}</div>`:''}</div></div>`;
  $$('[data-close-modal]').forEach(b=>b.onclick=()=>root.innerHTML='');
  return root.querySelector('.modal-card');
}

async function api(path, opts={}) {
  const headers = {...(opts.headers || {})};
  if(window.Capacitor) headers['X-ATI-Mobile']='1';
  if (!(opts.body instanceof FormData)) headers['Content-Type'] = headers['Content-Type'] || 'application/json';
  const method=(opts.method||'GET').toUpperCase();
  if (method!=='GET' && method!=='HEAD' && method!=='OPTIONS') { const csrf=cookieValue('ati_csrf'); if(csrf) headers['X-CSRF-Token']=csrf; }
  const isGet=['GET','HEAD'].includes(method);
  const key=await cacheKey(path);
  if(isGet && !navigator.onLine){const cached=await localGet('cache',key);if(cached!==undefined)return cached;throw new Error('This screen has not been cached yet. Connect once to download its data.');}
  if(!isGet && !navigator.onLine && OFFLINE_ALLOWED_MUTATIONS.has(path)){
    let body={};try{body=typeof opts.body==='string'?JSON.parse(opts.body):opts.body||{};}catch{throw new Error('This change cannot be queued offline.');}
    if(path==='/api/attendance'&&body.student_id&&body.date){const cachedKey=`/api/attendance?class_id=${body.class_id||''}&attendance_date=${body.date}`;}
    return queueMutation(path,method,body);
  }
  try{
    const response = await fetch(`${API_BASE}${path}`, {...opts, credentials:'include', headers});
    let payload=null; try { payload=await response.json(); } catch {}
    if (!response.ok) { if(response.status===401) logout(false); throw new Error(messageFromDetail(payload?.detail)||response.statusText||'Request failed'); }
    if(isGet) await localPut('cache',key,payload);
    else { const entries=await localGet('meta','cache_version')||0; await localPut('meta','cache_version',entries+1); }
    return payload;
  }catch(err){
    if(isGet){const cached=await localGet('cache',key);if(cached!==undefined)return cached;}
    if(!isGet && OFFLINE_ALLOWED_MUTATIONS.has(path) && (err instanceof TypeError || /failed to fetch|networkerror|load failed|cannot reach/i.test(String(err?.message||'')))){
      let body={};try{body=typeof opts.body==='string'?JSON.parse(opts.body):opts.body||{};}catch{throw err;}
      return queueMutation(path,method,body);
    }
    throw err instanceof Error?err:new Error(String(err));
  }
}

function setView(view, syncHistory=true) {
  state.view=view;
  $$('.nav').forEach(btn=>btn.classList.toggle('active', btn.dataset.view===view));
  $('#page-title').textContent=titleFor(view);
  if (window.innerWidth <= 820) window.scrollTo({top:0,behavior:'smooth'});
}

async function boot() {
  try {
    const [me,school] = await Promise.all([api('/api/me'), api('/api/school')]);
    let health=await localGet('cache','__health__');
    if(navigator.onLine){try{health=await fetch(`${API_BASE}/api/health`,{credentials:'include'}).then(r=>r.json());await localPut('cache','__health__',health);}catch{}}
    if(!health) health={gemini_configured:false,model:'offline'};
    $('#login').classList.add('hidden'); $('#app').classList.remove('hidden');
    $('#user-name').textContent=me.full_name; $('#school-name').textContent=school.name;
    $('#user-avatar').textContent=initials(me.full_name);
    $('#api-status').textContent=health.gemini_configured ? `Gemini ready · ${health.model}` : 'Core ready · Gemini not configured';
    setView((location.hash||'#home').slice(1) || 'home'); await render();
    state.historyReady=true;
    history.replaceState({view:state.view},'',`#${state.view}`);
    await setQueuedStatus();
    if(navigator.onLine) syncOfflineQueue();
  } catch (err) {
    $('#app').classList.add('hidden'); $('#login').classList.remove('hidden'); $('#login-error').textContent=apiErrorMessage(err);
  }
}

async function logout(reload=true) { try{ await api('/api/auth/logout',{method:'POST'}); }catch(e){} await clearOfflineData(); if(reload) location.reload(); }

function setAuthMode(mode){
  const signin=mode==='signin';
  $('#login-form').classList.toggle('hidden',!signin); $('#signup-form').classList.toggle('hidden',signin);
  $('#signin-tab').classList.toggle('active',signin); $('#signup-tab').classList.toggle('active',!signin);
  $('#signin-tab').setAttribute('aria-selected',String(signin)); $('#signup-tab').setAttribute('aria-selected',String(!signin));
  $('#auth-title').textContent=signin?'Welcome back.':'Create your teaching workspace.';
  $('#auth-lead').textContent=signin?'Sign in to your private teaching workspace.':'Start with an empty workspace and build your roster your way.';
  $('#login-error').textContent='';
}
$('#signin-tab').onclick=()=>setAuthMode('signin'); $('#signup-tab').onclick=()=>setAuthMode('signup');
$('#login-form').addEventListener('submit', async e=>{
  e.preventDefault(); $('#login-error').textContent='';
  try {
    const r=await fetch(`${API_BASE}/api/auth/login`,{method:'POST',headers:{'Content-Type':'application/json'},credentials:'include',body:JSON.stringify({email:$('#email').value.trim(),password:$('#password').value})});
    const p=await r.json(); if(!r.ok) throw new Error(messageFromDetail(p?.detail)||'Sign in failed.');
    await boot();
  } catch(err) { $('#login-error').textContent=apiErrorMessage(err); }
});
$('#signup-form').addEventListener('submit', async e=>{
  e.preventDefault(); $('#login-error').textContent='';
  const p1=$('#signup-password').value, p2=$('#signup-password-confirm').value;
  if(p1!==p2){$('#login-error').textContent='Passwords do not match.';return;}
  try {
    const r=await fetch(`${API_BASE}/api/auth/signup`,{method:'POST',headers:{'Content-Type':'application/json'},credentials:'include',body:JSON.stringify({email:$('#signup-email').value.trim(),full_name:$('#signup-name').value.trim(),school_name:$('#signup-school').value.trim(),password:p1,password_confirm:p2})});
    const p=await r.json(); if(!r.ok) throw new Error(messageFromDetail(p?.detail)||'Account creation failed.');
    showToast('Workspace created. Welcome!','ok'); await boot();
  } catch(err) { $('#login-error').textContent=apiErrorMessage(err); }
});
$('#logout').onclick=()=>logout(); $('#mobile-account')?.addEventListener('click',()=>logout()); $('#account-settings')?.addEventListener('click', accountSecurityModal); $('#app-back')?.addEventListener('click',()=>{if(history.length>1)history.back();else navigateTo('home',true);});
$$('#nav .nav, #mobile-nav .nav').forEach(btn=>btn.addEventListener('click',(e)=>{e.preventDefault();navigateTo(btn.dataset.view,true);}));
$('#global-add').onclick=()=>quickAdd();
document.addEventListener('keydown',e=>{
  if(['INPUT','TEXTAREA','SELECT'].includes(e.target.tagName) || e.metaKey || e.ctrlKey || e.altKey) return;
  const keys={'1':'home','2':'students','3':'scores','4':'checker','5':'attendance','6':'analytics','7':'reports','8':'settings'};
  if(keys[e.key]) { navigateTo(keys[e.key],true); }
});

async function render() {
  const f={home:renderHome,students:renderStudents,scores:renderScores,checker:renderChecker,attendance:renderAttendance,analytics:renderAnalytics,reports:renderReports,settings:renderSettings}[state.view];
  if(!f)return; $('#view').innerHTML='<div class="card notice">Loading workspace…</div>';
  try { await f(); } catch(err) { $('#view').innerHTML=`<div class="card notice warn"><strong>Could not load this section.</strong><br>${esc(apiErrorMessage(err))}</div>`; }
}

async function dashboardData(){ return api('/api/dashboard'); }
async function renderHome(){
  const [d,classes,students,types,subjects] = await Promise.all([dashboardData(),api('/api/classes'),api('/api/students?limit=1000'),api('/api/assessment-types'),api('/api/subjects')]);
  const setupDone = classes.length>0 && students.length>0 && subjects.length>0 && types.some(t=>t.enabled);
  $('#nav-students-count').textContent=d.students;
  $('#nav-today-count').textContent=d.pending_ai_reviews + d.missing_scores;
  $('#view').innerHTML=`
    <div class="grid kpi-grid">
      <div class="card kpi-card"><div class="kpi-label">Active students</div><div class="kpi">${d.students}</div><div class="muted small">Your current roster</div></div>
      <div class="card kpi-card"><div class="kpi-label">Classes</div><div class="kpi">${d.classes}</div><div class="muted small">All active classes</div></div>
      <div class="card kpi-card"><div class="kpi-label">Reviews waiting</div><div class="kpi">${d.pending_ai_reviews}</div><div class="muted small">Teacher verification</div></div>
      <div class="card kpi-card"><div class="kpi-label">Scanned papers</div><div class="kpi">${d.submissions}</div><div class="muted small">Processed exam history</div></div>
    </div>
    ${setupDone ? '' : `<div class="section card"><div class="eyebrow">First-run setup</div><h3 style="margin-top:5px">Build your workspace</h3><p class="muted">Nothing is preloaded. Complete only the steps you actually use.</p><div class="setup-progress">
      ${[['classes','Create a class',classes.length>0,'settings'],['students','Add students',students.length>0,'students'],['subjects','Add subjects',subjects.length>0,'settings'],['assessments','Create an assessment type',types.length>0,'settings']].map(([k,l,done,v])=>`<button class="setup-step ${done?'done':''}" data-setup-view="${v}"><span class="step-icon">${done?icon('check'):'·'}</span><span><strong>${l}</strong><small>${done?'Completed':'Open setup'}</small></span></button>`).join('')}
    </div></div>`}
    <div class="section card"><div class="toolbar"><div><div class="eyebrow">Quick actions</div><h3 style="margin:4px 0 0">Common teacher tasks</h3></div></div><div class="quick-grid">
      ${quick('students','users','Add students','Build or update your roster')}
      ${quick('scores','score','Enter scores','Open the assessment gradebook')}
      ${quick('checker','scan','Scan exam','Capture a paper with the camera')}
      ${quick('attendance','calendar','Take attendance','Mark P / A in one tap')}
    </div></div>
    <div class="section split">
      <div class="card"><h3>What needs attention</h3>
        <div class="list-row"><div class="row-left"><span class="badge-icon">${icon('warning')}</span><div class="row-main"><strong>AI reviews</strong><span>Results awaiting teacher decision</span></div></div><strong>${d.pending_ai_reviews}</strong></div>
        <div class="list-row"><div class="row-left"><span class="badge-icon">${icon('score')}</span><div class="row-main"><strong>Missing scores</strong><span>Scores not entered yet</span></div></div><strong>${d.missing_scores}</strong></div>
        <div class="list-row"><div class="row-left"><span class="badge-icon">${icon('users')}</span><div class="row-main"><strong>Students needing support</strong><span>Based on current stored evidence</span></div></div><strong>${d.students_needing_attention}</strong></div>
      </div>
      <div class="card"><h3>System principles</h3>
        ${[['Evidence once','Calculations update automatically'],['Teacher review','AI never silently becomes final'],['Memory','Mistakes build a history'],['Privacy','Student data stays in your workspace']].map(([a,b])=>`<div class="metric-row"><span>${a}</span><span class="pill">${b}</span></div>`).join('')}
      </div>
    </div>`;
  $$('.quick[data-view]').forEach(b=>b.onclick=()=>navigateTo(b.dataset.view,true));
  $$('[data-setup-view]').forEach(b=>b.onclick=()=>navigateTo(b.dataset.setupView,true));
}
function quick(view,iconName,title,sub){return `<button class="quick" data-view="${view}"><span class="quick-icon">${icon(iconName)}</span><strong>${title}</strong><span>${sub}</span></button>`;}

async function renderStudents(){
  const classes=await api('/api/classes');
  $('#view').innerHTML=`<div class="page-hero"><div><div class="eyebrow">Roster management</div><h1>Students</h1><p class="muted">Build the roster once. Class numbers are assigned automatically in alphabetical order.</p></div><div class="hero-actions"><button id="add-student" class="primary">${icon('plus')} Add student</button><label class="secondary file-drop-inline">${icon('upload')} Import CSV<input id="student-csv" type="file" accept=".csv,text/csv" hidden></label></div></div><div class="toolbar"><select id="student-class" class="stretch"><option value="">All active classes</option>${classes.map(c=>`<option value="${c.id}">${esc(c.name)} · ${esc(c.grade_level)} · ${c.student_count}</option>`).join('')}</select><div class="search-field stretch">${icon('search')}<input id="student-search" placeholder="Search students" aria-label="Search students"></div><span id="student-total" class="pill">0</span></div><div class="card"><div class="section-head"><div><h3>Active roster</h3><div class="helper">No student is created until you add or import one.</div></div></div><div id="student-table"></div></div><div class="section card"><div class="section-head"><div><div class="eyebrow">Roster rule</div><h3>Automatic class numbering</h3><p class="muted">The first name alphabetically is No. 1. Adding, renaming, or archiving students can change the displayed numbers.</p></div></div></div>`;
  const load=async()=>{
    const params=new URLSearchParams(); const cid=$('#student-class').value; const q=$('#student-search').value.trim(); if(cid)params.set('class_id',cid); if(q)params.set('q',q); params.set('limit','1000');
    let rows; try{rows=await api(`/api/students?${params.toString()}`);}catch(err){$('#student-table').innerHTML=`<div class="notice warn">${esc(apiErrorMessage(err))}</div>`;return;}
    $('#student-total').textContent=`${rows.length} student${rows.length===1?'':'s'}`;
    $('#student-table').innerHTML=rows.length?`<div class="table-wrap"><table class="table roster-table"><thead><tr><th>No.</th><th>Student</th><th>Class</th><th>Average</th><th>Attendance</th><th></th></tr></thead><tbody>${rows.map(s=>{const c=classes.find(x=>x.id===s.class_id);return `<tr><td><span class="roll-number">${esc(s.student_code)}</span></td><td><div class="student-cell"><div class="student-avatar">${esc(initials(s.full_name))}</div><div class="student-meta"><strong>${esc(s.full_name)}</strong><span>Student profile</span></div></div></td><td>${esc(c?.name||'—')}</td><td><strong>${s.average}%</strong></td><td>${s.attendance}%</td><td><div class="action-group"><button class="mini-btn" data-profile="${s.id}">${icon('user')} Profile</button><button class="icon-btn" data-edit="${s.id}" title="Edit student" aria-label="Edit ${esc(s.full_name)}">${icon('edit')}</button></div></td></tr>`}).join('')}</tbody></table></div>`:emptyState('Your roster is empty','Add a student or import a CSV roster. The app will assign class numbers automatically.','Add student','add-student');
    $$('[data-edit]', $('#student-table')).forEach(b=>b.onclick=()=>studentModal(rows.find(s=>s.id===+b.dataset.edit),classes));
    $$('[data-profile]', $('#student-table')).forEach(b=>b.onclick=()=>profileModal(+b.dataset.profile));
    $$('[data-action="add-student"]', $('#student-table')).forEach(b=>b.onclick=()=>studentModal(null,classes));
  };
  $('#student-class').onchange=load; $('#student-search').oninput=()=>{clearTimeout(load.t);load.t=setTimeout(load,160);}; $('#add-student').onclick=()=>studentModal(null,classes); $('#student-csv').onchange=async e=>{const file=e.target.files?.[0];if(!file)return;const cid=$('#student-class').value;if(!cid){showToast('Choose a class before importing students.','warn');e.target.value='';return;}const fd=new FormData();fd.append('upload',file,file.name);try{const r=await api(`/api/students/import?class_id=${cid}`,{method:'POST',body:fd});showToast(`${r.added} students imported · ${r.skipped} skipped`,'ok');await renderStudents();}catch(err){showToast(apiErrorMessage(err),'warn');}finally{e.target.value='';}}; await load();
}

function studentModal(student,classes){
  if(!classes.length){showToast('Create a class before adding students.','warn');return;}
  const body=`<div class="form-grid"><label>Class<select id="m-class">${classes.map(c=>`<option value="${c.id}" ${student?.class_id===c.id?'selected':''}>${esc(c.name)} · ${esc(c.grade_level)}</option>`).join('')}</select></label><label>Class number<div class="readonly-field">${student?esc(student.student_code):'Assigned automatically'}</div><span class="helper">Numbers follow alphabetical order in the class and update automatically when the roster changes.</span></label><label class="full">Full name<input id="m-name" value="${esc(student?.full_name||'')}" placeholder="Full student name" autocomplete="off" autofocus></label></div><div class="notice section">The system assigns the student's number. You do not need to create or remember a code.</div>`;
  const actions=`<button class="secondary" data-close-modal>Cancel</button><button class="primary" id="save-student">${student?'Save changes':'Add student'}</button>`;
  const card=modal(student?'Edit student':'Add student',body,actions);
  card.querySelector('#save-student').onclick=async()=>{
    const payload={class_id:+$('#m-class',card).value,student_code:'',full_name:$('#m-name',card).value.trim()};
    if(!payload.class_id||!payload.full_name){showToast('Choose a class and enter the full name.','warn');return;}
    try{const saved=await api(student?`/api/students/${student.id}`:'/api/students',{method:student?'PATCH':'POST',body:JSON.stringify(payload)});$('#modal-root').innerHTML='';showToast(`${student?'Student updated':'Student added'} · No. ${saved.student_code}`,'ok');renderStudents();}
    catch(e){showToast(apiErrorMessage(e),'warn');}
  };
  $$('[data-close-modal]',card).forEach(b=>b.onclick=()=>$('#modal-root').innerHTML='');
  if(student){const old=card.querySelector('.modal-actions'); const arch=document.createElement('button');arch.className='danger-btn';arch.textContent='Archive student';old.prepend(arch);arch.onclick=async()=>{if(!confirm(`Archive ${student.full_name}?`))return;try{await api(`/api/students/${student.id}/archive`,{method:'POST'});$('#modal-root').innerHTML='';showToast('Student archived','ok');renderStudents();}catch(e){showToast(apiErrorMessage(e),'warn');}};}
}

async function profileModal(id){
  try{const d=await api(`/api/students/${id}/profile`);const s=d.student;const history=d.assessments?.length?`<div class="profile-list">${d.assessments.map(a=>`<div class="list-row"><div class="row-main"><strong>${esc(a.title)}</strong><span>${esc(a.date)} · ${a.score??'—'} / ${a.max_score}</span></div><span class="status-chip ${a.passed?'good':'bad'}">${a.passed?'Passed':'Below pass mark'}</span></div>`).join('')}</div>`:'<div class="notice">No assessment evidence yet.</div>';const mistakes=d.mistakes?.length?d.mistakes.map(m=>`<div class="list-row"><div class="row-main"><strong>${esc(m.mistake_type)}</strong><span>${esc(m.topic)}</span></div><span class="pill">${m.occurrences}×</span></div>`).join(''):'<div class="notice">No repeated mistake evidence yet.</div>';const body=`<div class="profile-hero"><div class="student-avatar profile-avatar">${esc(initials(s.name))}</div><div><div class="eyebrow">Student profile</div><h3>${esc(s.name)}</h3><div class="muted">No. ${esc(s.code)}</div></div></div><div class="grid profile-stats"><div class="stat-box"><span>Overall</span><strong>${d.overall}%</strong></div><div class="stat-box"><span>Attendance</span><strong>${d.attendance.attendance_percent}%</strong></div><div class="stat-box"><span>Absences</span><strong>${d.attendance.absent}</strong></div><div class="stat-box"><span>Pass mark</span><strong>${d.pass_mark}%</strong></div></div><div class="section"><h4>Assessment history</h4>${history}</div><div class="section"><h4>Repeated mistakes</h4>${mistakes}</div><div class="section"><h4>Recommended focus</h4><div class="notice">${esc(d.recommendations?.[0]||'Collect more evidence before recommending a topic.')}</div></div>`;modal('Student profile',body,'<button class="primary" data-close-modal>Done</button>');}catch(e){showToast(apiErrorMessage(e),'warn');}
}

async function renderScores(){
  const [classes,assessments]=await Promise.all([api('/api/classes'),api('/api/assessments')]);
  $('#view').innerHTML=`<div class="toolbar"><select id="score-assessment" class="stretch"><option value="">Choose an assessment</option>${assessments.map(a=>`<option value="${a.id}">${esc(a.title)} · ${esc(a.subject)} · ${esc(a.class_id?'Class-specific':'All classes')}</option>`).join('')}</select><button id="new-assessment" class="secondary"><span>${icon('plus')}</span>Create assessment</button><button id="score-refresh" class="secondary">Refresh</button></div><div id="score-area">${assessments.length?emptyState('Choose an assessment','Select an assessment above to open its fast score grid.','',''):emptyState('No assessments yet','Create an assessment type and an assessment before entering scores.','Open setup','settings')}</div>`;
  $('#new-assessment').onclick=()=>assessmentModal(classes); $('#score-refresh').onclick=()=>renderScores(); $('#score-assessment').onchange=()=>loadScoreGrid(+$('#score-assessment').value);
}
async function loadScoreGrid(id){
  if(!id)return;const area=$('#score-area');area.innerHTML='<div class="card notice">Loading score grid…</div>';
  try{const [rows,assessments]=await Promise.all([api(`/api/scores?assessment_id=${id}`),api('/api/assessments')]);const a=assessments.find(x=>x.id===id);area.innerHTML=`<div class="card"><div class="toolbar"><div><div class="eyebrow">${esc(a?.subject||'')}</div><h3 style="margin:4px 0 0">${esc(a?.title||'Assessment')}</h3><div class="helper">Maximum ${a?.max_score??'—'} · Weight ${a?.weight??0}% · Mode: ${a?.grading_mode==='ai'?'AI checking':'Teacher entry'} · Empty is never treated as zero</div></div><span class="pill">${rows.length} students</span></div>${rows.length?`<div class="table-wrap"><table class="table"><thead><tr><th>Student</th><th>Score</th><th>Status</th><th></th></tr></thead><tbody>${rows.map(s=>`<tr><td><div class="student-cell"><div class="student-avatar">${esc(initials(s.student))}</div><div class="student-meta"><strong>${esc(s.student)}</strong><span>${esc(s.code)}</span></div></div></td><td><input data-score-input="${s.student_id}" type="number" min="0" max="${a?.max_score||100}" step="0.1" value="${s.score??''}" aria-label="Score for ${esc(s.student)}"></td><td><select data-score-status="${s.student_id}"><option value="empty" ${s.status==='empty'?'selected':''}>Empty</option><option value="entered" ${s.status==='entered'?'selected':''}>Entered</option><option value="zero" ${s.status==='zero'?'selected':''}>Zero</option><option value="absent" ${s.status==='absent'?'selected':''}>Absent</option><option value="excused" ${s.status==='excused'?'selected':''}>Excused</option><option value="not_applicable" ${s.status==='not_applicable'?'selected':''}>N/A</option></select></td><td><button class="mini-btn primary" data-save-score="${s.student_id}">${icon('check')} Save</button></td></tr>`).join('')}</tbody></table></div>`:emptyState('No students in this assessment','Create students in the selected class before entering scores.','Add students','students')}</div>`;
    $$('[data-save-score]',area).forEach(b=>b.onclick=async()=>{const sid=+b.dataset.saveScore;const input=$(`[data-score-input="${sid}"]`,area);const status=$(`[data-score-status="${sid}"]`,area).value;const score=input.value===''?null:+input.value;try{const r=await api('/api/scores',{method:'POST',body:JSON.stringify({student_id:sid,assessment_id:id,status,score})});b.textContent='Saved';setTimeout(()=>b.innerHTML=icon('check')+' Save',700);showToast(r?.queued?'Saved offline · will sync automatically':'Score saved','ok');}catch(e){showToast(apiErrorMessage(e),'warn');}});
  }catch(e){area.innerHTML=`<div class="notice warn">${esc(apiErrorMessage(e))}</div>`;}
}
function assessmentModal(classes){
  Promise.all([api('/api/subjects'),api('/api/assessment-types')]).then(([subjects,types])=>{
    if(!subjects.length||!types.some(t=>t.enabled)){showToast('Create a subject and an enabled assessment type first.','warn');setView('settings');render();return;}
    const body=`<div class="form-grid"><label>Class<select id="am-class"><option value="">All classes</option>${classes.map(c=>`<option value="${c.id}">${esc(c.name)} · ${esc(c.grade_level)}</option>`).join('')}</select></label><label>Subject<select id="am-subject">${subjects.map(s=>`<option value="${s.id}">${esc(s.name)}</option>`).join('')}</select></label><label>Assessment type<select id="am-type">${types.filter(t=>t.enabled).map(t=>`<option value="${t.id}">${esc(t.name)} · ${t.max_score} pts · ${t.weight}%</option>`).join('')}</select></label><label>Date<input id="am-date" type="date" value="${today()}"></label><label>Checking mode<select id="am-mode"><option value="manual">Teacher enters scores</option><option value="ai">AI checks papers</option></select></label><label class="full">Title<input id="am-title" placeholder="e.g. Chapter 2 Test"></label></div><div class="notice section"><strong>Choose once:</strong> Teacher mode keeps the score grid fast and fully manual. AI mode enables the camera checker for this assessment.</div>`;
    const card=modal('Create assessment',body,'<button class="secondary" data-close-modal>Cancel</button><button class="primary" id="create-assessment">Create assessment</button>');
    card.querySelector('#create-assessment').onclick=async()=>{const payload={assessment_type_id:+$('#am-type',card).value,subject_id:+$('#am-subject',card).value,title:$('#am-title',card).value.trim(),date:$('#am-date',card).value,class_id:$('#am-class',card).value?+$('#am-class',card).value:null,grading_mode:$('#am-mode',card).value};if(!payload.title){showToast('Assessment title is required.','warn');return;}try{await api('/api/assessments',{method:'POST',body:JSON.stringify(payload)});$('#modal-root').innerHTML='';showToast('Assessment created','ok');renderScores();}catch(e){showToast(apiErrorMessage(e),'warn');}};
    $$('[data-close-modal]',card).forEach(b=>b.onclick=()=>$('#modal-root').innerHTML='');
  }).catch(e=>showToast(apiErrorMessage(e),'warn'));
}

let examsCache=[];
async function renderChecker(){
  const [exams,classes,subjects,assessments]=await Promise.all([api('/api/exams'),api('/api/classes'),api('/api/subjects'),api('/api/assessments')]); examsCache=exams;
  $('#view').innerHTML=`<div class="page-hero"><div><div class="eyebrow">Assessment intelligence</div><h1>AI Checker</h1><p class="muted">Capture papers in any order. Safe matches are stored automatically; uncertain papers stay in review.</p></div><div class="hero-actions"><button id="create-exam" class="secondary">${icon('plus')} New exam</button></div></div><div class="toolbar"><select id="checker-exam" class="stretch"><option value="">Choose an exam</option>${exams.map(e=>`<option value="${e.id}">${esc(e.title)} · ${esc(e.class_name)} · ${esc(e.subject)}</option>`).join('')}</select></div><div id="checker-area">${exams.length?emptyState('Choose an exam','Select an exam to use the camera, batch-scan a large stack, or review processed papers.','',''):emptyState('No exams yet','Create an exam, add its questions and start scanning.','Create exam','new-exam')}</div>`;
  $('#create-exam').onclick=()=>examModal(classes,subjects,assessments); $('#checker-exam').onchange=()=>loadExam(+$('#checker-exam').value);
}
async function loadExam(id){
  if(!id)return; const area=$('#checker-area');area.innerHTML='<div class="card notice">Loading exam…</div>';
  try{
    const [exam,questions,submissions]=await Promise.all([api('/api/exams'),api(`/api/exams/${id}/questions`),api(`/api/exams/${id}/submissions?limit=20`)]);
    const e=exam.find(x=>x.id===id);
    const history=submissions.length?`<div class="review-list">${submissions.map(s=>`<div class="queue-item"><div><strong>${esc(s.detected_name||'Unidentified paper')}</strong><small class="muted" style="display:block;margin-top:3px">${s.detected_code?`No. ${esc(s.detected_code)} · `:''}${new Date(s.created_at).toLocaleString()}</small></div><span class="status-chip ${s.status==='completed'?'good':'warn'}">${esc(s.status.replaceAll('_',' '))}</span></div>`).join('')}</div>`:'<div class="notice">No papers processed yet.</div>';
    const body=`<div class="page-grid-two"><div><div class="card scan-launch"><div class="eyebrow">${esc(e.subject)}</div><h3>${esc(e.title)}</h3><p class="muted">${esc(e.class_name)} · ${e.total_marks} marks</p><div class="scan-actions"><button class="primary xl" id="open-camera">${icon('scan')} Open camera</button><label class="secondary file-drop-inline">${icon('upload')} Select papers<input id="batch-file" type="file" accept="image/jpeg,image/png,image/webp" multiple hidden></label></div><div class="helper section">One paper at a time with the camera, or select up to 150 images for rapid batch processing. Paper order does not matter.</div></div><div class="card"><div class="toolbar"><div><div class="eyebrow">Batch processing</div><h3 style="margin:4px 0 0">Process a stack</h3></div><span class="pill">Up to 150 papers</span></div><div id="batch-summary" class="notice">Select image files to start. The system will identify each student independently and auto-store safe results.</div><div id="batch-progress"></div></div></div><div><div class="card"><div class="toolbar"><h3 style="margin:0">Questions</h3><span class="pill">${questions.length}</span></div>${questions.length?questions.map(q=>`<div class="list-row"><div class="row-main"><strong>Q${q.question_no} · ${esc(q.answer_type)}</strong><span>${esc(q.question_text)}</span></div><span class="pill">${q.max_score} pts</span></div>`).join(''):'<div class="notice warn">Add questions before AI checking. The AI will not invent them.</div>'}<button class="secondary section" id="add-question">${icon('plus')} Add question</button></div><div class="card"><div class="toolbar"><div><div class="eyebrow">Recent papers</div><h3 style="margin:4px 0 0">Processing history</h3></div></div>${history}</div></div></div>`;
    area.innerHTML=body;$('#open-camera').onclick=()=>openCamera(id);$('#add-question').onclick=()=>questionModal(id);
    const fileInput=$('#batch-file');fileInput.onchange=async()=>{const files=[...fileInput.files||[]];if(!files.length)return;if(files.length>150){showToast('Select no more than 150 papers per batch.','warn');fileInput.value='';return;}await startBatchScan(id,files);fileInput.value='';};
  }catch(e){area.innerHTML=`<div class="notice warn">${esc(apiErrorMessage(e))}</div>`;}
}
async function startBatchScan(examId, files){
  const summary=$('#batch-summary'), progress=$('#batch-progress'); if(!summary||!progress)return;
  summary.className='notice';summary.textContent=`Uploading ${files.length} paper${files.length===1?'':'s'}…`;
  progress.innerHTML='<div class="progress-line"><span style="width:3%"></span></div><div class="helper section">Preparing secure processing queue…</div>';
  const fd=new FormData();files.forEach(f=>fd.append('uploads',f,f.name));
  try{const job=await api(`/api/exams/${examId}/scan-batch`,{method:'POST',body:fd}); summary.className='notice';summary.innerHTML=`Batch #${job.job_id} is processing. You can stay on this page while papers are checked.`; await pollBatch(job.job_id); await loadExam(examId);}
  catch(e){summary.className='notice warn';summary.textContent=apiErrorMessage(e);}
}
async function pollBatch(jobId){
  const progress=$('#batch-progress'); if(!progress)return;
  for(let i=0;i<900;i++){const j=await api(`/api/scan-jobs/${jobId}`);const pct=j.progress_percent||0;progress.innerHTML=`<div class="progress-line"><span style="width:${pct}%"></span></div><div class="batch-stats"><div class="stat-box"><span>Processed</span><strong>${j.completed_files}/${j.total_files}</strong></div><div class="stat-box"><span>Auto stored</span><strong>${j.auto_stored_files}</strong></div><div class="stat-box"><span>Review</span><strong>${j.review_required_files}</strong></div><div class="stat-box"><span>Failed</span><strong>${j.failed_files}</strong></div></div>`;if(['completed','completed_with_errors','failed'].includes(j.status))return;await new Promise(r=>setTimeout(r,900));}
}

function examModal(classes,subjects,assessments){
  if(!classes.length||!subjects.length){showToast('Create at least one class and one subject first.','warn');setView('settings');render();return;}
  const body=`<div class="form-grid"><label>Class<select id="em-class">${classes.map(c=>`<option value="${c.id}">${esc(c.name)} · ${esc(c.grade_level)}</option>`).join('')}</select></label><label>Subject<select id="em-subject">${subjects.map(s=>`<option value="${s.id}">${esc(s.name)}</option>`).join('')}</select></label><label>Linked assessment<select id="em-assessment"><option value="">None</option>${assessments.map(a=>`<option value="${a.id}">${esc(a.title)} · ${esc(a.subject)}</option>`).join('')}</select></label><label>Total marks<input id="em-marks" type="number" min="1" step="0.1" value="100"></label><label class="full">Exam title<input id="em-title" placeholder="e.g. Midterm Examination"></label><label class="full">Answer key / rubric<input id="em-key" placeholder="Paste a concise answer key or rubric (optional)"></label></div><div class="notice section">For reliable AI grading, add explicit questions and an answer key/rubric. The system keeps uncertain cases for teacher review.</div>`;
  const card=modal('Create exam',body,'<button class="secondary" data-close-modal>Cancel</button><button class="primary" id="create-exam-save">Create exam</button>');
  card.querySelector('#create-exam-save').onclick=async()=>{const p={class_id:+$('#em-class',card).value,subject_id:+$('#em-subject',card).value,assessment_id:$('#em-assessment',card).value?+$('#em-assessment',card).value:null,title:$('#em-title',card).value.trim(),total_marks:+$('#em-marks',card).value,answer_key:$('#em-key',card).value.trim()||null};if(!p.title){showToast('Exam title is required.','warn');return;}try{const created=await api('/api/exams',{method:'POST',body:JSON.stringify(p)});$('#modal-root').innerHTML='';renderChecker().then(()=>{if($('#checker-exam')){$('#checker-exam').value=created.id;loadExam(created.id);}});showToast('Exam created','ok');}catch(e){showToast(apiErrorMessage(e),'warn');}};
  $$('[data-close-modal]',card).forEach(b=>b.onclick=()=>$('#modal-root').innerHTML='');
}
function questionModal(examId){
  const body=`<div class="form-grid"><label>Question number<input id="qm-no" type="number" min="1" step="1"></label><label>Maximum score<input id="qm-max" type="number" min="0.1" step="0.1" value="1"></label><label>Answer type<select id="qm-type"><option value="multiple_choice">Multiple choice</option><option value="true_false">True / False</option><option value="short_answer" selected>Short answer</option><option value="definition">Definition</option><option value="mathematics">Mathematics</option><option value="science">Science</option><option value="essay">Essay</option></select></label><label>Topic<input id="qm-topic" placeholder="e.g. Photosynthesis"></label><label class="full">Question text<textarea id="qm-text" placeholder="Enter the exact question"></textarea></label></div>`;
  const card=modal('Add exam question',body,'<button class="secondary" data-close-modal>Cancel</button><button class="primary" id="save-question">Add question</button>');
  card.querySelector('#save-question').onclick=async()=>{const p={exam_id:examId,question_no:+$('#qm-no',card).value,question_text:$('#qm-text',card).value.trim(),max_score:+$('#qm-max',card).value,topic:$('#qm-topic',card).value.trim()||null,answer_type:$('#qm-type',card).value};if(!p.question_no||!p.question_text||!p.max_score){showToast('Question number, text and maximum score are required.','warn');return;}try{await api('/api/questions',{method:'POST',body:JSON.stringify(p)});$('#modal-root').innerHTML='';showToast('Question added','ok');loadExam(examId);}catch(e){showToast(apiErrorMessage(e),'warn');}};$$('[data-close-modal]',card).forEach(b=>b.onclick=()=>$('#modal-root').innerHTML='');
}

async function openCamera(examId){
  state.currentExamId=examId;const m=$('#camera-modal');m.classList.remove('hidden');m.setAttribute('aria-hidden','false');$('#camera-status').textContent='Starting camera…';$('#capture-photo').disabled=true;
  try{await startCamera();}catch(e){$('#camera-status').textContent='Camera unavailable — use photo upload instead';showToast(apiErrorMessage(e),'warn');}
}
async function startCamera(){stopCamera();const constraints={video:{facingMode:{ideal:state.cameraFacing},width:{ideal:1920},height:{ideal:1440}},audio:false};state.cameraStream=await navigator.mediaDevices.getUserMedia(constraints);const video=$('#camera-video');video.srcObject=state.cameraStream;await video.play();$('#camera-status').textContent='Camera ready';$('#capture-photo').disabled=false;}
function stopCamera(){if(state.cameraStream){state.cameraStream.getTracks().forEach(t=>t.stop());state.cameraStream=null;}}
function closeCamera(){stopCamera();$('#camera-modal').classList.add('hidden');$('#camera-modal').setAttribute('aria-hidden','true');$('#camera-file').value='';state.cameraBusy=false;}
$$('[data-close-camera]').forEach(b=>b.onclick=closeCamera);
$('#flip-camera').onclick=async()=>{state.cameraFacing=state.cameraFacing==='environment'?'user':'environment';try{await startCamera();}catch(e){showToast(apiErrorMessage(e),'warn');}};
$('#capture-photo').onclick=()=>captureAndScan();
$('#camera-file').onchange=async e=>{const file=e.target.files?.[0];if(file)await uploadScan(file);};
async function captureAndScan(){if(state.cameraBusy)return;const video=$('#camera-video');if(!video.videoWidth)return showToast('Camera is not ready yet.','warn');const canvas=$('#camera-canvas');canvas.width=video.videoWidth;canvas.height=video.videoHeight;canvas.getContext('2d').drawImage(video,0,0);const blob=await new Promise(res=>canvas.toBlob(res,'image/jpeg',.92));if(blob)await uploadScan(new File([blob],'camera-capture.jpg',{type:'image/jpeg'}));}
async function uploadScan(file){
  if(!state.currentExamId||state.cameraBusy)return;state.cameraBusy=true;$('#capture-photo').disabled=true;$('#camera-status').textContent='Uploading and checking…';
  const fd=new FormData();fd.append('upload',file,file.name||'sheet.jpg');
  try{const result=await api(`/api/exams/${state.currentExamId}/scan`,{method:'POST',body:fd});$('#camera-status').textContent=result.status==='ai_processed'?'Processed — ready for next paper':'Saved — review required';showToast(result.status==='ai_processed'?'Paper processed':'Paper saved for review','ok');await showScanResult(result);setTimeout(()=>{$('#camera-status').textContent='Ready for next paper';$('#capture-photo').disabled=false;state.cameraBusy=false;},350);}catch(e){$('#camera-status').textContent='Could not process this paper';showToast(apiErrorMessage(e),'error');$('#capture-photo').disabled=false;state.cameraBusy=false;}
}
async function showScanResult(r){const area=$('#checker-area');if(!area)return;let details=r;if(r.submission_id){try{details=await api(`/api/submissions/${r.submission_id}`);}catch{}}const exam=examsCache.find(x=>x.id===state.currentExamId);const results=(details.results||r.ai_results||[]);const identity=details.student?`<span class="status-chip good">Matched: ${esc(details.student.name)}</span>`:(details.detected_name?`<span class="status-chip warn">Detected: ${esc(details.detected_name)}</span>`:'<span class="status-chip warn">Identity unresolved</span>');area.innerHTML=`<div class="card"><div class="toolbar"><div><div class="eyebrow">Latest paper</div><h3 style="margin:4px 0">${esc(exam?.title||'Exam')}</h3></div>${identity}</div><div class="split"><div><div class="identity-box"><div><span class="helper">Detected name</span><strong>${esc(details.detected_name||'Not detected')}</strong></div><div><span class="helper">Detected code</span><strong>${esc(details.detected_code||'Not detected')}</strong></div></div><div class="section notice">${details.identity_status==='matched'?'Student matched automatically.':details.identity_status==='ambiguous'?'Identity is ambiguous. Choose the correct student before accepting results.':'The paper is preserved; teacher review is required.'}</div></div><div><div class="scan-queue"><div class="queue-item"><span>Submission</span><strong>#${details.id||r.submission_id||'—'}</strong></div><div class="queue-item"><span>AI results</span><strong>${results.length}</strong></div><div class="queue-item"><span>Status</span><span class="status-chip ${details.status==='completed'?'good':'warn'}">${esc(details.status||r.status)}</span></div></div></div></div><div class="section"><h4>Question review</h4>${results.length?`<div class="review-list">${results.map(x=>{const max=x.maximum_score||1;const score=x.teacher_score??x.suggested_score??0;const conf=x.confidence??0;const cls=conf>=.9?'high':conf>=.7?'mid':'low';return `<div class="review-card"><div class="result-grid"><div><strong>Question ${esc(x.question_id)}</strong><div class="helper">${esc(x.feedback||x.reason||'')}</div></div><span class="confidence ${cls}">${Math.round(conf*100)}% confidence</span></div><div class="toolbar section"><input data-review-score="${x.id}" type="number" min="0" max="${max}" step="0.1" value="${score}" style="max-width:140px"><button class="mini-btn primary" data-review-id="${x.id}">Accept / edit</button><span class="pill">Suggested ${x.suggested_score??'—'} / ${max}</span></div></div>`}).join('')}</div>`:'<div class="notice">No AI results were returned. The paper remains available for manual review.</div>'}</div></div></div>`;
  $$('[data-review-id]',area).forEach(b=>b.onclick=async()=>{const id=+b.dataset.reviewId;const input=area.querySelector(`[data-review-score="${id}"]`);try{await api(`/api/ai-results/${id}/review`,{method:'POST',body:JSON.stringify({teacher_score:+input.value,action:'edit',reason:'Teacher reviewed in AI Checker'})});showToast('Teacher review saved','ok');await showScanResult({submission_id:details.id});}catch(e){showToast(apiErrorMessage(e),'warn');}});
  closeCamera();
}

async function renderAttendance(){
  const classes=await api('/api/classes');
  $('#view').innerHTML=`<div class="page-hero"><div><div class="eyebrow">Fast daily register</div><h1>Attendance</h1><p class="muted">Choose a class and keep its attendance history. The register remembers the last date you worked on.</p></div><div class="hero-actions"><button id="att-new-day" class="primary">${icon('plus')} New day</button><button id="att-history" class="secondary">${icon('calendar')} History</button></div></div><div class="toolbar"><select id="att-class" class="stretch"><option value="">Choose class</option>${classes.map(c=>`<option value="${c.id}">${esc(c.name)} · ${esc(c.grade_level)} · ${c.student_count} students</option>`).join('')}</select><div class="attendance-date"><button class="icon-btn" id="att-prev" aria-label="Previous day">${icon('calendarPrev')}</button><input id="att-date" type="date" value="${today()}" aria-label="Attendance date"><button class="icon-btn" id="att-next" aria-label="Next day">${icon('calendarNext')}</button></div><button id="att-today" class="secondary">Today</button></div><div id="att-date-note" class="notice hidden"></div><div id="att-area">${classes.length?emptyState('Ready for attendance','Choose a class to reopen its saved register.','',''):emptyState('No classes yet','Create a class and add students first.','Open setup','settings')}</div>`;
  $('#att-class').onchange=async()=>{const cid=$('#att-class').value;if(!cid)return;const info=await api(`/api/attendance/last-date?class_id=${cid}`);const chosen=info.latest_date||info.today;$('#att-date').value=chosen;loadAttendance();};
  $('#att-date').onchange=loadAttendance; $('#att-prev').onclick=()=>shiftDate(-1);$('#att-next').onclick=()=>shiftDate(1);$('#att-today').onclick=()=>{$('#att-date').value=today();loadAttendance();};
  $('#att-new-day').onclick=()=>{if(!$('#att-class').value)return showToast('Choose a class first.','warn');$('#att-date').value=today();loadAttendance();};
  $('#att-history').onclick=async()=>{const cid=$('#att-class').value;if(!cid)return showToast('Choose a class first.','warn');const h=await api(`/api/attendance/history?class_id=${cid}`);const items=h.dates.map(d=>`<button class="secondary history-date" data-date="${d}">${d}</button>`).join('')||'<div class="notice">No saved attendance dates yet.</div>';const card=modal('Attendance history',`<div class="stack">${items}</div>`);$$('[data-date]',card).forEach(b=>b.onclick=()=>{$('#att-date').value=b.dataset.date;$('#modal-root').innerHTML='';loadAttendance();});};
  async function shiftDate(delta){const d=new Date($('#att-date').value+'T12:00:00');d.setDate(d.getDate()+delta);$('#att-date').value=d.toISOString().slice(0,10);loadAttendance();}
  async function loadAttendance(){const cid=$('#att-class').value;if(!cid)return;const date=$('#att-date').value;const area=$('#att-area');area.innerHTML='<div class="card notice">Loading saved register…</div>';try{const d=await api(`/api/attendance?class_id=${cid}&attendance_date=${date}`);const counts={present:d.rows.filter(x=>x.status==='present').length,absent:d.rows.filter(x=>x.status==='absent').length,late:d.rows.filter(x=>x.status==='late').length,excused:d.rows.filter(x=>x.status==='excused').length};const savedCount=d.rows.filter(x=>x.recorded).length;const note=$('#att-date-note');note.classList.toggle('hidden',!savedCount);if(savedCount){note.textContent=`Saved register restored · ${savedCount}/${d.rows.length} student records on ${d.date}.`;}area.innerHTML=`<div class="card"><div class="attendance-toolbar"><div><div class="eyebrow">Saved register · ${esc(d.date)}</div><h3 style="margin:4px 0">${esc($('#att-class option:checked').textContent||'Class')}</h3></div><button id="mark-all-present" class="primary">${icon('check')} Mark all present</button></div><div class="attendance-summary"><div class="stat-box"><span>Present</span><strong id="att-present">${counts.present}</strong></div><div class="stat-box"><span>Absent</span><strong id="att-absent">${counts.absent}</strong></div><div class="stat-box"><span>Late</span><strong id="att-late">${counts.late}</strong></div><div class="stat-box"><span>Excused</span><strong id="att-excused">${counts.excused}</strong></div></div><div class="attendance-list">${d.rows.length?d.rows.map((r,i)=>`<div class="attendance-row" data-student-row="${r.student_id}"><div class="row-left"><span class="roll-number">${i+1}</span><span class="student-avatar">${esc(initials(r.student))}</span><div class="attendance-name"><strong>${esc(r.student)}</strong><span>Student No. ${esc(r.code)}</span></div></div><div class="att-actions"><button class="circle-action ${r.status==='present'?'active-p':''}" data-att="${r.student_id}" data-status="present" aria-label="Mark ${esc(r.student)} present">P</button><button class="circle-action ${r.status==='absent'?'active-a':''}" data-att="${r.student_id}" data-status="absent" aria-label="Mark ${esc(r.student)} absent">A</button><button class="icon-btn" data-att-more="${r.student_id}" aria-label="More statuses">⋯</button></div></div>`).join(''):'<div class="notice">No active students in this class.</div>'}</div></div>`;
    const updateCounts=()=>{const rows=$$('[data-student-row]',area);let p=0,a=0,l=0,x=0;rows.forEach(row=>{const active=row.querySelector('.active-p,.active-a');if(active?.classList.contains('active-p'))p++;else if(active?.classList.contains('active-a'))a++;else {const more=row.querySelector('[data-att-more]');const st=more?.dataset.extraStatus||'';if(st==='late')l++;if(st==='excused')x++;}});$('#att-present').textContent=p;$('#att-absent').textContent=a;$('#att-late').textContent=l;$('#att-excused').textContent=x;};
    $$('[data-att]',area).forEach(b=>b.onclick=()=>saveAtt(+b.dataset.att,b.dataset.status,b));
    $$('[data-att-more]',area).forEach(b=>b.onclick=()=>moreAttendanceMenu(+b.dataset.attMore,date,b));
    $('#mark-all-present').onclick=async()=>{const ids=d.rows.map(r=>r.student_id);if(!ids.length)return;try{await api('/api/attendance/bulk',{method:'POST',body:JSON.stringify({date,student_ids:ids,status:'present'})});d.rows.forEach(r=>{const row=area.querySelector(`[data-student-row="${r.student_id}"]`);row?.querySelector('[data-status="present"]')?.classList.add('active-p');row?.querySelector('[data-status="absent"]')?.classList.remove('active-a');});updateCounts();showToast(`${ids.length} students marked present`,'ok');}catch(e){showToast(apiErrorMessage(e),'warn');}};
    async function saveAtt(student_id,status,button){const row=button.closest('[data-student-row]');const prev=[...row.querySelectorAll('.circle-action')].map(x=>x.className);row.querySelector('[data-status="present"]').classList.toggle('active-p',status==='present');row.querySelector('[data-status="absent"]').classList.toggle('active-a',status==='absent');updateCounts();button.disabled=true;try{await api('/api/attendance',{method:'POST',body:JSON.stringify({student_id,date,status})});showToast('Saved to attendance history','ok');}catch(e){row.querySelectorAll('.circle-action').forEach((x,i)=>x.className=prev[i]);updateCounts();showToast(apiErrorMessage(e),'warn');}finally{button.disabled=false;}}
    function moreAttendanceMenu(student_id,d,trigger){const opts=['late','excused'];const card=modal('Other attendance statuses','<div class="stack">'+opts.map(o=>`<button class="secondary" data-extra-status="${o}">${o==='late'?'Late':'Excused'}</button>`).join('')+'</div>');$$('[data-extra-status]',card).forEach(b=>b.onclick=async()=>{try{await api('/api/attendance',{method:'POST',body:JSON.stringify({student_id,date:d,status:b.dataset.extraStatus})});$('#modal-root').innerHTML='';trigger.dataset.extraStatus=b.dataset.extraStatus;const row=area.querySelector(`[data-student-row="${student_id}"]`);row.querySelector('.circle-action.active-p,.circle-action.active-a')?.classList.remove('active-p','active-a');updateCounts();showToast('Saved','ok');}catch(e){showToast(apiErrorMessage(e),'warn');}});}
  }catch(e){area.innerHTML=`<div class="notice warn">${esc(apiErrorMessage(e))}</div>`;}}
}

async function renderAnalytics(){
  const classes=await api('/api/classes');$('#view').innerHTML=`<div class="toolbar"><select id="an-class" class="stretch"><option value="">Choose class</option>${classes.map(c=>`<option value="${c.id}">${esc(c.name)} · ${esc(c.grade_level)}</option>`).join('')}</select><button id="an-run" class="primary"><span>${icon('chart')}</span>View analytics</button></div><div id="an-area">${classes.length?emptyState('Class intelligence','Select a class to inspect averages, attendance, ranking and stored mistake evidence.','',''):emptyState('No classes yet','Create a class and collect evidence first.','Open setup','settings')}</div>`;$('#an-run').onclick=async()=>{const id=$('#an-class').value;if(!id)return showToast('Choose a class first.','warn');const a=$('#an-area');a.innerHTML='<div class="card notice">Analyzing stored evidence…</div>';try{const d=await api(`/api/analytics/class/${id}`);a.innerHTML=`<div class="grid kpi-grid"><div class="card kpi-card"><div class="kpi-label">Class average</div><div class="kpi">${d.average}%</div></div><div class="card kpi-card"><div class="kpi-label">Pass rate</div><div class="kpi">${d.pass_rate}%</div></div><div class="card kpi-card"><div class="kpi-label">Attendance</div><div class="kpi">${d.attendance}%</div></div><div class="card kpi-card"><div class="kpi-label">Support needed</div><div class="kpi">${d.students_needing_support}</div></div></div><div class="section split"><div class="card"><h3>Ranking</h3>${d.rankings.length?`<div class="table-wrap"><table class="table"><thead><tr><th>Rank</th><th>Student</th><th>Average</th></tr></thead><tbody>${d.rankings.map(r=>`<tr><td>${r.rank}</td><td>${esc(r.name)}</td><td>${r.average}%</td></tr>`).join('')}</tbody></table></div>`:'<div class="notice">No scores yet.</div>'}</div><div class="card"><h3>Top mistake evidence</h3><div class="kpi" style="font-size:22px">${esc(d.top_mistake)}</div><div class="helper">Only stored evidence is used; the system does not invent causes.</div></div></div>`;}catch(e){a.innerHTML=`<div class="notice warn">${esc(apiErrorMessage(e))}</div>`;}};
}

async function renderReports(){
  const students=await api('/api/students?limit=5000');
  $('#view').innerHTML=`<div class="page-hero"><div><div class="eyebrow">Teacher-ready reporting</div><h1>Reports</h1><p class="muted">Generate attendance, score, midterm, final and transcript reports for one student or your full roster.</p></div></div><div class="card"><div class="form-grid"><label>Student<select id="report-student"><option value="">Choose student</option>${students.map(s=>`<option value="${s.id}">${esc(s.full_name)} · No. ${esc(s.student_code)}</option>`).join('')}</select></label><label>Report type<select id="report-type"><option value="overview">Student overview</option><option value="attendance">Attendance report</option><option value="score">Score report</option><option value="midterm">Middle-term report</option><option value="final">Final report</option><option value="transcript">Full transcript</option></select></label></div><div class="hero-actions section"><button id="report-generate" class="primary">${icon('file')} Generate report</button><span class="helper">Reports are generated from stored evidence; nothing is invented.</span></div></div><div id="report-output" class="section"></div>`;
  $('#report-generate').onclick=async()=>{const id=$('#report-student').value, type=$('#report-type').value;if(!id)return showToast('Choose a student first.','warn');const out=$('#report-output');out.innerHTML='<div class="card notice">Generating report…</div>';try{const d=await api(`/api/reports/student/${id}?report_type=${encodeURIComponent(type)}`);out.innerHTML=reportHtml(d);attachReportActions(id,type,d);}catch(e){out.innerHTML=`<div class="notice warn">${esc(apiErrorMessage(e))}</div>`;}};
}
function reportHtml(d){const title=d.type==='midterm'?'Middle-term report':d.type==='final'?'Final report':d.type==='attendance'?'Attendance report':d.type==='score'?'Score report':d.type==='transcript'?'Full transcript':'Student overview';const rows=(d.assessments||[]).map(a=>`<tr><td>${esc(a.title)}</td><td>${esc(a.date)}</td><td>${esc(a.assessment_type)}</td><td>${a.score??'—'} / ${a.max_score}</td><td>${a.percent??'—'}%</td><td>${a.passed?'Passed':'—'}</td></tr>`).join('');return `<div class="card report-card"><div class="report-head"><div><div class="eyebrow">${esc(title)}</div><h2>${esc(d.student)}</h2><p class="muted">Student No. ${esc(d.code)}</p></div><div class="hero-actions"><button id="print-report" class="primary">${icon('file')} Print</button><button id="download-report" class="secondary">${icon('download')} CSV</button></div></div>${d.summary?`<div class="grid profile-stats"><div class="stat-box"><span>Present</span><strong>${d.summary.present}</strong></div><div class="stat-box"><span>Absent</span><strong>${d.summary.absent}</strong></div><div class="stat-box"><span>Late</span><strong>${d.summary.late}</strong></div><div class="stat-box"><span>Attendance</span><strong>${d.summary.attendance_percent}%</strong></div></div>`:''}${d.attendance?`<div class="section"><h3>Attendance</h3><div class="table-wrap"><table class="table"><thead><tr><th>Date</th><th>Status</th></tr></thead><tbody>${d.attendance.map(x=>`<tr><td>${esc(x.date)}</td><td><span class="status-chip">${esc(x.status)}</span></td></tr>`).join('')}</tbody></table></div></div>`:''}${d.overall!==undefined?`<div class="metric-row section"><span>Overall performance</span><strong>${d.overall}%</strong></div>`:''}${d.average!==undefined?`<div class="metric-row section"><span>Report average</span><strong>${d.average}%</strong></div>`:''}${(d.assessments||[]).length?`<div class="section"><h3>Assessment results</h3><div class="table-wrap"><table class="table"><thead><tr><th>Assessment</th><th>Date</th><th>Type</th><th>Score</th><th>%</th><th>Result</th></tr></thead><tbody>${rows}</tbody></table></div></div>`:''}${(d.mistakes||[]).length?`<div class="section"><h3>Stored mistake evidence</h3>${d.mistakes.map(m=>`<div class="list-row"><div><strong>${esc(m.mistake_type)}</strong><span>${esc(m.topic)}</span></div><span class="pill">${m.occurrences}×</span></div>`).join('')}</div>`:''}</div>`}
function attachReportActions(id,type,d){$('#print-report').onclick=()=>window.print();$('#download-report').onclick=()=>{const a=document.createElement('a');a.href=`${API_BASE}/api/reports/student/${id}/csv?report_type=${encodeURIComponent(type)}`;a.target='_blank';a.rel='noopener';document.body.appendChild(a);a.click();a.remove();};}

function accountSecurityModal(){
  const card=modal('Account security',`<div class="stack"><div class="notice">Password changes invalidate your current browser session.</div><label>Current password<input id="sec-current" type="password" autocomplete="current-password"></label><label>New password<input id="sec-new" type="password" minlength="10" autocomplete="new-password"></label><button id="sec-save" class="primary">Change password</button></div>`);
  $('#sec-save').onclick=async()=>{try{await api('/api/auth/change-password',{method:'POST',body:JSON.stringify({current_password:$('#sec-current').value,new_password:$('#sec-new').value})});$('#modal-root').innerHTML='';showToast('Password changed. Please sign in again.','ok');setTimeout(()=>logout(),500);}catch(e){showToast(apiErrorMessage(e),'warn');}};
}

async function renderSettings(){
  const [school,classes,subjects,types]=await Promise.all([api('/api/school'),api('/api/classes'),api('/api/subjects'),api('/api/assessment-types')]);
  const cardClasses=classes.length?classes.map(c=>`<div class="list-row"><div class="row-left"><span class="badge-icon">${icon('users')}</span><div class="row-main"><strong>${esc(c.name)}</strong><span>Grade ${esc(c.grade_level)} · ${c.student_count} students</span></div></div><div class="action-group"><button class="mini-btn" data-edit-class="${c.id}">${icon('edit')} Edit</button><button class="icon-btn" data-archive-class="${c.id}" title="Archive class" aria-label="Archive ${esc(c.name)}">${icon('archive')}</button></div></div>`).join(''):'<div class="notice">No classes created yet.</div>';
  const cardSubjects=subjects.length?subjects.map(s=>`<div class="list-row"><div class="row-left"><span class="badge-icon">${icon('file')}</span><div class="row-main"><strong>${esc(s.name)}</strong><span>Active subject</span></div></div><div class="action-group"><button class="mini-btn" data-edit-subject="${s.id}">${icon('edit')} Edit</button><button class="icon-btn" data-archive-subject="${s.id}" title="Archive subject" aria-label="Archive ${esc(s.name)}">${icon('archive')}</button></div></div>`).join(''):'<div class="notice">No subjects created yet.</div>';
  const cardTypes=types.length?types.map(t=>`<div class="list-row"><div class="row-main"><strong>${esc(t.name)}</strong><span>${t.max_score} pts · ${t.weight}% weight · ${t.enabled?'Enabled':'Disabled'}</span></div><div class="action-group"><button class="mini-btn" data-edit-type="${t.id}">${icon('edit')} Edit</button>${t.enabled?`<button class="icon-btn" data-disable-type="${t.id}" title="Disable assessment type" aria-label="Disable ${esc(t.name)}">${icon('archive')}</button>`:'<span class="status-chip warn">Disabled</span>'}</div></div>`).join(''):'<div class="notice">No assessment types created yet.</div>';
  $('#view').innerHTML=`<div class="setup-grid"><div class="card"><div class="eyebrow">Workspace</div><h3>School settings</h3><div class="stack-tight"><label>School name<input id="set-school" value="${esc(school.name)}"></label><label>Academic year<input id="set-year" value="${esc(school.academic_year)}"></label><label>Default language<input id="set-lang" value="${esc(school.default_language)}"></label><label>Pass mark %<input id="set-pass" type="number" min="0" max="100" step="1" value="${school.pass_mark??50}"></label><button id="save-school" class="primary">Save settings</button></div></div><div class="card"><div class="toolbar"><div><div class="eyebrow">Roster structure</div><h3 style="margin:4px 0 0">Classes</h3></div><button id="new-class" class="secondary">${icon('plus')} Add</button></div>${cardClasses}</div><div class="card"><div class="toolbar"><div><div class="eyebrow">Curriculum</div><h3 style="margin:4px 0 0">Subjects</h3></div><button id="new-subject" class="secondary">${icon('plus')} Add</button></div>${cardSubjects}</div></div><div class="section card"><div class="toolbar"><div><div class="eyebrow">Grading configuration</div><h3 style="margin:4px 0 0">Assessment types</h3></div><button id="new-type" class="primary">${icon('plus')} Add type</button></div><div class="notice">Use only the assessment types your school actually uses. Weights and maximum scores are editable; disabling a type does not erase historical scores.</div><div class="section">${cardTypes}</div></div><div class="section card"><div class="toolbar"><div><div class="eyebrow">AI & data</div><h3 style="margin:4px 0 0">Service status</h3></div>${$('#api-status').textContent.startsWith('Gemini ready')?'<span class="status-chip good">Gemini connected</span>':'<span class="status-chip warn">Manual mode</span>'}</div><div class="metric-row"><span>AI model</span><strong>${esc($('#api-status').textContent)}</strong></div><div class="helper">The Gemini API key is server-side. Core roster, score and attendance workflows do not depend on Gemini.</div></div>`;
  $('#save-school').onclick=async()=>{try{await api('/api/school',{method:'PATCH',body:JSON.stringify({name:$('#set-school').value.trim(),academic_year:$('#set-year').value.trim(),default_language:$('#set-lang').value.trim(),pass_mark:+$('#set-pass').value})});$('#school-name').textContent=$('#set-school').value.trim();showToast('School settings saved','ok');}catch(e){showToast(apiErrorMessage(e),'warn');}};
  $('#new-class').onclick=()=>classModal();$('#new-subject').onclick=()=>subjectModal();$('#new-type').onclick=()=>typeModal();
  $$('[data-edit-class]').forEach(b=>b.onclick=()=>classModal(classes.find(c=>c.id===+b.dataset.editClass)));$$('[data-archive-class]').forEach(b=>b.onclick=()=>archiveThing(`/api/classes/${b.dataset.archiveClass}/archive`,'Class archived'));$$('[data-edit-subject]').forEach(b=>b.onclick=()=>subjectModal(subjects.find(s=>s.id===+b.dataset.editSubject)));$$('[data-archive-subject]').forEach(b=>b.onclick=()=>archiveThing(`/api/subjects/${b.dataset.archiveSubject}/archive`,'Subject archived'));$$('[data-edit-type]').forEach(b=>b.onclick=()=>typeModal(types.find(t=>t.id===+b.dataset.editType)));$$('[data-disable-type]').forEach(b=>b.onclick=()=>archiveThing(`/api/assessment-types/${b.dataset.disableType}/archive`,'Assessment type disabled'));
}
async function archiveThing(path,message){if(!confirm('Archive this item? Historical data is preserved.'))return;try{await api(path,{method:'POST'});showToast(message,'ok');renderSettings();}catch(e){showToast(apiErrorMessage(e),'warn');}}
function classModal(c){const body=`<div class="form-grid"><label>Class name<input id="cm-name" value="${esc(c?.name||'')}" placeholder="Grade 10A"></label><label>Grade level<input id="cm-grade" value="${esc(c?.grade_level||'')}" placeholder="10"></label></div>`;const card=modal(c?'Edit class':'Create class',body,`<button class="secondary" data-close-modal>Cancel</button><button class="primary" id="save-class">${c?'Save changes':'Create class'}</button>`);card.querySelector('#save-class').onclick=async()=>{const p={name:$('#cm-name',card).value.trim(),grade_level:$('#cm-grade',card).value.trim()};if(!p.name||!p.grade_level)return showToast('Class name and grade are required.','warn');try{await api(c?`/api/classes/${c.id}`:'/api/classes',{method:c?'PATCH':'POST',body:JSON.stringify(p)});$('#modal-root').innerHTML='';showToast(c?'Class updated':'Class created','ok');renderSettings();}catch(e){showToast(apiErrorMessage(e),'warn');}};$$('[data-close-modal]',card).forEach(b=>b.onclick=()=>$('#modal-root').innerHTML='');}
function subjectModal(s){const body=`<label>Subject name<input id="sm-name" value="${esc(s?.name||'')}" placeholder="Mathematics"></label>`;const card=modal(s?'Edit subject':'Create subject',body,`<button class="secondary" data-close-modal>Cancel</button><button class="primary" id="save-subject">${s?'Save changes':'Create subject'}</button>`);card.querySelector('#save-subject').onclick=async()=>{const p={name:$('#sm-name',card).value.trim()};if(!p.name)return showToast('Subject name is required.','warn');try{await api(s?`/api/subjects/${s.id}`:'/api/subjects',{method:s?'PATCH':'POST',body:JSON.stringify(p)});$('#modal-root').innerHTML='';showToast(s?'Subject updated':'Subject created','ok');renderSettings();}catch(e){showToast(apiErrorMessage(e),'warn');}};$$('[data-close-modal]',card).forEach(b=>b.onclick=()=>$('#modal-root').innerHTML='');}
function typeModal(t){const body=`<div class="form-grid"><label>Name<input id="tm-name" value="${esc(t?.name||'')}" placeholder="Test"></label><label>Maximum score<input id="tm-max" type="number" min="0.1" step="0.1" value="${t?.max_score??100}"></label><label>Weight %<input id="tm-weight" type="number" min="0" max="100" step="0.1" value="${t?.weight??0}"></label><label>Enabled<select id="tm-enabled"><option value="true" ${t?.enabled!==false?'selected':''}>Enabled</option><option value="false" ${t?.enabled===false?'selected':''}>Disabled</option></select></label></div>`;const card=modal(t?'Edit assessment type':'Create assessment type',body,`<button class="secondary" data-close-modal>Cancel</button><button class="primary" id="save-type">${t?'Save changes':'Create type'}</button>`);card.querySelector('#save-type').onclick=async()=>{const p={name:$('#tm-name',card).value.trim(),max_score:+$('#tm-max',card).value,weight:+$('#tm-weight',card).value,enabled:$('#tm-enabled',card).value==='true',sort_order:t?.sort_order??999};if(!p.name||p.max_score<=0)return showToast('Name and maximum score are required.','warn');try{await api(t?`/api/assessment-types/${t.id}`:'/api/assessment-types',{method:t?'PATCH':'POST',body:JSON.stringify(p)});$('#modal-root').innerHTML='';showToast(t?'Assessment type updated':'Assessment type created','ok');renderSettings();}catch(e){showToast(apiErrorMessage(e),'warn');}};$$('[data-close-modal]',card).forEach(b=>b.onclick=()=>$('#modal-root').innerHTML='');}

function quickAdd(){
  const options=[['Add student','Add to your roster','students'],['Create class','Create a class structure','settings'],['Create assessment','Open the gradebook setup','scores'],['Scan exam','Open the AI camera checker','checker']];
  const body=`<div class="stack">${options.map(([t,s,v],i)=>`<button class="secondary" data-quick-view="${v}" style="display:flex;justify-content:space-between;align-items:center"><span><strong>${t}</strong><small class="muted" style="display:block;margin-top:3px">${s}</small></span><span>${icon('arrow')}</span></button>`).join('')}</div>`;const card=modal('Quick add',body);$$('[data-quick-view]',card).forEach(b=>b.onclick=()=>{$('#modal-root').innerHTML='';setView(b.dataset.quickView);render();});
}

$$('[data-icon]').forEach(el=>el.innerHTML = icon(el.dataset.icon));
if('serviceWorker' in navigator) navigator.serviceWorker.register(window.Capacitor?'./sw.js':'/static/sw.js').catch(()=>{});
boot();
