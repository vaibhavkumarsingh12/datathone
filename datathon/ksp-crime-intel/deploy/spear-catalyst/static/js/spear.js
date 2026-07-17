/* SPEAR frontend — vanilla JS. No build step, no framework, no WebSocket.
   Faithful port of the original Streamlit SPEAR dashboard. */
const T = {bg:'#090F17', surface:'#111A26', surface2:'#16212F', border:'#26364A',
  borderSub:'#1B2735', text:'#E8EDF2', text2:'#A4B2C1', muted:'#6C7D90',
  accent:'#4C87D8', critical:'#EC7468', warning:'#E3B94A', success:'#57C58C'};
const SERIES = ['#5A9BE6','#4FC48B','#E3B94A','#EC7468','#A98BD6','#45C0B2','#D08A5E','#7E97B0'];
const HEAT = [[0,'#16212F'],[.25,'#3A4C63'],[.5,'#8A5A46'],[.75,'#C05C3A'],[1,'#EC7468']];
const DOW = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
const CFG = {displayModeBar:false, responsive:true};

/* ---- layout builder — returns a FRESH object every call.
   (The old shared LAYOUT constant was mutated by Plotly across charts, which
    broke the horizontal Top-10 bars. Fresh nested axes fix that permanently.) */
function fig(o) {
  o = o || {};
  const lay = {
    paper_bgcolor:'rgba(0,0,0,0)', plot_bgcolor:'rgba(0,0,0,0)',
    font:{family:'IBM Plex Sans, sans-serif', color:T.text2, size:12},
    colorway:SERIES.slice(),
    margin:o.margin || {l:50, r:14, t:(o.title?44:16), b:44},
    hoverlabel:{bgcolor:T.surface2, bordercolor:T.border,
                font:{family:'IBM Plex Sans', color:T.text, size:12}},
    legend:{font:{color:T.text2, size:11}, bgcolor:'rgba(0,0,0,0)'},
    xaxis:Object.assign({showgrid:false, zeroline:false, linecolor:T.border,
      tickfont:{color:T.muted, size:11}, titlefont:{color:T.muted, size:11}}, o.xaxis||{}),
    yaxis:Object.assign({showgrid:true, gridcolor:T.borderSub, zeroline:false,
      linecolor:'rgba(0,0,0,0)', tickfont:{color:T.muted, size:11},
      titlefont:{color:T.muted, size:11}}, o.yaxis||{})
  };
  if (o.title)  lay.title = {text:o.title, font:{size:15, color:T.text}};
  if (o.height) lay.height = o.height;
  if (o.mapbox) lay.mapbox = o.mapbox;
  if (o.shapes) lay.shapes = o.shapes;
  if (o.showlegend !== undefined) lay.showlegend = o.showlegend;
  return lay;
}

let BOOT = null, GEO = null;
const $ = s => document.querySelector(s);
const qs = extra => new URLSearchParams(Object.assign({
  head:$('#f-head').value, type:$('#f-type').value,
  from:$('#f-from').value, to:$('#f-to').value}, extra||{})).toString();
const get = (path, extra) => fetch(path + '?' + qs(extra)).then(r => r.json());
const raw = (path, p) => fetch(path + '?' + new URLSearchParams(p||{})).then(r => r.json());

const fmt = n => (n ?? 0).toLocaleString();
const round = (v, n) => (v == null || v === '') ? '' : Number(v).toFixed(n);
const pct = v => Math.round((v || 0) * 100) + '%';

function stat(label, value, sub, accent) {
  return `<div class="stat" style="--sa:${accent}"><div class="stat-l">${label}</div>
    <div class="stat-v">${value}</div><div class="stat-s">${sub}</div></div>`;
}

