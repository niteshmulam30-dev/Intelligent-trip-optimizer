const $ = s => document.querySelector(s);
let currentTripId = null;
let currentPlan = null;
let lastPayload = null;
let options = {};

const money = n => new Intl.NumberFormat('en-IN',{style:'currency',currency:'INR',maximumFractionDigits:0}).format(Number(n||0));
const esc = v => String(v ?? '').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
const title = s => String(s||'').replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase());

async function api(url, opts={}){
  const r = await fetch(url,{headers:{'Content-Type':'application/json',...(opts.headers||{})},...opts});
  let data={}; try{data=await r.json()}catch{}
  if(!r.ok || data.ok===false) throw new Error(data.error || `Request failed (${r.status})`);
  return data;
}
function alertMsg(msg,type='error',actions=''){
  const b=$('#alertBox'); b.className=`alert ${type}`; b.innerHTML=`<span>${esc(msg)}</span>${actions}`; b.classList.remove('hidden');
}
function clearAlert(){ $('#alertBox').classList.add('hidden'); }
function loading(on,text){ $('#loading').classList.toggle('hidden',!on); $('#planBtn').disabled=on; if(text) $('#loadingText').textContent=text; }
function fillSelect(el, values, selected){
  el.innerHTML=''; (values||[]).forEach(v=>{const value=typeof v==='object'?(v.code??v.value):v; const label=typeof v==='object'?(v.label??value):title(v); const o=new Option(label,value); if(String(value)===String(selected)) o.selected=true; el.add(o)});
}

async function init(){
  try{
    const [opt,health]=await Promise.all([api('/api/options'),api('/api/health')]); options=opt;
    fillSelect($('#interest'),opt.interests,'general'); fillSelect($('#user_preference'),opt.preferences,'relaxation');
    fillSelect($('#preferred_mode'),opt.transport_modes,'Train'); fillSelect($('#preferred_hotel'),opt.hotel_types,'standard'); fillSelect($('#lang'),opt.languages,'en');
    fillSelect($('#r_interest'),opt.interests); fillSelect($('#r_mode'),opt.transport_modes); fillSelect($('#r_hotel'),opt.hotel_types);
    $('#apiStatus').textContent=`● API online · ${health.persisted_trips} saved`; $('#apiStatus').style.color='var(--ok)';
  }catch(e){ $('#apiStatus').textContent='● API unavailable'; $('#apiStatus').style.color='var(--danger)'; alertMsg(e.message); }
  setDefaultDates(); loadHistory();
}
function setDefaultDates(){const s=new Date(); s.setDate(s.getDate()+7); const e=new Date(s); e.setDate(e.getDate()+3); const fmt=d=>d.toISOString().slice(0,10); $('#start_date').value=fmt(s); $('#end_date').value=fmt(e)}
function formPayload(force=false){
  const fd=new FormData($('#tripForm')); const p=Object.fromEntries(fd.entries());
  p.total_budget=Number(p.total_budget); p.rooms=Number(p.rooms); p.num_people=Number(p.num_people); if(force)p.force=true; return p;
}

$('#tripForm').addEventListener('submit',async e=>{e.preventDefault(); await generate(false)});
async function generate(force){
  clearAlert(); lastPayload=formPayload(force); loading(true);
  try{
    const data=await api('/api/plan',{method:'POST',body:JSON.stringify(lastPayload)});
    if(data.status==='weather_warning'){
      loading(false); alertMsg(`${data.weather_risk || 'High weather risk'} — ${data.message}`,'warning',` <button id="forceBtn" class="secondary">Plan anyway</button>`);
      $('#forceBtn').onclick=()=>generate(true); return;
    }
    currentTripId=data.trip_id; currentPlan=data.plan; renderPlan(data.plan); await loadHistory();
    alertMsg('Trip generated successfully.','success'); $('#results').scrollIntoView({behavior:'smooth'});
  }catch(e){alertMsg(e.message)}finally{loading(false)}
}

