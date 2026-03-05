

// =======================
// ERP2_EXAMPLE_BODY
// =======================

let ERP2_EXAMPLES = {};

async function loadExamples(){
  try{
    const r = await fetch("/erp2/static/item_examples.json");
    if(r.ok){
      ERP2_EXAMPLES = await r.json();
    }
  }catch(e){
    console.warn("example load failed",e);
  }
}

function applyExample(method,path){
  const key = method+" "+path;
  if(ERP2_EXAMPLES[key]){
    const body = document.getElementById("erp2_req_body");
    if(body && body.value.trim()===""){
      body.value = JSON.stringify(ERP2_EXAMPLES[key],null,2);
    }
  }
}

document.addEventListener("DOMContentLoaded", loadExamples);



// =======================
// TASK_ERP2_03_B_RUNNER_ENHANCE
// =======================
function $(id){ return document.getElementById(id); }

function setErr(msg){
  const el = $("erp2_err");
  if(el) el.textContent = msg || "";
}

function prettyJson(obj){
  try { return JSON.stringify(obj, null, 2); } catch(e){ return String(obj); }
}

function tryParseJson(txt){
  const t = (txt || "").trim();
  if(!t) return { ok:true, value:null, empty:true };
  try {
    return { ok:true, value: JSON.parse(t), empty:false };
  } catch(e){
    return { ok:false, error: e };
  }
}

function lsKey(method, path){
  return "erp2.body." + (method||"").toUpperCase() + ":" + (path||"");
}

function restoreBody(method, path){
  const el = $("erp2_req_body");
  if(!el) return;
  const k = lsKey(method, path);
  const v = localStorage.getItem(k);
  if(v !== null) el.value = v;
}

function saveBody(method, path, bodyText){
  const k = lsKey(method, path);
  localStorage.setItem(k, bodyText || "");
}

async function sendRunnerRequest(method, path, bodyText){
  const metaEl = $("erp2_resp_meta");
  const bodyEl = $("erp2_resp_body");
  const t0 = performance.now();

  const url = path; // same-origin
  const headers = { "Content-Type": "application/json" };

  let opts = { method, headers, credentials: "same-origin" };

  // For non-GET, validate json
  const m = (method||"GET").toUpperCase();
  if(m !== "GET" && m !== "HEAD"){
    const parsed = tryParseJson(bodyText);
    if(!parsed.ok){
      setErr("JSON 无效：" + parsed.error);
      throw new Error("invalid json");
    }
    opts.body = parsed.empty ? "{}" : JSON.stringify(parsed.value);
  }

  const resp = await fetch(url, opts);
  const t1 = performance.now();
  const ms = Math.round(t1 - t0);

  let text = await resp.text();
  let shown = text;

  try {
    const j = JSON.parse(text);
    shown = prettyJson(j);
  } catch(e) {
    // non-json, keep raw
  }

  if(metaEl){
    metaEl.textContent = `HTTP ${resp.status} ${resp.statusText}   ${ms}ms   ${m} ${path}`;
  }
  if(bodyEl){
    bodyEl.textContent = shown;
  }

  if(!resp.ok){
    setErr(`请求失败：HTTP ${resp.status}`);
  } else {
    setErr("");
  }
}

function wireRunner(){
  const methodEl = $("erp2_req_method");
  const pathEl   = $("erp2_req_path");
  const bodyEl   = $("erp2_req_body");
  const sendBtn  = $("erp2_send");
  if(!methodEl || !pathEl || !bodyEl || !sendBtn) return;

  // restore on change
  function onSelChange(){
    restoreBody(methodEl.value, pathEl.value);
  }
  methodEl.addEventListener("change", onSelChange);
  pathEl.addEventListener("change", onSelChange);

  sendBtn.addEventListener("click", async ()=>{
    const method = (methodEl.value || "GET").toUpperCase();
    const path = (pathEl.value || "").trim();
    const bodyText = bodyEl.value || "";
    if(!path){
      setErr("请输入 Path，例如：/api/subjects");
      return;
    }

    // remember body
    saveBody(method, path, bodyText);

    // dangerous confirm (from TASK-ERP2-03-A)
    if(typeof confirmDangerous === "function"){
      if(!confirmDangerous(method, path)) return;
    }

    try{
      await sendRunnerRequest(method, path, bodyText);
    }catch(e){
      // errors already shown
    }
  });

  // initial restore
  restoreBody(methodEl.value, pathEl.value);
}

document.addEventListener("DOMContentLoaded", wireRunner);



// =======================
// ERP2_SAFE_METHODS
// =======================

const SAFE_METHODS = ["GET","HEAD","OPTIONS"];

function confirmDangerous(method,path){
  if(SAFE_METHODS.includes(method)){
    return true;
  }

  return confirm(
    "危险操作确认:\n" +
    method + " " + path + "\n\n" +
    "该操作可能修改系统数据，是否继续？"
  );
}


