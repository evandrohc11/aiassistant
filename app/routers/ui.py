"""
app/routers/ui.py — Local browser UI: home dashboard + transactions CRUD.
No external JS/CSS dependencies — vanilla HTML/CSS/JS only.
"""
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(prefix="/ui", tags=["ui"])

# ── shared pieces ────────────────────────────────────────────────────────────

_CSS = """
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:system-ui,sans-serif;font-size:13px;background:#f0f2f5;color:#1a1a1a;display:flex;flex-direction:column;min-height:100vh}
nav{background:#1a1a2e;color:#fff;display:flex;align-items:center;height:48px}
nav .brand{padding:0 20px;font-weight:700;font-size:15px;color:#fff;text-decoration:none;border-right:1px solid #33335a;height:100%;display:flex;align-items:center}
nav a{color:#ccc;text-decoration:none;padding:0 18px;height:100%;display:flex;align-items:center;font-size:13px}
nav a:hover,nav a.active{background:#2d2d5e;color:#fff}
.page{flex:1;padding:20px 24px}
h2{font-size:18px;font-weight:700;margin-bottom:16px}
h3{font-size:14px;font-weight:600;margin-bottom:10px}
.card{background:#fff;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,.08);padding:18px 20px}
.grid{display:grid;gap:16px}
.g2{grid-template-columns:repeat(2,1fr)}
.g4{grid-template-columns:repeat(4,1fr)}
@media(max-width:700px){.g4{grid-template-columns:repeat(2,1fr)}.g2{grid-template-columns:1fr}}
.stat{text-align:center}.stat .val{font-size:26px;font-weight:700}.stat .lbl{font-size:11px;color:#777;margin-top:2px}
.income{color:#1a7f37}.expense{color:#cf222e}
label{display:flex;flex-direction:column;gap:3px;font-size:11px;font-weight:600;color:#555}
input,select,textarea{padding:6px 10px;border:1px solid #ccc;border-radius:5px;font-size:13px;width:100%;background:#fff}
input:focus,select:focus,textarea:focus{outline:2px solid #4a6fd8;border-color:transparent}
.row{display:flex;gap:10px;flex-wrap:wrap}.row label{flex:1;min-width:120px}
.btn{padding:7px 18px;border:none;border-radius:5px;cursor:pointer;font-size:13px;font-weight:600;display:inline-flex;align-items:center;gap:5px}
.btn-primary{background:#1a1a2e;color:#fff}.btn-primary:hover{opacity:.85}
.btn-danger{background:#cf222e;color:#fff}.btn-danger:hover{opacity:.85}
.btn-ghost{background:transparent;color:#555;border:1px solid #ccc}.btn-ghost:hover{background:#f5f5f5}
.btn-sm{padding:3px 10px;font-size:12px}
table{width:100%;border-collapse:collapse}
th{background:#f0f0f0;padding:7px 10px;text-align:left;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.4px;cursor:pointer;user-select:none;border-bottom:2px solid #ddd;white-space:nowrap}
th:hover{background:#e8e8e8}
th.asc::after{content:" ▲";font-size:9px}th.desc::after{content:" ▼";font-size:9px}
td{padding:6px 10px;border-bottom:1px solid #f0f0f0;vertical-align:middle}
tr:last-child td{border-bottom:none}tr:hover td{background:#fafbff}
.tag{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;background:#eef;color:#447;font-weight:600}
.tag.income{background:#e6f9ee;color:#1a7f37}.tag.expense{background:#fde8e8;color:#cf222e}
.filters{background:#fff;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,.08);padding:12px 16px;margin-bottom:14px;display:flex;flex-wrap:wrap;gap:10px;align-items:flex-end}
.filters label{min-width:90px}
.stats-bar{font-size:12px;color:#555;padding:6px 0 10px;display:flex;gap:20px;flex-wrap:wrap}
.stats-bar b{color:#222}
.empty{padding:32px;text-align:center;color:#aaa;font-size:14px}
.modal-bg{display:none;position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:100;align-items:center;justify-content:center}
.modal-bg.open{display:flex}
.modal{background:#fff;border-radius:10px;padding:24px;width:min(540px,95vw);max-height:90vh;overflow-y:auto;box-shadow:0 8px 32px rgba(0,0,0,.2)}
.modal h3{margin-bottom:16px}
.modal-footer{margin-top:18px;display:flex;gap:8px;justify-content:flex-end;align-items:center}
.toast{position:fixed;bottom:24px;right:24px;color:#fff;padding:10px 18px;border-radius:6px;font-size:13px;z-index:200;opacity:0;transition:opacity .3s;pointer-events:none}
.toast.show{opacity:1}
</style>
"""

