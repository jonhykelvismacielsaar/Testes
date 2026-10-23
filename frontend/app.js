// VoiceStudio Arena — Frontend logic
const API = ""; // same origin (proxied) ou http://localhost:3900 quando dev
let currentEngine = "arena-tts";
let wsDict = null, mediaRecorder = null;

async function api(path, opts={}) {
  const res = await fetch(API + path, opts);
  if (!res.ok) throw new Error(await res.text());
  const ct = res.headers.get("content-type")||"";
  return ct.includes("application/json") ? res.json() : res;
}

// Tabs
function switchTab(name){
  document.querySelectorAll(".tab-btn").forEach(b=>b.classList.remove("tab-active"));
  document.querySelector(`[data-tab="${name}"]`)?.classList.add("tab-active");
  document.querySelectorAll(".tab-pane").forEach(p=>p.classList.add("hidden"));
  document.getElementById(`tab-${name}`)?.classList.remove("hidden");
  window.scrollTo({top:0, behavior:'smooth'});
}
document.querySelectorAll(".tab-btn").forEach(b=>b.addEventListener("click",()=>switchTab(b.dataset.tab)));

// Load voices
async function loadVoices(){
  try{
    const voices = await api("/api/voices");
    const sel = document.getElementById("voiceSelect");
    const dubVoice = document.getElementById("dubVoice");
    const bookVoice = document.getElementById("bookVoice");
    const list = document.getElementById("voicesList");
    sel.innerHTML = voices.map(v=>`<option value="${v.id}">${v.name} — ${v.lang} ${v.cloned?'🧬':''}</option>`).join("");
    if(dubVoice) dubVoice.innerHTML = voices.map(v=>`<option value="${v.id}">${v.name} (${v.lang})</option>`).join("");
    if(bookVoice) bookVoice.innerHTML = voices.map(v=>`<option value="${v.id}">${v.name}</option>`).join("");
    // sidebar
    if(list) list.innerHTML = voices.slice(0,8).map(v=>`
      <div class="flex items-center gap-3 p-2.5 rounded-xl bg-ink border border-white/5">
        <div class="w-8 h-8 rounded-full bg-gradient-to-br from-accent to-accent2 flex items-center justify-center text-xs font-bold">${v.name[0]}</div>
        <div class="flex-1 min-w-0"><div class="font-semibold text-xs truncate">${v.name}</div><div class="text-[11px] text-muted">${v.lang} • ${v.engine}</div></div>
        <button onclick="previewVoiceById('${v.id}')" class="w-7 h-7 rounded-full bg-white text-ink flex items-center justify-center text-xs"><i class="fa-solid fa-play text-[10px]"></i></button>
      </div>`).join("");
  }catch(e){console.error(e)}
}
async function previewVoiceById(id){ document.getElementById("voiceSelect").value=id; previewVoice(); }

async function loadEngines(){
  try{
    const engines = await api("/api/engines");
    const c = document.getElementById("engineChips");
    c.innerHTML = Object.entries(engines).map(([id,e])=>`
      <button data-engine="${id}" class="engine-chip px-3 py-1.5 rounded-full border text-xs font-semibold transition ${id===currentEngine?'bg-accent text-white border-accent':'bg-white/5 border-white/10 text-muted hover:bg-white/10'}">${e.label.split(" —")[0]} <span class="opacity-60">${e.langs||''}</span></button>
    `).join("");
    c.querySelectorAll(".engine-chip").forEach(b=>b.addEventListener("click",()=>{
      currentEngine=b.dataset.engine;
      c.querySelectorAll(".engine-chip").forEach(x=>x.className="engine-chip px-3 py-1.5 rounded-full border text-xs font-semibold transition bg-white/5 border-white/10 text-muted hover:bg-white/10");
      b.className="engine-chip px-3 py-1.5 rounded-full border text-xs font-semibold transition bg-accent text-white border-accent";
    }));
    // models grid
    const grid=document.getElementById("modelsGrid");
    if(grid){
      grid.innerHTML = Object.entries(engines).map(([id,e])=>`
        <div class="p-4 rounded-xl bg-ink border border-white/5">
          <div class="font-bold text-sm flex items-center gap-2">${e.label} <span class="ml-auto text-[10px] px-2 py-0.5 rounded-full ${e.role==='TTS'?'bg-accent/20 text-accent':'bg-success/15 text-success'}">${e.role}</span></div>
          <div class="text-xs text-muted mt-1">${e.desc||''}</div>
          <div class="mt-3 flex gap-2"><span class="text-xs px-2 py-1 rounded-full bg-white/5 border border-white/10">${id}</span><span class="text-xs px-2 py-1 rounded-full bg-success/15 text-success border border-success/20">instalado</span></div>
        </div>`).join("");
    }
  }catch(e){console.warn(e)}
}