$('#sampleBtn').onclick=()=>{ $('#origin').value='Mumbai';$('#destination').value='Goa';$('#total_budget').value=40000;$('#num_people').value=2;$('#rooms').value=1;$('#interest').value='beach';$('#user_preference').value='relaxation';$('#preferred_mode').value='Train';$('#preferred_hotel').value='standard';setDefaultDates() };

function renderPlan(p){
  $('#results').classList.remove('hidden'); $('#tripTitle').textContent=`${p.origin} → ${p.destination}`; $('#tripScore').textContent=p.trip_score ?? 0;
  const spent=p.budget_breakdown?.total_used||0;
  $('#summaryCards').innerHTML=[['Duration',`${p.days} days`],['Travelers',`${p.num_people} people`],['Budget',money(p.total_budget)],['Estimated spend',money(spent)]].map(([a,b])=>`<div class="summary-card"><small>${a}</small><strong>${b}</strong></div>`).join('');
  renderHotel(p); renderBudget(p); renderTransport(p); renderItinerary(p); renderWeatherPacking(p);
  $('#r_budget').value=p.total_budget||''; $('#r_interest').value=p.interest||'general'; $('#r_mode').value=p.preferred_mode||'Train'; $('#r_hotel').value=p.preferred_hotel||'standard';
}
function renderHotel(p){const h=p.best_hotel; if(!h){$('#hotel').innerHTML='<p class="muted">No hotel recommendation available.</p>';return} const links=h.booking_links||h.links||{}; $('#hotel').innerHTML=`<h4>${esc(h.name)}</h4><p class="muted">${esc(h.area||h.location||'')}</p>${kv('Price / night',money(h.price))}${kv('Rating',h.rating??'—')}${h._avg_dist_km!=null?kv('Avg. attraction distance',`${h._avg_dist_km} km`):''}<div>${Object.entries(links).map(([k,u])=>`<a class="linkbtn" target="_blank" rel="noopener" href="${esc(u)}">${esc(k)}</a>`).join('')}</div>`}
function renderBudget(p){const b=p.budget_breakdown||{}; if(!Object.keys(b).length){$('#budget').innerHTML='<p class="muted">No budget data.</p>';return} const pct=Math.max(0,Math.min(100,Number(b.percent_used||0))); const skip=new Set(['adjustments','status','percent_used','total_budget','total_used','remaining']); const rows=Object.entries(b).filter(([k,v])=>!skip.has(k)&&typeof v==='number').map(([k,v])=>kv(title(k),money(v))).join(''); const tips=(p.budget_savings_tips||[]).map(x=>`<span class="pill">${esc(typeof x==='string'?x:(x.message||JSON.stringify(x)))}</span>`).join(''); $('#budget').innerHTML=`${kv('Total budget',money(b.total_budget||p.total_budget))}${kv('Estimated used',money(b.total_used))}${kv('Remaining',money(b.remaining))}<div class="budget-bar"><div class="budget-fill" style="width:${pct}%"></div></div><p class="meta">${pct}% used · ${esc(b.status||'')}</p>${rows}<div>${tips}</div>`}
function renderTransport(p){let html=''; const i=p.intercity; if(i){html+=`<h4>${esc(i.mode||'Intercity')} · ${esc(i.from)} → ${esc(i.to)}</h4>${kv('Distance',`${i.distance??'—'} km`)}${kv('Round trip',money(i.round_trip_cost))}${kv('Travel time',`${i.round_trip_time??i.total_time??'—'} hr`)}<div>${Object.entries(i.booking_links||{}).map(([k,u])=>`<a class="linkbtn" target="_blank" rel="noopener" href="${esc(u)}">${esc(k)}</a>`).join('')}</div>`} const l=p.local_transport; if(l){html+=`<h4 style="margin-top:20px">Local transport</h4>${kv('Estimated local cost',money(l.total_local_transport_cost))}<p class="meta">${(l.routes||[]).length} route legs generated from the final itinerary.</p>`} $('#transport').innerHTML=html||'<p class="muted">No transport data.</p>'}
function renderItinerary(p){const arr=p.itinerary||[]; if(!arr.length){$('#itinerary').innerHTML='<p class="muted">No itinerary available.</p>';return} const groups={}; arr.forEach(x=>{const d=x.day||1;(groups[d]??=[]).push(x)}); $('#itinerary').innerHTML=Object.entries(groups).map(([d,items])=>`<div class="timeline-day"><h4>Day ${d}</h4>${items.map(it=>{const typ=it.type||'visit'; const name=it.name||it.place||it.to||title(typ); const tm=it.time||it.start_time||it.arrival_time||''; const desc=it.description||it.selected_because||it.reason||''; return `<div class="timeline-item"><strong>${esc(name)}</strong><div class="meta">${esc(tm)}${tm&&typ?' · ':''}${esc(title(typ))}</div>${desc?`<div class="meta">${esc(desc)}</div>`:''}</div>`}).join('')}</div>`).join('')}
function renderWeatherPacking(p){const w=p.weather_data||{}; let html=''; if(Object.keys(w).length) html+=`${kv('Condition',w.condition||'—')}${kv('Temperature',w.temp!=null?`${w.temp}°C`:'—')}${kv('Feels like',w.feels_like!=null?`${w.feels_like}°C`:'—')}${kv('Humidity',w.humidity!=null?`${w.humidity}%`:'—')}${kv('AQI',p.aqi??'—')}${kv('Risk',p.weather_risk||'—')}`; const pack=p.packing_list||[]; if(pack.length) html+=`<h4 style="margin-top:18px">Packing list</h4><div>${pack.map(x=>`<span class="pill">${esc(x)}</span>`).join('')}</div>`; $('#weatherPacking').innerHTML=html||'<p class="muted">No weather data.</p>'}
function kv(k,v){return `<div class="kv"><span>${esc(k)}</span><strong>${esc(v)}</strong></div>`}