_MODAL_HTML = """
<div class="modal-bg" id="txModal">
  <div class="modal">
    <h3 id="modalTitle">Add Transaction</h3>
    <input type="hidden" id="txId">
    <div style="display:grid;gap:10px">
      <div class="row">
        <label>Date *<input type="date" id="fDate" required></label>
        <label>Direction *
          <select id="fDir"><option value="expense">expense</option><option value="income">income</option></select>
        </label>
        <label>Amount *<input type="number" id="fAmt" min="0" step="0.01" placeholder="0.00"></label>
        <label>Currency
          <select id="fCur"><option value="CAD">CAD</option><option value="BRL">BRL</option><option value="USD">USD</option></select>
        </label>
      </div>
      <div class="row">
        <label>Category<select id="fCat"><option value="">— none —</option></select></label>
        <label>Label<select id="fLbl"><option value="">— none —</option></select></label>
      </div>
      <div class="row">
        <label>Details (merchant)<input type="text" id="fDetails" placeholder="e.g. Starbucks"></label>
        <label>Account<select id="fAcc"><option value="">— none —</option></select></label>
        <label>Card<select id="fCard"><option value="">— none —</option></select></label>
      </div>
      <label>Notes<textarea id="fNotes" rows="2" placeholder="optional free text"></textarea></label>
      <label style="flex-direction:row;align-items:center;gap:8px;font-size:13px;font-weight:400;cursor:pointer">
        <input type="checkbox" id="fCleared" style="width:auto"> Cleared
      </label>
    </div>
    <div class="modal-footer">
      <button class="btn btn-danger btn-sm" id="btnDel" style="display:none;margin-right:auto" onclick="deleteTx()">Delete</button>
      <button class="btn btn-ghost" onclick="closeModal()">Cancel</button>
      <button class="btn btn-primary" onclick="saveTx()">Save</button>
    </div>
  </div>
</div>
<div class="toast" id="toast"></div>
"""