async function loadLanguages(){
  try{
    const langs = await api("/api/languages");
    const opts = langs.map(l=>`<option value="${l.code}">${l.name}</option>`).join("");
    ["cloneLang","designLang","dubSource","dubTarget","sttLang"].forEach(id=>{
      const el=document.getElementById(id);
      if(!el) return;
      if(id==="sttLang"){ /* já tem Auto */ el.innerHTML += langs.map(l=>`<option value="${l.code.split('-')[0]}">${l.name}</option>`).join(""); }
      else el.innerHTML=opts;
    });
    document.getElementById("dubTarget").value="en-US";
  }catch(e){}
}

async function loadPresets(){
  try{
    const presets = await api("/api/voice-presets");
    const c=document.getElementById("presetChips");
    if(!c) return;
    c.innerHTML = presets.map(p=>`<button data-prompt="${p.prompt.replace(/"/g,'&quot;')}" class="preset-btn px-3 py-1.5 rounded-full bg-ink border border-white/10 text-xs hover:border-accent transition">${p.label}</button>`).join("");
    c.querySelectorAll(".preset-btn").forEach(b=>b.addEventListener("click",()=>{
      document.getElementById("designPrompt").value=b.dataset.prompt;
    }));
  }catch(e){}
}

async function loadHistory(){
  try{
    const hist = await api("/api/generations");
    const el=document.getElementById("historyList");
    if(!el) return;
    if(!hist.length){ el.innerHTML=`<div class="text-xs text-muted text-center py-4">Nenhum áudio ainda. Gere o primeiro!</div>`; return; }
    el.innerHTML = hist.map(h=>`
      <div class="flex items-center gap-3 p-3 rounded-xl bg-ink border border-white/5">
        <button onclick="playHistory('${h.id}')" class="w-8 h-8 rounded-full bg-accent text-white flex items-center justify-center shrink-0"><i class="fa-solid fa-play text-[11px]"></i></button>
        <div class="flex-1 min-w-0"><div class="text-xs font-semibold truncate">${(h.text||'').slice(0,70)}</div><div class="text-[11px] text-muted font-mono">${h.voice} • ${h.duration}s • ${new Date(h.created_at).toLocaleString('pt-BR')}</div></div>
        <button onclick="deleteHistory('${h.id}')" class="w-7 h-7 rounded-full bg-white/5 border border-white/10 flex items-center justify-center hover:bg-red-500/20 hover:text-red-400"><i class="fa-solid fa-trash text-[11px]"></i></button>
      </div>`).join("");
  }catch(e){}
}
async function playHistory(id){
  const audio=document.getElementById("genAudio");
  const out=document.getElementById("genOutput");
  out.classList.remove("hidden");
  audio.src=`/api/audio/${id}`;
  audio.play();
  document.getElementById("genMeta").textContent=`• ${id} • histórico`;
}
async function deleteHistory(id){
  if(!confirm("Deletar este áudio?")) return;
  await fetch(`/api/generations/${id}`,{method:"DELETE"});
  loadHistory();
}