/* generic table; columns = [{k,label,f?}] or auto from keys */
function tbl(rows, columns) {
  if (!rows || !rows.length) return '<p class="note">Nothing to show.</p>';
  const cols = columns || Object.keys(rows[0]).map(k => ({k, label:k}));
  return `<table><thead><tr>${cols.map(c=>`<th>${c.label}</th>`).join('')}</tr></thead>`
    + `<tbody>${rows.map(r=>`<tr>${cols.map(c=>
        `<td>${c.f ? c.f(r[c.k], r) : (r[c.k] ?? '')}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
}

/* ---------------------------------------------------------------- boot */
async function boot() {
  BOOT = await fetch('/api/bootstrap').then(r => r.json());
  const o = BOOT.options, m = BOOT.meta;

  $('#f-head').innerHTML = ['All', ...o.heads].map(h=>`<option>${h}</option>`).join('');
  $('#f-from').value = $('#f-from').min = o.date_min;
  $('#f-to').value   = $('#f-to').max   = o.date_max;
  $('#f-from').max = $('#f-to').min = o.date_max;
  syncTypes();

  $('#cap-meta').textContent = `${fmt(m.n_cases)} cases · ${m.date_min} → ${m.date_max}`;
  $('#build-info').innerHTML = `build ${m.built_at}<br>alert z floor ${m.alert_z_floor}`;

  const scopes = [...new Set(BOOT.hotspot_params.map(p=>p.scope))];
  $('#hot-scope').innerHTML = scopes.map(s=>`<option>${s}</option>`).join('');
  refreshHotParams();

  $('#net-min').innerHTML = [2,3,4,5,6,8].map(n=>
    `<option${n===4?' selected':''}>${n}</option>`).join('');

  try { GEO = await fetch('/static/karnataka.geojson').then(r=>r.json()); } catch(e) {}

  document.querySelectorAll('#tabs button').forEach(b =>
    b.onclick = () => showTab(b.dataset.tab));
  ['#f-head','#f-type','#f-from','#f-to'].forEach(s =>
    $(s).onchange = () => { if (s==='#f-head') syncTypes(); render(); });
  $('#f-reset').onclick = () => {
    $('#f-head').value='All'; syncTypes();
    $('#f-from').value=o.date_min; $('#f-to').value=o.date_max; render();
  };
  ['#hot-scope','#hot-eps','#hot-mins'].forEach(s =>
    $(s).onchange = () => { if (s==='#hot-scope') refreshHotParams(); drawHot(); });
  $('#al-z').oninput = e => { $('#al-zv').textContent = e.target.value; drawAlerts(); };
  ['#net-min','#net-comm'].forEach(s => $(s).onchange = drawNetwork);
  $('#map-district').onchange = drawStations;
  $('#net-alias').onchange = drawAlias;

  render();
}

function syncTypes() {
  const h = $('#f-head').value;
  const t = BOOT.options.types.filter(r => h==='All' || r.CrimeHead===h).map(r => r.CrimeType);
  $('#f-type').innerHTML = ['All', ...new Set(t)].map(x=>`<option>${x}</option>`).join('');
}

let TAB = 'overview';
function showTab(name) {
  TAB = name;
  document.querySelectorAll('#tabs button').forEach(b =>
    b.classList.toggle('on', b.dataset.tab===name));
  document.querySelectorAll('.tab').forEach(s =>
    s.classList.toggle('on', s.id==='tab-'+name));
  render();
}

function render() {
  ({overview:drawOverview, map:drawMap, hot:drawHot, time:drawTime,
    alerts:drawAlerts, network:drawNetwork, risk:drawRisk,
    anom:drawAnom, valid:drawValid}[TAB] || (()=>{}))();
}

/* ---------------------------------------------------------------- overview */
async function drawOverview() {
  const d = await get('/api/overview'), s = d.summary;
  $('#ov-stats').innerHTML =
    stat('Cases (filtered)', fmt(s.n_cases), 'in current view', T.accent) +
    stat('Districts active', s.n_districts, 'of 31 districts', T.success) +
    stat('Stations reporting', fmt(s.n_stations), 'police stations', T.warning) +
    stat('Top crime type', s.top_crime, 'most frequent', T.critical);

  Plotly.newPlot('ov-monthly',
    [{x:d.monthly.map(r=>r.ym), y:d.monthly.map(r=>r.n), type:'scatter',
      mode:'lines+markers', line:{width:2.2, color:SERIES[0]}, marker:{size:6, color:SERIES[0]}}],
    fig({title:'Cases per month', height:340}), CFG);

  const t = d.top_types.slice().reverse();          // ascending so biggest is on top
  Plotly.newPlot('ov-types',
    [{x:t.map(r=>r.n), y:t.map(r=>r.CrimeType), type:'bar', orientation:'h',
      marker:{color:SERIES[0]}, hovertemplate:'%{y}: %{x} cases<extra></extra>'}],
    fig({title:'Top 10 crime types', height:380,
         margin:{l:180, r:14, t:44, b:44},
         xaxis:{title:'Cases'},
         yaxis:{type:'category', automargin:true, showgrid:false}}), CFG);
}

/* ---------------------------------------------------------------- map */
async function drawMap() {
  const d = await get('/api/districts');
  if (GEO && GEO.features) {
    const key = GEO.featureidkey || 'DISTRICT';
    Plotly.newPlot('map-choro',
      [{type:'choroplethmapbox', geojson:GEO, featureidkey:'properties.'+key,
        locations:d.map(r=>r.DistrictName), z:d.map(r=>r.per_100k),
        colorscale:HEAT, marker:{opacity:.78, line:{width:.4, color:T.border}},
        colorbar:{tickfont:{color:T.muted, size:11}, outlinewidth:0, thickness:12},
        text:d.map(r=>`${r.DistrictName}<br>${fmt(r.n_cases)} cases`),
        hovertemplate:'%{text}<br>%{z} per 100k<extra></extra>'}],
      fig({title:'Crime rate per 100k population', height:650,
         mapbox:{style:'carto-darkmatter', center:{lat:14.8, lon:75.7}, zoom:5.6},
         margin:{l:0, r:0, t:44, b:0}}), CFG);
  } else {
    $('#map-choro').innerHTML = '<p class="note">No boundary file found — district table only.</p>';
  }
  $('#map-district').innerHTML = d.map(r=>`<option>${r.DistrictName}</option>`).join('');
  $('#map-table').innerHTML = tbl(d, [
    {k:'DistrictName', label:'District'},
    {k:'n_cases', label:'Cases', f:v=>fmt(v)},
    {k:'Population', label:'Population', f:v=>fmt(v)},
    {k:'per_100k', label:'Per 100k'}]);
  drawStations();
}

async function drawStations() {
  const dn = $('#map-district').value;
  if (!dn) return;
  const s = await get('/api/stations', {district: dn});
  Plotly.newPlot('map-stations',
    [{x:s.map(r=>r.Station), y:s.map(r=>r.n), type:'bar', marker:{color:SERIES[0]}}],
    fig({title:`Cases by police station — ${dn}`, height:360}), CFG);
}

/* ---------------------------------------------------------------- hotspots */
function refreshHotParams() {
  const sc = $('#hot-scope').value;
  const ps = BOOT.hotspot_params.filter(p => p.scope===sc);
  const eps  = [...new Set(ps.map(p=>p.eps_km))].sort((a,b)=>a-b);
  const mins = [...new Set(ps.map(p=>p.min_samples))].sort((a,b)=>a-b);
  $('#hot-eps').innerHTML  = eps.map(e=>`<option${e==2?' selected':''}>${e}</option>`).join('');
  $('#hot-mins').innerHTML = mins.map(m=>`<option${m==25?' selected':''}>${m}</option>`).join('');
}

async function drawHot() {
  const d = await get('/api/hotspots',
    {scope:$('#hot-scope').value, eps:$('#hot-eps').value, mins:$('#hot-mins').value});
  if (!d.param_id || !d.points.length) {
    $('#hot-msg').innerHTML = '<div class="banner err">No hotspots at these settings — '
      + 'widen the radius or lower min cases.</div>';
    Plotly.purge('hot-map'); $('#hot-table').innerHTML = ''; return;
  }
  const n = new Set(d.points.map(p=>p.cluster)).size;
  $('#hot-msg').innerHTML = `<div class="banner ok">${n} hotspot(s) detected</div>`;
  const byC = {};
  d.points.forEach(p => (byC[p.cluster] = byC[p.cluster] || []).push(p));
  const traces = Object.entries(byC).map(([c, pts], i) => ({
    type:'scattermapbox', mode:'markers', name:'Hotspot '+c,
    lat:pts.map(p=>p.latitude), lon:pts.map(p=>p.longitude),
    marker:{size:6, color:SERIES[i % SERIES.length]},
    text:pts.map(p=>`${p.DistrictName}<br>${p.CrimeType}`),
    hovertemplate:'%{text}<extra>Hotspot '+c+'</extra>'}));
  Plotly.newPlot('hot-map', traces,
    fig({title:'Detected crime hotspots (each colour = one cluster)', height:600,
       mapbox:{style:'carto-darkmatter', center:{lat:14.8, lon:75.7}, zoom:5.6},
       margin:{l:0, r:0, t:44, b:0}}), CFG);
  $('#hot-table').innerHTML = tbl(d.summary, [
    {k:'cluster', label:'Hotspot #'},
    {k:'n_cases', label:'Cases', f:v=>fmt(v)},
    {k:'district', label:'District'},
    {k:'top_crime', label:'Dominant crime'}]);
}

/* ---------------------------------------------------------------- time */
async function drawTime() {
  const d = await get('/api/heatmap');
  const z = Array.from({length:7}, () => new Array(24).fill(0));
  d.forEach(r => { z[r.dow][r.hour] = r.n; });
  Plotly.newPlot('time-heat',
    [{type:'heatmap', z, x:Array.from({length:24},(_,i)=>i), y:DOW, colorscale:HEAT,
      hovertemplate:'%{y} %{x}:00 · %{z} cases<extra></extra>'}],
    fig({title:'When does crime happen? (day × hour of incident)', height:450,
       xaxis:{title:'Hour of day'}, yaxis:{showgrid:false}}), CFG);
}

/* ---------------------------------------------------------------- alerts */
async function drawAlerts() {
  const z = $('#al-z').value;
  const d = await get('/api/alerts', {z});
  if (!d.length) {
    $('#al-msg').innerHTML = '<div class="banner ok">No spikes above threshold in the current view.</div>';
    $('#al-table').innerHTML = ''; Plotly.purge('al-hist'); return;
  }
  $('#al-msg').innerHTML = `<div class="banner err">${d.length} red-zone spike(s) detected</div>`;
  $('#al-table').innerHTML = tbl(d, [
    {k:'DistrictName', label:'District'},
    {k:'CrimeType', label:'Crime'},
    {k:'ym', label:'Month'},
    {k:'cases', label:'Cases'},
    {k:'baseline', label:'Expected', f:v=>round(v,1)},
    {k:'z', label:'Z-score', f:v=>round(v,2)}]);
  const top = d[0];
  const hist = await raw('/api/alert-history', {district:top.DistrictName, type:top.CrimeType});
  Plotly.newPlot('al-hist',
    [{x:hist.map(r=>r.ym), y:hist.map(r=>r.n), type:'bar', marker:{color:SERIES[0]}}],
    fig({title:`Worst spike: ${top.CrimeType} in ${top.DistrictName}`, height:380,
       shapes:[{type:'line', x0:top.ym, x1:top.ym, yref:'paper', y0:0, y1:1,
                line:{color:T.critical, dash:'dash', width:2}}]}), CFG);
}

/* ---------------------------------------------------------------- network */
let NET_DATA = null;
async function drawNetwork() {
  const d = await raw('/api/network',
    {min_size:$('#net-min').value, community:$('#net-comm').value || 'All'});
  NET_DATA = d;

  $('#net-stats').innerHTML =
    stat('Resolved entities', fmt(d.graph.nodes.length), 'in current view', T.accent) +
    stat('Co-offense edges', fmt(d.graph.edges.length), 'shared-case links', T.success) +
    stat('Suspected rings', d.communities.length, 'communities ≥4 entities', T.warning) +
    stat('Top connector', d.kingpins[0]?.CanonicalName ?? '—', 'highest betweenness', T.critical);

  if ($('#net-comm').options.length <= 0) {
    $('#net-comm').innerHTML = '<option>All</option>' +
      d.communities.map(c=>`<option>${c.CommunityID}</option>`).join('');
  }
  if (!$('#net-alias').options.length) {
    $('#net-alias').innerHTML = d.aliases.map(a =>
      `<option value="${a.EntityID}">Entity ${a.EntityID} — ${a.CanonicalName} `
      + `(${a.NumAliases} aliases, ${a.NumCases} cases)</option>`).join('');
  }
  drawAlias();

  const deg = Object.fromEntries(d.graph.nodes.map(n=>[n.EntityID, n.Degree]));
  const nodes = new vis.DataSet(d.graph.nodes.map(n => ({
    id:n.EntityID, label:n.CanonicalName,
    color:SERIES[n.CommunityID % SERIES.length],
    value:12 + 60*(deg[n.EntityID]||0),
    title:`${n.CanonicalName}\nEntity ${n.EntityID} · Community ${n.CommunityID}\n`
        + `${n.NumCases} cases · ${n.NumAliases} aliases\nDistricts: ${n.Districts}`})));
  const edges = new vis.DataSet(d.graph.edges.map(e => ({
    from:e.EntityA, to:e.EntityB, value:e.Weight, title:`${e.Weight} shared case(s)`})));
  new vis.Network($('#net-graph'), {nodes, edges}, {
    nodes:{shape:'dot', font:{color:T.text, size:12, face:'IBM Plex Sans'}},
    edges:{color:{color:'#3A4C63', highlight:T.accent}, smooth:false},
    physics:{barnesHut:{gravitationalConstant:-3000, springLength:120},
             stabilization:{iterations:220}},
    interaction:{hover:true, tooltipDelay:120}});

  $('#net-kings').innerHTML = tbl(d.kingpins, [
    {k:'CanonicalName', label:'Name'},
    {k:'CommunityID', label:'Ring'},
    {k:'NumCases', label:'Cases'},
    {k:'NumAliases', label:'Aliases'},
    {k:'Districts', label:'Districts'},
    {k:'Degree', label:'Degree'},
    {k:'Betweenness', label:'Betweenness', f:v=>round(v,3)}]);
  $('#net-comms').innerHTML = tbl(d.communities);
}

function drawAlias() {
  if (!NET_DATA || !NET_DATA.aliases) return;
  const id = $('#net-alias').value;
  const a = NET_DATA.aliases.find(x => x.EntityID == id);
  if (a) $('#net-alias-list').textContent =
    a.AliasList.split(/\s*[|,]\s*/).filter(Boolean).join('\n');
}

/* ---------------------------------------------------------------- risk */
async function drawRisk() {
  const d = await raw('/api/risk');
  const k = d.kpis;
  $('#risk-stats').innerHTML =
    stat('Backtest hit-rate', pct(k.hit_rate), `top-20 cells · ${k.n_months} held-out months`, T.accent) +
    stat('vs random patrols', Math.round(k.lift) + '×', 'lift over chance', T.success) +
    stat('High-risk cells', fmt(k.high_cells), 'top decile each month', T.critical) +
    stat('Top signal', k.top_feature, 'strongest predictor', T.warning);

  const sel = $('#risk-month');
  if (!sel.options.length) {
    sel.innerHTML = d.months.map(m=>`<option>${m}</option>`).join('');
    sel.value = d.months[d.months.length-1];
    sel.onchange = drawRiskSurface;
  }
  drawRiskSurface();

  const bt = d.backtest;
  Plotly.newPlot('risk-backtest', [
    {x:bt.map(r=>r.ym), y:bt.map(r=>r.hit_rate), name:'model hit-rate',
     mode:'lines+markers', line:{width:2.4, color:SERIES[0]}},
    {x:bt.map(r=>r.ym), y:bt.map(r=>r.baseline_persistence), name:'persistence',
     mode:'lines+markers', line:{color:SERIES[1]}},
    {x:bt.map(r=>r.ym), y:bt.map(r=>r.random_expectation), name:'random',
     mode:'lines+markers', line:{color:SERIES[3]}}],
    fig({title:'Backtest: model vs persistence vs random', height:340,
         yaxis:{tickformat:'.0%'}}), CFG);

  const c = d.corr;
  Plotly.newPlot('risk-corr',
    [{type:'heatmap', z:c.z, x:c.labels, y:c.labels, colorscale:HEAT,
      text:c.z, texttemplate:'%{text}', textfont:{color:T.text, size:12},
      hovertemplate:'%{y} · %{x}: %{z}<extra></extra>'}],
    fig({title:'Correlation matrix', height:340, yaxis:{showgrid:false}}), CFG);

  $('#risk-reg').innerHTML = '<h3 style="margin-top:2px">Socio-economic regression (OLS)</h3>'
    + tbl(d.regression, [
        {k:'term', label:'Term'},
        {k:'coef', label:'Coefficient', f:v=>round(v,3)},
        {k:'p_value', label:'p-value', f:v=>round(v,4)}]);
}

async function drawRiskSurface() {
  const m = $('#risk-month').value;
  const s = await raw('/api/risk-surface', {month:m});
  Plotly.newPlot('risk-surface',
    [{type:'heatmap', z:s.z, x:s.types, y:s.districts, colorscale:HEAT,
      hovertemplate:'District %{y} · Type %{x} · risk %{z:.0%}<extra></extra>'}],
    fig({title:`Risk surface — ${m} (district × crime type)`, height:560,
       xaxis:{title:'Crime type ID', type:'category'},
       yaxis:{title:'District ID', type:'category', showgrid:false}}), CFG);
}

/* ---------------------------------------------------------------- anomalies */
async function drawAnom() {
  const d = await raw('/api/anomalies');
  const k = d.kpis;
  $('#anom-stats').innerHTML =
    stat('Cases scored', fmt(k.scored), 'IsolationForest', T.accent) +
    stat('Flagged for review', fmt(k.flagged), '1% triage budget', T.critical) +
    stat('Worst volume spike', 'z = ' + round(k.worst_z, 1), 'district×type×month', T.warning);

  $('#anom-cases').innerHTML = tbl(d.cases, [
    {k:'CaseMasterID', label:'Case ID'},
    {k:'DistrictID', label:'District'},
    {k:'CrimeMinorHeadID', label:'Crime code'},
    {k:'ym', label:'Month'},
    {k:'anomaly_score', label:'Score'},
    {k:'reason', label:'Reason'}]);

  const byD = {};
  d.cells.forEach(r => (byD[r.DistrictID] = byD[r.DistrictID] || []).push(r));
  const traces = Object.entries(byD).map(([dist, pts], i) => ({
    x:pts.map(p=>p.ym), y:pts.map(p=>p.z), mode:'markers', type:'scatter', name:'District '+dist,
    marker:{size:7, color:SERIES[i % SERIES.length]},
    text:pts.map(p=>`District ${p.DistrictID} · type ${p.CrimeMinorHeadID} · ${p.cases} cases`),
    hovertemplate:'%{text}<br>z = %{y}<extra></extra>'}));
  Plotly.newPlot('anom-scatter', traces,
    fig({title:'Highest-z cells (dashed line = alert threshold)', height:400, showlegend:false,
       xaxis:{title:'Month'}, yaxis:{title:'z-score'},
       shapes:[{type:'line', xref:'paper', x0:0, x1:1, y0:2.5, y1:2.5,
                line:{color:T.critical, dash:'dash', width:1.5}}]}), CFG);
}

/* ---------------------------------------------------------------- validation */
async function drawValid() {
  const m = await fetch('/api/validation').then(r=>r.json());
  let html = '';
  for (const [k, v] of Object.entries(m)) {
    html += `<div class="card"><h3 style="margin-top:2px">${k.replace(/_/g,' ').toUpperCase()}</h3>`
          + `<pre>${JSON.stringify(v, null, 2)}</pre></div>`;
  }
  $('#valid-body').innerHTML = html || '<p class="note">No metrics files were folded in at build time.</p>';
}

boot();