_MODAL_JS = """
<script>
let _dims=null;
async function getDims(){
  if(_dims)return _dims;
  const[cats,accs,lbls,cards]=await Promise.all([
    fetch('/dimensions/categories').then(r=>r.json()),
    fetch('/dimensions/accounts').then(r=>r.json()),
    fetch('/dimensions/labels').then(r=>r.json()),
    fetch('/dimensions/cards').then(r=>r.json()),
  ]);
  _dims={cats,accs,lbls,cards};return _dims;
}
function esc(s){return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}
function mkOpts(items,vf,lf,sel=''){return items.map(i=>`<option value="${esc(vf(i))}"${vf(i)===sel?' selected':''}>${esc(lf(i))}</option>`).join('')}
function toast(msg,err=false){
  const t=document.getElementById('toast');t.textContent=msg;
  t.style.background=err?'#cf222e':'#1a7f37';t.classList.add('show');
  setTimeout(()=>t.classList.remove('show'),2800);
}
async function openModal(row=null){
  const d=await getDims();
  const catSel=row?.category_id||'';
  document.getElementById('fCat').innerHTML='<option value="">— none —</option>'+mkOpts(d.cats,x=>x.id,x=>x.name,catSel);
  document.getElementById('fAcc').innerHTML='<option value="">— none —</option>'+mkOpts(d.accs,x=>x.id,x=>x.name,row?.account_id||'');
  document.getElementById('fCard').innerHTML='<option value="">— none —</option>'+mkOpts(d.cards,x=>String(x.id),x=>x.name,row?.card_id!=null?String(row.card_id):'');
  const fillLbls=cat=>{
    const fl=cat?d.lbls.filter(l=>l.category_id===cat):d.lbls;
    document.getElementById('fLbl').innerHTML='<option value="">— none —</option>'+mkOpts(fl,x=>String(x.id),x=>x.name,row?.label_id!=null?String(row.label_id):'');
  };
  fillLbls(catSel);
  document.getElementById('fCat').onchange=e=>fillLbls(e.target.value);
  document.getElementById('txId').value=row?.id||'';
  const today=new Date();const localDate=today.getFullYear()+'-'+String(today.getMonth()+1).padStart(2,'0')+'-'+String(today.getDate()).padStart(2,'0');
  document.getElementById('fDate').value=row?.occurred_on||localDate;
  document.getElementById('fDir').value=row?.direction||'expense';
  document.getElementById('fAmt').value=row?.amount!=null?Math.abs(row.amount):'';
  document.getElementById('fCur').value=row?.currency||'CAD';
  document.getElementById('fDetails').value=row?.details||'';
  document.getElementById('fNotes').value=row?.notes||'';
  document.getElementById('fCleared').checked=row!=null?!!row.cleared:true;
  document.getElementById('modalTitle').textContent=row?'Edit Transaction':'Add Transaction';
  document.getElementById('btnDel').style.display=row?'inline-flex':'none';
  document.getElementById('txModal').classList.add('open');
}
function closeModal(){document.getElementById('txModal').classList.remove('open')}
document.getElementById('txModal').addEventListener('click',e=>{if(e.target===e.currentTarget)closeModal()});
async function saveTx(){
  const id=document.getElementById('txId').value;
  const p={
    occurred_on:document.getElementById('fDate').value,
    direction:document.getElementById('fDir').value,
    amount:parseFloat(document.getElementById('fAmt').value),
    currency:document.getElementById('fCur').value,
    details:document.getElementById('fDetails').value||null,
    notes:document.getElementById('fNotes').value||null,
    cleared:document.getElementById('fCleared').checked,
    category_id:document.getElementById('fCat').value||null,
    account_id:document.getElementById('fAcc').value||null,
    card_id:document.getElementById('fCard').value?parseInt(document.getElementById('fCard').value):null,
    label_id:document.getElementById('fLbl').value?parseInt(document.getElementById('fLbl').value):null,
  };
  if(!p.occurred_on||isNaN(p.amount)){toast('Date and amount are required',true);return}
  try{
    const res=await fetch(id?`/transactions/${id}`:'/transactions/',{
      method:id?'PUT':'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(p)
    });
    if(!res.ok){const t=await res.text();toast('Server error: '+t,true);return;}
    toast(id?'Saved ✓':'Added ✓');closeModal();
    if(typeof reload==='function')reload();
    if(typeof loadSummary==='function')loadSummary();
  }catch(e){toast('Error: '+e.message,true)}
}
async function deleteTx(){
  const id=document.getElementById('txId').value;
  if(!id||!confirm('Delete this transaction? This cannot be undone.'))return;
  try{
    const res=await fetch(`/transactions/${id}`,{method:'DELETE'});
    if(!res.ok){const t=await res.text();toast('Server error: '+t,true);return;}
    toast('Deleted ✓');closeModal();
    if(typeof reload==='function')reload();
    if(typeof loadSummary==='function')loadSummary();
  }catch(e){toast('Error: '+e.message,true)}
}
</script>
"""


def _page(nav_active: str, body: str, extra_js: str = "") -> str:
    links = [("home", "/ui/"), ("transactions", "/ui/transactions"), ("dimensions", "/ui/dimensions")]
    nav = "".join(
        f'<a href="{h}" class="{"active" if n==nav_active else ""}">{n.capitalize()}</a>'
        for n, h in links
    )
    return (
        f"<!DOCTYPE html><html lang='en'><head><meta charset='UTF-8'>"
        f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>Personal Finance</title>{_CSS}</head>"
        f"<body><nav><a class='brand' href='/ui/'>💰 Finance</a>{nav}</nav>"
        f"{_MODAL_HTML}"
        f"<div class='page'>{body}</div>"
        f"{_MODAL_JS}{extra_js}</body></html>"
    )


# ── Home dashboard ───────────────────────────────────────────────────────────