// Generate
document.getElementById("btnGenerate")?.addEventListener("click", async ()=>{
  const text=document.getElementById("ttsText").value.trim();
  const voice=document.getElementById("voiceSelect").value;
  const format=document.getElementById("formatSelect").value;
  const rate=document.getElementById("rateRange").value;
  const pitch=document.getElementById("pitchRange").value;
  if(!text) return alert("Digite um texto");
  const btn=document.getElementById("btnGenerate");
  const spinner=document.getElementById("genSpinner"), icon=document.getElementById("genIcon");
  btn.disabled=true; spinner.classList.remove("hidden"); icon.classList.add("hidden");
  try{
    const res = await api("/api/generate",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({text, voice, engine: currentEngine, rate: `${rate>0?'+':''}${rate}%`, pitch: `${pitch>0?'+':''}${pitch}Hz`, format})});
    const out=document.getElementById("genOutput");
    const audio=document.getElementById("genAudio");
    out.classList.remove("hidden");
    audio.src=`/api/audio/${res.id}`;
    audio.play();
    document.getElementById("genMeta").textContent=`• ${res.id} • ${res.duration}s • ${res.engine}`;
    document.getElementById("genDownload").href=`/api/audio/${res.id}`;
    document.getElementById("genDownload").download=`${res.id}.wav`;
    loadHistory();
  }catch(e){ alert("Erro: "+e.message); }
  finally{ btn.disabled=false; spinner.classList.add("hidden"); icon.classList.remove("hidden"); }
});

// Preview voice (sintetiza amostra curta)
async function previewVoice(){
  const voice=document.getElementById("voiceSelect").value;
  const samples={"pt-BR-FranciscaNeural":"Olá, eu sou a Francisca, sua voz de demonstração.","pt-BR-AntonioNeural":"Olá, eu sou o Antônio, pronto para narrar.","en-US-JennyNeural":"Hello, I'm Jenny, your demo voice."};
  const text=samples[voice]||"Olá, preview de voz do VoiceStudio Arena.";
  document.getElementById("ttsText").value=text;
  document.getElementById("btnGenerate").click();
}
document.getElementById("previewVoice")?.addEventListener("click", previewVoice);

// Char count
document.getElementById("ttsText")?.addEventListener("input", e=>{document.getElementById("charCount").textContent=e.target.value.length});

// Sample buttons
document.querySelectorAll(".sample-btn").forEach(b=>b.addEventListener("click",()=>{
  document.getElementById("ttsText").value=b.dataset.sample;
  document.getElementById("ttsText").dispatchEvent(new Event("input"));
}));

// Clone toggle
document.getElementById("openClone")?.addEventListener("click",()=>{
  document.getElementById("cloneForm").classList.toggle("hidden");
});
document.getElementById("doClone")?.addEventListener("click", async ()=>{
  const name=document.getElementById("cloneName").value.trim();
  if(!name) return alert("Dê um nome à voz");
  const fd=new FormData();
  fd.append("name", name);
  fd.append("language", document.getElementById("cloneLang").value);
  fd.append("gender", document.getElementById("cloneGender").value);
  fd.append("engine", currentEngine);
  const file=document.getElementById("cloneFile").files[0];
  if(file) fd.append("sample", file);
  const start=document.getElementById("cloneStart").value;
  const duration=document.getElementById("cloneDuration").value;
  if(start) fd.append("start", start);
  if(duration) fd.append("duration", duration);
  const box=document.getElementById("cloneQuality");
  try{
    const v= await fetch("/api/voices/clone",{method:"POST", body:fd}).then(r=>r.json());
    if(v.detail) throw new Error(v.detail);
    if(v.quality){
      const q=v.quality;
      box.classList.remove("hidden");
      box.innerHTML=`🎧 Amostra: ${q.duration}s, pico ${q.peak_db} dB, RMS ${q.rms_db} dB${q.warnings&&q.warnings.length?`<br><span class="text-amber-300">⚠️ ${q.warnings.join("<br>⚠️ ")}</span>`:""}`;
    }
    alert(`Voz clonada: ${v.name} (${v.id})`);
    await loadVoices();
    document.getElementById("voiceSelect").value=v.id;
  }catch(e){alert(e.message)}
});
document.getElementById("rateRange")?.addEventListener("input", e=>{document.getElementById("rateVal").textContent=`${e.target.value>0?'+':''}${e.target.value}%`});
document.getElementById("pitchRange")?.addEventListener("input", e=>{document.getElementById("pitchVal").textContent=`${e.target.value>0?'+':''}${e.target.value}Hz`});

// Voice Design
document.getElementById("btnDesign")?.addEventListener("click", async ()=>{
  const name=document.getElementById("designName").value.trim();
  const prompt=document.getElementById("designPrompt").value.trim();
  if(!name||!prompt) return alert("Preencha nome e prompt");
  const res=await api("/api/voices/design",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({name, prompt, language: document.getElementById("designLang").value, gender: document.getElementById("designGender").value})});
  document.getElementById("designResult").classList.remove("hidden");
  document.getElementById("designResult").textContent=`✅ Voz criada: ${res.name} (${res.id}) — pronta para uso em Clonar & Gerar.`;
  await loadVoices();
});