(async function(){
  const $=id=>document.getElementById(id);
  const menuEl=$("menu"), qEl=$("q"), reloadBtn=$("reload");
  const mEl=$("m"), pEl=$("p"), bEl=$("b");
  const sendBtn=$("send"), copyBtn=$("copy");
  const curEl=$("cur"), hintEl=$("hint"), outEl=$("out"), stEl=$("st"), rtEl=$("rt");
  let catalog=null, active=null;

  function fmt(text){ try{return JSON.stringify(JSON.parse(text),null,2);}catch(_){return text;} }
  function guessMethod(path){
    const p=path.toLowerCase();
    if (/(generate|build|import|validate|sync|commit|run|confirm|configure)/.test(p)) return "POST";
    return "GET";
  }
  function buildMenu(filter){
    const f=(filter||"").trim().toLowerCase();
    menuEl.innerHTML="";
    for(const sec of (catalog?.menus||[])){
      const items=sec.items.filter(it => !f || it.path.toLowerCase().includes(f));
      if(!items.length) continue;
      const wrap=document.createElement("div"); wrap.className="sec";
      const title=document.createElement("div"); title.className="sec-title"; title.textContent=`${sec.name} (${items.length})`;
      wrap.appendChild(title);
      for(const it of items){
        const a=document.createElement("a"); a.className="item"; a.href="javascript:void(0)"; a.textContent=`${it.path}  [${it.methods.join(",")}]`;
        a.onclick=()=>select(it,a);
        wrap.appendChild(a);
      }
      menuEl.appendChild(wrap);
    }
  }
  function select(it, link){
    if(active) active.classList.remove("active");
    active=link; active.classList.add("active");
    curEl.textContent=it.path;
    const m=it.methods.includes("GET") ? guessMethod(it.path) : it.methods[0];
    mEl.value=m;
    pEl.value=it.path;
    hintEl.textContent=`methods=${it.methods.join(", ")}`;
    if(m==="GET") bEl.value="";
  }
  async function load(){
    const r=await fetch("/erp2/catalog.json",{cache:"no-store"});
    catalog=await r.json();
    buildMenu(qEl.value);
  }
  async function send(){
    const method=mEl.value, path=pEl.value.trim();
    if(!path) return;
    const t0=performance.now();
    stEl.textContent="..."; rtEl.textContent=""; outEl.textContent="请求中...";
    try{
      let body=null;
      if(method!=="GET" && method!=="HEAD"){
        const raw=bEl.value.trim();
        body=raw?raw:"{}";
      }
      const r=await fetch(path,{method,headers:{"Content-Type":"application/json"},body,credentials:"same-origin"});
      const t1=performance.now();
      stEl.textContent="HTTP "+r.status; rtEl.textContent="rt="+Math.round(t1-t0)+"ms";
      const text=await r.text();
      outEl.textContent=fmt(text);
    }catch(e){
      const t1=performance.now();
      stEl.textContent="ERR"; rtEl.textContent="rt="+Math.round(t1-t0)+"ms";
      outEl.textContent=String(e);
    }
  }
  function curlCmd(){
    const method=mEl.value, path=pEl.value.trim();
    let cmd=`curl -i -X ${method} http://127.0.0.1:5000${path} -H "Content-Type: application/json"`;
    if(method!=="GET" && method!=="HEAD"){
      const raw=bEl.value.trim()||"{}";
      cmd+=` --data '${raw.replace(/'/g,"'\\''")}'`;
    }
    return cmd;
  }

  reloadBtn.onclick=()=>load().catch(e=>menuEl.innerHTML="<div class='muted'>load failed:"+e+"</div>");
  qEl.oninput=()=>buildMenu(qEl.value);
  sendBtn.onclick=send;
  copyBtn.onclick=async ()=>{ const t=curlCmd(); try{await navigator.clipboard.writeText(t);}catch(_){} outEl.textContent=t; };

  await load();
})();


// =======================
// TASK_ERP2_03_D_WIRE_EXAMPLES
// =======================
function wireExamples(){
  const methodEl = document.getElementById("erp2_req_method");
  const pathEl   = document.getElementById("erp2_req_path");
  const bodyEl   = document.getElementById("erp2_req_body");
  const fillBtn  = document.getElementById("erp2_fill_example");
  if(!methodEl || !pathEl || !bodyEl) return;

  function autoFill(){
    const m = (methodEl.value || "GET").toUpperCase();
    const p = (pathEl.value || "").trim();
    if(!p) return;
    // only auto-fill when empty
    applyExample(m, p);
  }

  methodEl.addEventListener("change", autoFill);
  pathEl.addEventListener("change", autoFill);

  if(fillBtn){
    fillBtn.addEventListener("click", ()=>{
      const m = (methodEl.value || "GET").toUpperCase();
      const p = (pathEl.value || "").trim();
      if(!p) return;
      const key = m + " " + p;
      if(!ERP2_EXAMPLES[key]){
        alert("没有找到该接口的示例 body");
        return;
      }
      if(bodyEl.value.trim() !== ""){
        const ok = confirm("将覆盖当前 Body，是否继续？");
        if(!ok) return;
      }
      bodyEl.value = JSON.stringify(ERP2_EXAMPLES[key], null, 2);
    });
  }

  // initial try
  autoFill();
}

document.addEventListener("DOMContentLoaded", wireExamples);