_HOME_BODY = """
<h2>Dashboard</h2>
<div class="grid g4" id="statCards" style="margin-bottom:20px">
  <div class="card stat"><div class="val income" id="sInc">—</div><div class="lbl">Income this month</div></div>
  <div class="card stat"><div class="val expense" id="sExp">—</div><div class="lbl">Expenses this month</div></div>
  <div class="card stat"><div class="val" id="sNet">—</div><div class="lbl">Net this month</div></div>
  <div class="card stat"><div class="val" id="sTx">—</div><div class="lbl">Transactions</div></div>
</div>
<div class="grid g2">
  <div class="card">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
      <h3>Top expenses — <span id="periodLabel"></span></h3>
      <div style="display:flex;gap:8px">
        <select id="sumYear" style="width:90px"></select>
        <select id="sumMonth" style="width:90px">
          <option value="1">Jan</option><option value="2">Feb</option><option value="3">Mar</option>
          <option value="4">Apr</option><option value="5">May</option><option value="6">Jun</option>
          <option value="7">Jul</option><option value="8">Aug</option><option value="9">Sep</option>
          <option value="10">Oct</option><option value="11">Nov</option><option value="12">Dec</option>
        </select>
        <button class="btn btn-ghost btn-sm" onclick="loadSummary()">Go</button>
      </div>
    </div>
    <table id="sumTable">
      <thead><tr><th>Category</th><th style="text-align:right">Amount</th><th style="text-align:right">Txns</th></tr></thead>
      <tbody id="sumBody"><tr><td colspan="3" class="empty">Loading…</td></tr></tbody>
    </table>
  </div>
  <div class="card">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
      <h3>Add transaction</h3>
      <button class="btn btn-primary btn-sm" onclick="openModal()">+ New</button>
    </div>
    <p style="color:#777;font-size:12px;line-height:1.6">
      Click <b>+ New</b> to log a transaction. All required fields are marked with *.
      After saving it will appear in the summary and the transactions list.
    </p>
    <div style="margin-top:16px;border-top:1px solid #eee;padding-top:14px">
      <h3 style="margin-bottom:8px">Recent (last 5)</h3>
      <div id="recentList"><div class="empty">Loading…</div></div>
    </div>
  </div>
</div>
"""

_HOME_JS = """
<script>
async function loadSummary(){
  const y=document.getElementById('sumYear').value;
  const m=document.getElementById('sumMonth').value;
  document.getElementById('periodLabel').textContent=document.getElementById('sumMonth').selectedOptions[0].text+' '+y;
  const [summary, txns] = await Promise.all([
    fetch(`/transactions/summary?year=${y}&month=${m}`).then(r=>r.json()),
    fetch(`/transactions/?year=${y}&month=${m}&limit=500`).then(r=>r.json()),
  ]);
  let inc=0,exp=0;
  txns.forEach(r=>{const a=Math.abs(parseFloat(r.amount)||0);r.direction==='income'?inc+=a:exp+=a});
  document.getElementById('sInc').textContent='+'+inc.toFixed(2);
  document.getElementById('sExp').textContent='-'+exp.toFixed(2);
  const net=inc-exp;
  const sn=document.getElementById('sNet');
  sn.textContent=(net>=0?'+':'')+net.toFixed(2);
  sn.className='val '+(net>=0?'income':'expense');
  document.getElementById('sTx').textContent=txns.length;
  const expenses=summary.filter(r=>r.direction==='expense').sort((a,b)=>b.total-a.total);
  document.getElementById('sumBody').innerHTML=expenses.length
    ?expenses.map(r=>`<tr>
        <td><span class="tag">${esc(r.category||'—')}</span></td>
        <td style="text-align:right;color:#cf222e">${parseFloat(r.total).toFixed(2)}</td>
        <td style="text-align:right;color:#999">${r.count}</td>
      </tr>`).join('')
    :'<tr><td colspan="3" class="empty">No data</td></tr>';
  // recent
  const recent=txns.slice(0,5);
  document.getElementById('recentList').innerHTML=recent.length
    ?recent.map(r=>`<div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #f0f0f0">
        <div>
          <span class="tag ${r.direction}">${r.direction}</span>
          <span style="margin-left:8px">${esc(r.label||r.details||'—')}</span>
        </div>
        <b class="${r.direction}">${r.currency} ${Math.abs(parseFloat(r.amount)).toFixed(2)}</b>
      </div>`).join('')
    :'<div class="empty">No transactions this month</div>';
}
// init
const now=new Date();
const yEl=document.getElementById('sumYear');
for(let y=now.getFullYear();y>=2018;y--) yEl.innerHTML+=`<option value="${y}">${y}</option>`;
document.getElementById('sumMonth').value=now.getMonth()+1;
loadSummary();
</script>
"""


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def ui_home() -> HTMLResponse:
    return HTMLResponse(_page("home", _HOME_BODY, _HOME_JS))