// Dub
document.getElementById("dubFile")?.addEventListener("change", e=>{
  document.getElementById("dubFileName").textContent=e.target.files[0]?.name||"";
});
document.getElementById("btnDub")?.addEventListener("click", async ()=>{
  const file=document.getElementById("dubFile").files[0];
  const text=document.getElementById("dubText").value.trim();
  if(!file && !text) return alert("Envie áudio/vídeo ou texto");
  const fd=new FormData();
  if(file) fd.append("file", file);
  if(text) fd.append("text", text);
  fd.append("source_lang", document.getElementById("dubSource").value);
  fd.append("target_lang", document.getElementById("dubTarget").value);
  fd.append("voice", document.getElementById("dubVoice").value);
  fd.append("engine", currentEngine);
  const btn=document.getElementById("btnDub"); btn.disabled=true; btn.textContent="Dublando...";
  try{
    const res=await fetch("/api/dub",{method:"POST", body:fd}).then(r=>r.json());
    const out=document.getElementById("dubOutput");
    out.classList.remove("hidden");
    out.innerHTML=`
      <div class="p-4 rounded-xl bg-ink border border-white/10">
        <div class="text-xs font-bold text-muted uppercase mb-2">Original (${res.source_lang})</div><div class="text-sm">${res.original_text||"(do áudio)"}</div>
        <div class="text-xs font-bold text-muted uppercase mt-3 mb-2">Traduzido (${res.target_lang})</div><div class="text-sm">${res.translated_text}</div>
        <audio controls class="w-full mt-3" src="/api/audio/${res.audio.id}"></audio>
        <a href="/api/audio/${res.audio.id}" download class="inline-block mt-2 text-xs px-3 py-1.5 rounded-full bg-white text-ink font-bold">↓ Baixar dublado</a>
      </div>`;
  }catch(e){alert(e.message)} finally{btn.disabled=false; btn.textContent="🌐 Dublar agora"}
});

// Transcribe
document.getElementById("sttFile")?.addEventListener("change", e=>{
  document.getElementById("sttFileName").textContent=e.target.files[0]?.name||"";
});
document.getElementById("btnTranscribe")?.addEventListener("click", async ()=>{
  const file=document.getElementById("sttFile").files[0];
  if(!file) return alert("Envie um áudio");
  const fd=new FormData();
  fd.append("file", file);
  fd.append("language", document.getElementById("sttLang").value);
  fd.append("diarize", document.getElementById("sttDiarize").checked);
  const btn=document.getElementById("btnTranscribe"); btn.disabled=true; btn.textContent="Transcrevendo...";
  try{
    const res=await fetch("/api/transcribe",{method:"POST", body:fd}).then(r=>r.json());
    const out=document.getElementById("sttOutput"); out.classList.remove("hidden");
    let html=`<div class="font-bold mb-2">Transcrição (${res.language||'auto'}) — engine: ${res.engine}</div><div class="mb-3">${res.text}</div>`;
    if(res.segments) html+=`<div class="text-xs text-muted">Segments:</div><div class="space-y-1 font-mono text-xs">${res.segments.map(s=>`<div><span class="text-accent">${s.start.toFixed(1)}s</span> ${s.text}</div>`).join("")}</div>`;
    if(res.diarization) html+=`<div class="mt-3 text-xs"><div class="font-bold">Diarização:</div>${res.diarization.map(d=>`<div><b>${d.speaker}</b> ${d.start.toFixed(1)}-${d.end.toFixed(1)}s: ${d.text}</div>`).join("")}</div>`;
    out.innerHTML=html;
  }catch(e){alert(e.message)} finally{btn.disabled=false; btn.textContent="Transcrever"}
});