$('#refineForm').addEventListener('submit',async e=>{e.preventDefault(); if(!currentTripId)return; clearAlert(); loading(true,'Updating only the affected agents…'); const p={total_budget:Number($('#r_budget').value),interest:$('#r_interest').value,preferred_mode:$('#r_mode').value,preferred_hotel:$('#r_hotel').value}; try{const d=await api(`/api/plan/${currentTripId}/refine`,{method:'POST',body:JSON.stringify(p)});currentPlan=d.plan;renderPlan(d.plan);alertMsg(`Plan updated: ${d.changed.join(', ')}`,'success');await loadHistory()}catch(e){alertMsg(e.message)}finally{loading(false)}});

async function loadHistory(){try{const d=await api('/api/history?limit=20'); const el=$('#historyList'); if(!d.trips.length){el.innerHTML='<p class="muted">No trips yet. Generated plans will be saved here.</p>';return} el.innerHTML=d.trips.map(t=>`<div class="history-item"><div><strong>${esc(t.origin)} → ${esc(t.destination)}</strong><p>${t.days} days · ${money(t.total_budget)} · score ${t.trip_score}/100</p></div><span class="meta">${new Date(t.updated_at||t.created_at).toLocaleString()}</span><div class="history-actions"><button class="ghost" data-open="${t.trip_id}">Open</button><button class="ghost" data-del="${t.trip_id}">Delete</button></div></div>`).join(''); el.querySelectorAll('[data-open]').forEach(b=>b.onclick=()=>openTrip(b.dataset.open)); el.querySelectorAll('[data-del]').forEach(b=>b.onclick=()=>deleteTrip(b.dataset.del))}catch(e){$('#historyList').innerHTML=`<p class="muted">${esc(e.message)}</p>`}}
async function openTrip(id){clearAlert();try{const d=await api(`/api/plan/${id}`);currentTripId=id;currentPlan=d.plan;renderPlan(d.plan);$('#results').scrollIntoView({behavior:'smooth'})}catch(e){alertMsg(e.message)}}
async function deleteTrip(id){if(!confirm('Delete this saved trip?'))return;try{await api(`/api/history/${id}`,{method:'DELETE'});if(currentTripId===id){currentTripId=null}await loadHistory()}catch(e){alertMsg(e.message)}}
$('#refreshHistory').onclick=loadHistory;
init();