# ── Transactions list ────────────────────────────────────────────────────────

_TX_BODY = """
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
  <h2 style="margin:0">Transactions</h2>
  <button class="btn btn-primary" onclick="openModal()">+ New</button>
</div>
<div class="filters">
  <label>Year<input type="number" id="fYear" style="width:80px" placeholder="any"></label>
  <label>Month
    <select id="fMonth">
      <option value="">any</option>
      <option value="1">Jan</option><option value="2">Feb</option><option value="3">Mar</option>
      <option value="4">Apr</option><option value="5">May</option><option value="6">Jun</option>
      <option value="7">Jul</option><option value="8">Aug</option><option value="9">Sep</option>
      <option value="10">Oct</option><option value="11">Nov</option><option value="12">Dec</option>
    </select>
  </label>
  <label>Direction
    <select id="fDir2"><option value="">all</option><option value="expense">expense</option><option value="income">income</option></select>
  </label>
  <label>Search (label / details / notes)
    <input type="text" id="fSearch" style="width:220px" placeholder="type to filter…">
  </label>
  <label>&nbsp;<button class="btn btn-primary btn-sm" onclick="reload()">Load</button></label>
</div>
<div class="stats-bar" id="statsBar">—</div>
<div class="card" style="padding:0;overflow-x:auto">
  <table>
    <thead>
      <tr>
        <th onclick="sort('occurred_on')">Date</th>
        <th onclick="sort('direction')">Dir</th>
        <th onclick="sort('amount')">Amount</th>
        <th onclick="sort('label')">Label</th>
        <th onclick="sort('details')">Details</th>
        <th onclick="sort('notes')">Notes</th>
        <th onclick="sort('account_raw')">Account</th>
        <th onclick="sort('cleared')">Clr</th>
        <th>Edit</th>
      </tr>
    </thead>
    <tbody id="txBody"><tr><td colspan="9" class="empty">Click Load to fetch transactions.</td></tr></tbody>
  </table>
</div>
"""