// Audiobook
document.getElementById("bookPdf")?.addEventListener("change", async e=>{
  const file=e.target.files[0];
  if(!file) return;
  alert("PDF selecionado — ao criar, enviaremos o PDF direto para /api/audiobook/pdf");
});
document.getElementById("btnAudiobook")?.addEventListener("click", async ()=>{
  const text=document.getElementById("bookText").value.trim();
  const file=document.getElementById("bookPdf").files[0];
  if(!text && !file) return alert("Cole texto ou envie PDF");
  const btn=document.getElementById("btnAudiobook"); btn.disabled=true; btn.textContent="Gerando... (pode levar 1-2 min)";
  try{
    let res;
    if(file){
      const fd=new FormData(); fd.append("file", file); fd.append("voice", document.getElementById("bookVoice").value); fd.append("engine", currentEngine); fd.append("title", document.getElementById("bookTitle").value);
      res=await fetch("/api/audiobook/pdf",{method:"POST", body:fd}).then(r=>r.json());
    } else {
      res=await api("/api/audiobook",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({text, voice: document.getElementById("bookVoice").value, engine: currentEngine, title: document.getElementById("bookTitle").value})});
    }
    const out=document.getElementById("bookOutput"); out.classList.remove("hidden");
    out.innerHTML=`<div class="p-4 rounded-xl bg-ink border border-success/20"><div class="font-bold">${res.title} — ${res.generated_chapters}/${res.total_chapters} capítulos</div>${res.note?`<div class="text-xs text-amber-400 mt-1">${res.note}</div>`:''}<div class="mt-3 space-y-2">${res.chapters.map(ch=>`<div class="p-3 rounded-lg bg-card border border-white/5"><div class="text-xs font-bold">${ch.title}</div><div class="text-xs text-muted truncate">${ch.text}</div><audio controls class="w-full mt-2" src="/api/audio/${ch.audio.id}"></audio></div>`).join("")}</div></div>`;
  }catch(e){alert(e.message)} finally{btn.disabled=false; btn.textContent="📚 Criar audiobook"}
});

// Dictation WS
document.getElementById("btnDictStart")?.addEventListener("click", async ()=>{
  const start=document.getElementById("btnDictStart"), stop=document.getElementById("btnDictStop");
  start.disabled=true; stop.disabled=false;
  document.getElementById("dictLive").textContent="Conectando...";
  const proto=location.protocol==="https:"?"wss":"ws";
  wsDict=new WebSocket(`${proto}://${location.host}/v1/audio/transcriptions/stream`);
  wsDict.onopen=()=>{ document.getElementById("dictLive").textContent="Ouvindo... fale agora.";
    // Tentar mic
    try{
      const stream=await navigator.mediaDevices.getUserMedia({audio:true});
      mediaRecorder=new MediaRecorder(stream);
      mediaRecorder.ondataavailable=e=>{ if(wsDict.readyState===1) wsDict.send(e.data); };
      mediaRecorder.start(500);
    }catch(e){ console.warn("Mic não disponível",e); }
  };
  wsDict.onmessage=e=>{
    try{
      const d=JSON.parse(e.data);
      if(d.type==="partial") document.getElementById("dictLive").textContent=d.text;
      if(d.type==="final"){ document.getElementById("dictFinal").classList.remove("hidden"); document.getElementById("dictFinal").textContent="✅ Final: "+d.text; }
    }catch{}
  };
  wsDict.onclose=()=>{ document.getElementById("dictLive").textContent="Desconectado."; start.disabled=false; stop.disabled=true; };
});
document.getElementById("btnDictStop")?.addEventListener("click", ()=>{
  if(mediaRecorder){ mediaRecorder.stop(); mediaRecorder=null; }
  if(wsDict){ wsDict.send(JSON.stringify({type:"input_audio.end"})); setTimeout(()=>wsDict.close(), 600); }
});

// HW info
fetch("/api/capabilities").then(r=>r.json()).then(c=>{
  document.getElementById("hwInfo").innerHTML=`Engines: ${Object.keys(c.engines).join(", ")} • Features: ${Object.keys(c.features).filter(k=>c.features[k]).join(", ")}`;
});

// Initial load
loadVoices(); loadEngines(); loadLanguages(); loadPresets(); loadHistory();
api("/api/health").then(h=>{document.getElementById("footerVer").textContent=`${h.product} ${h.version} • backend OK`;}).catch(()=>{document.getElementById("footerVer").textContent="backend offline? rode python backend/main.py"});