_TX_JS = """
<script>
let rows=[],sortCol='occurred_on',sortDir=-1;

async function reload(){
  const y=document.getElementById('fYear').value;
  const m=document.getElementById('fMonth').value;
  const d=document.getElementById('fDir2').value;
  let url='/transactions/?limit=500';
  if(y)url+='&year='+y;
  if(m)url+='&month='+m;
  if(d)url+='&direction='+d;
  document.getElementById('statsBar').textContent='Loading…';
  rows=await fetch(url).then(r=>r.json()).catch(()=>[]);
  render();
}

function render(){
  const q=document.getElementById('fSearch').value.toLowerCase();
  let data=rows.filter(r=>!q||[r.label,r.details,r.notes].some(v=>v&&v.toLowerCase().includes(q)));
  data=[...data].sort((a,b)=>{
    let av=a[sortCol]??'',bv=b[sortCol]??'';
    if(sortCol==='amount'){av=parseFloat(av)||0;bv=parseFloat(bv)||0}
    return av<bv?sortDir:av>bv?-sortDir:0;
  });
  const inc=data.filter(r=>r.direction==='income').reduce((s,r)=>s+Math.abs(parseFloat(r.amount)||0),0);
  const exp=data.filter(r=>r.direction==='expense').reduce((s,r)=>s+Math.abs(parseFloat(r.amount)||0),0);
  document.getElementById('statsBar').innerHTML=
    `<span><b>${data.length}</b> rows</span>`+
    `<span>Income: <b class="income">+${inc.toFixed(2)}</b></span>`+
    `<span>Expenses: <b class="expense">-${exp.toFixed(2)}</b></span>`+
    `<span>Net: <b class="${inc-exp>=0?'income':'expense'}">${(inc-exp>=0?'+':'')+(inc-exp).toFixed(2)}</b></span>`;
  document.querySelectorAll('th').forEach(t=>t.classList.remove('asc','desc'));
  const cols=['occurred_on','direction','amount','label','details','notes','account_raw','cleared'];
  const idx=cols.indexOf(sortCol);
  if(idx>=0)document.querySelectorAll('th')[idx].classList.add(sortDir===1?'asc':'desc');
  document.getElementById('txBody').innerHTML=data.length
    ?data.map(r=>`<tr>
        <td>${esc(r.occurred_on||'')}</td>
        <td><span class="tag ${r.direction}">${r.direction}</span></td>
        <td style="text-align:right"><b class="${r.direction}">${r.currency} ${Math.abs(parseFloat(r.amount||0)).toFixed(2)}</b></td>
        <td>${r.label?`<span class="tag">${esc(r.label)}</span>`:''}</td>
        <td>${esc(r.details||'')}</td>
        <td style="color:#999">${esc(r.notes||'')}</td>
        <td>${esc(r.account_raw||'')}</td>
        <td style="text-align:center">${r.cleared?'✓':''}</td>
        <td><button class="btn btn-ghost btn-sm" onclick='editRow(${JSON.stringify(r)})'>Edit</button></td>
      </tr>`).join('')
    :'<tr><td colspan="9" class="empty">No transactions found.</td></tr>';
}

function sort(col){if(sortCol===col)sortDir*=-1;else{sortCol=col;sortDir=-1}render()}

async function editRow(row){
  // fetch fresh copy so we have all FK fields
  const full=await fetch(`/transactions/${row.id}`).then(r=>r.json());
  openModal(full);
}

document.getElementById('fSearch').addEventListener('input',render);

// auto-load current month
const now=new Date();
document.getElementById('fYear').value=now.getFullYear();
document.getElementById('fMonth').value=now.getMonth()+1;
reload();
</script>
"""


@router.get("/transactions", response_class=HTMLResponse, include_in_schema=False)
async def ui_transactions() -> HTMLResponse:
    return HTMLResponse(_page("transactions", _TX_BODY, _TX_JS))


# ── Dimensions management ────────────────────────────────────────────────────

_DIM_BODY = """
<h2>Dimensions</h2>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:20px">

  <!-- CATEGORIES -->
  <div class="card" style="padding:0;overflow:hidden">
    <div style="display:flex;justify-content:space-between;align-items:center;padding:14px 16px;border-bottom:1px solid #eee">
      <h3 style="margin:0">Categories</h3>
      <button class="btn btn-primary btn-sm" onclick="openCatModal()">+ Add</button>
    </div>
    <table>
      <thead><tr><th>Name</th><th>Kind</th><th style="width:64px"></th></tr></thead>
      <tbody id="catBody"><tr><td colspan="3" class="empty">Loading…</td></tr></tbody>
    </table>
  </div>

  <!-- LABELS -->
  <div class="card" style="padding:0;overflow:hidden">
    <div style="display:flex;justify-content:space-between;align-items:center;padding:14px 16px;border-bottom:1px solid #eee">
      <h3 style="margin:0">Labels</h3>
      <div style="display:flex;gap:8px;align-items:center">
        <input type="text" id="lblSearch" placeholder="search…" style="width:140px;padding:4px 8px;font-size:12px" oninput="renderLabels()">
        <button class="btn btn-primary btn-sm" onclick="openLblModal()">+ Add</button>
      </div>
    </div>
    <div style="max-height:500px;overflow-y:auto">
      <table>
        <thead><tr><th>Name</th><th>Category</th><th>Routine</th><th>Active</th><th style="width:64px"></th></tr></thead>
        <tbody id="lblBody"><tr><td colspan="5" class="empty">Loading…</td></tr></tbody>
      </table>
    </div>
  </div>

</div>

<!-- Category modal -->
<div class="modal-bg" id="catModal">
  <div class="modal" style="width:min(360px,95vw)">
    <h3 id="catModalTitle">Add Category</h3>
    <input type="hidden" id="catId">
    <div style="display:grid;gap:12px">
      <label>Name *<input type="text" id="catName"></label>
      <label>Kind
        <select id="catKind">
          <option value="">— none —</option>
          <option value="expense">expense</option>
          <option value="income">income</option>
          <option value="transfer">transfer</option>
        </select>
      </label>
    </div>
    <div class="modal-footer">
      <button class="btn btn-danger btn-sm" id="catBtnDel" style="display:none;margin-right:auto" onclick="deleteCat()">Delete</button>
      <button class="btn btn-ghost" onclick="closeCatModal()">Cancel</button>
      <button class="btn btn-primary" onclick="saveCat()">Save</button>
    </div>
  </div>
</div>

<!-- Label modal -->
<div class="modal-bg" id="lblModal">
  <div class="modal" style="width:min(400px,95vw)">
    <h3 id="lblModalTitle">Add Label</h3>
    <input type="hidden" id="lblId">
    <div style="display:grid;gap:12px">
      <label>Name *<input type="text" id="lblName"></label>
      <label>Category<select id="lblCat"><option value="">— none —</option></select></label>
      <label style="flex-direction:row;align-items:center;gap:8px;font-size:13px;font-weight:400;cursor:pointer">
        <input type="checkbox" id="lblRoutine" style="width:auto"> Routine
      </label>
      <label style="flex-direction:row;align-items:center;gap:8px;font-size:13px;font-weight:400;cursor:pointer">
        <input type="checkbox" id="lblActive" style="width:auto"> Active
      </label>
    </div>
    <div class="modal-footer">
      <button class="btn btn-danger btn-sm" id="lblBtnDel" style="display:none;margin-right:auto" onclick="deleteLbl()">Delete</button>
      <button class="btn btn-ghost" onclick="closeLblModal()">Cancel</button>
      <button class="btn btn-primary" onclick="saveLbl()">Save</button>
    </div>
  </div>
</div>
"""

_DIM_JS = """
<script>
let _cats=[], _lbls=[];

async function loadAll(){
  [_cats, _lbls] = await Promise.all([
    fetch('/dimensions/categories').then(r=>r.json()),
    fetch('/dimensions/labels').then(r=>r.json()),
  ]);
  renderCats(); renderLabels();
}

// ── categories ────────────────────────────────────────────────────────────
function renderCats(){
  document.getElementById('catBody').innerHTML = _cats.length
    ? _cats.map(c=>`<tr>
        <td><b>${esc(c.name)}</b></td>
        <td>${c.kind?`<span class="tag ${c.kind}">${c.kind}</span>`:''}</td>
        <td><button class="btn btn-ghost btn-sm" onclick='openCatModal(${JSON.stringify(c)})'>Edit</button></td>
      </tr>`).join('')
    : '<tr><td colspan="3" class="empty">No categories</td></tr>';
}

function openCatModal(row=null){
  document.getElementById('catId').value = row?.id||'';
  document.getElementById('catName').value = row?.name||'';
  document.getElementById('catKind').value = row?.kind||'';
  document.getElementById('catModalTitle').textContent = row ? 'Edit Category' : 'Add Category';
  document.getElementById('catBtnDel').style.display = row ? 'inline-flex' : 'none';
  document.getElementById('catModal').classList.add('open');
}
function closeCatModal(){ document.getElementById('catModal').classList.remove('open'); }
document.getElementById('catModal').addEventListener('click',e=>{if(e.target===e.currentTarget)closeCatModal()});

async function saveCat(){
  const id = document.getElementById('catId').value;
  const name = document.getElementById('catName').value.trim();
  const kind = document.getElementById('catKind').value || null;
  if(!name){ toast('Name is required',true); return; }
  try{
    const res = await fetch(id ? `/dimensions/categories/${id}` : '/dimensions/categories',{
      method: id ? 'PUT' : 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({name, kind})
    });
    if(!res.ok){ const t=await res.text(); toast('Error: '+t,true); return; }
    toast(id ? 'Category updated ✓' : 'Category added ✓');
    closeCatModal();
    _cats=null; _lbls=null; // bust cache
    await loadAll();
  } catch(e){ toast('Error: '+e.message,true); }
}

async function deleteCat(){
  const id = document.getElementById('catId').value;
  if(!id||!confirm('Delete this category? Labels linked to it will lose their category.')) return;
  try{
    await fetch(`/dimensions/categories/${id}`, {method:'DELETE'});
    toast('Deleted ✓'); closeCatModal();
    _cats=null; _lbls=null;
    await loadAll();
  } catch(e){ toast('Error: '+e.message,true); }
}

// ── labels ────────────────────────────────────────────────────────────────
function renderLabels(){
  const q = document.getElementById('lblSearch').value.toLowerCase();
  const data = q ? _lbls.filter(l=>l.name.toLowerCase().includes(q)) : _lbls;
  const catMap = Object.fromEntries(_cats.map(c=>[c.id,c.name]));
  document.getElementById('lblBody').innerHTML = data.length
    ? data.map(l=>`<tr>
        <td>${esc(l.name)}</td>
        <td>${l.category_id?`<span class="tag">${esc(catMap[l.category_id]||'?')}</span>`:''}</td>
        <td style="text-align:center">${l.is_routine?'✓':''}</td>
        <td style="text-align:center">${l.active?'✓':''}</td>
        <td><button class="btn btn-ghost btn-sm" onclick='openLblModal(${JSON.stringify(l)})'>Edit</button></td>
      </tr>`).join('')
    : '<tr><td colspan="5" class="empty">No labels</td></tr>';
}

async function openLblModal(row=null){
  // populate category dropdown
  document.getElementById('lblCat').innerHTML = '<option value="">— none —</option>' +
    _cats.map(c=>`<option value="${esc(c.id)}"${c.id===row?.category_id?' selected':''}>${esc(c.name)}</option>`).join('');
  document.getElementById('lblId').value = row?.id!=null ? String(row.id) : '';
  document.getElementById('lblName').value = row?.name||'';
  document.getElementById('lblRoutine').checked = !!row?.is_routine;
  document.getElementById('lblActive').checked = row!=null ? !!row.active : true;
  document.getElementById('lblModalTitle').textContent = row ? 'Edit Label' : 'Add Label';
  document.getElementById('lblBtnDel').style.display = row ? 'inline-flex' : 'none';
  document.getElementById('lblModal').classList.add('open');
}
function closeLblModal(){ document.getElementById('lblModal').classList.remove('open'); }
document.getElementById('lblModal').addEventListener('click',e=>{if(e.target===e.currentTarget)closeLblModal()});

async function saveLbl(){
  const id = document.getElementById('lblId').value;
  const name = document.getElementById('lblName').value.trim();
  const category_id = document.getElementById('lblCat').value || null;
  const is_routine = document.getElementById('lblRoutine').checked;
  const active = document.getElementById('lblActive').checked;
  if(!name){ toast('Name is required',true); return; }
  try{
    const res = await fetch(id ? `/dimensions/labels/${id}` : '/dimensions/labels',{
      method: id ? 'PUT' : 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({name, category_id, is_routine, active})
    });
    if(!res.ok){ const t=await res.text(); toast('Error: '+t,true); return; }
    toast(id ? 'Label updated ✓' : 'Label added ✓');
    closeLblModal();
    _cats=null; _lbls=null;
    await loadAll();
  } catch(e){ toast('Error: '+e.message,true); }
}

async function deleteLbl(){
  const id = document.getElementById('lblId').value;
  if(!id||!confirm('Delete this label? Transactions using it will lose the label link.')) return;
  try{
    await fetch(`/dimensions/labels/${id}`, {method:'DELETE'});
    toast('Deleted ✓'); closeLblModal();
    _cats=null; _lbls=null;
    await loadAll();
  } catch(e){ toast('Error: '+e.message,true); }
}

loadAll();
</script>
"""


@router.get("/dimensions", response_class=HTMLResponse, include_in_schema=False)
async def ui_dimensions() -> HTMLResponse:
    return HTMLResponse(_page("dimensions", _DIM_BODY, _DIM_JS))
