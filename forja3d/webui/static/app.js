import * as THREE from "three";
import { STLLoader } from "/static/vendor/STLLoader.js";
import { OrbitControls } from "/static/vendor/OrbitControls.js";

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
let CAT = null, source = "model", file = null;

// ------------------------------------------------------------------ viewer
const view = $("#view");
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(window.devicePixelRatio);
view.appendChild(renderer.domElement);
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x15181c);
const camera = new THREE.PerspectiveCamera(40, 1, 0.1, 5000);
camera.up.set(0, 0, 1);
camera.position.set(220, -220, 180);
const controls = new OrbitControls(camera, renderer.domElement);
scene.add(new THREE.HemisphereLight(0xffffff, 0x333344, 1.6));
const sun = new THREE.DirectionalLight(0xffffff, 1.6); sun.position.set(200, -150, 300); scene.add(sun);
let bed = null, part = null;

function drawBed(vol) {
  if (bed) scene.remove(bed);
  const [x, y] = vol || [256, 256];
  bed = new THREE.Group();
  const plate = new THREE.Mesh(new THREE.PlaneGeometry(x, y), new THREE.MeshStandardMaterial({ color: 0x2a2f36 }));
  bed.add(plate);
  const grid = new THREE.GridHelper(Math.max(x, y), Math.round(Math.max(x, y) / 10), 0x3b424b, 0x30363d);
  grid.rotation.x = Math.PI / 2; grid.position.z = 0.05; bed.add(grid);
  scene.add(bed);
}
function resize() {
  const w = view.clientWidth, h = view.clientHeight;
  renderer.setSize(w, h); camera.aspect = w / Math.max(h, 1); camera.updateProjectionMatrix();
}
new ResizeObserver(resize).observe(view);
(function loop() { requestAnimationFrame(loop); controls.update(); renderer.render(scene, camera); })();

function showMesh(buffer, centerOnBed) {
  if (part) scene.remove(part);
  const geo = new STLLoader().parse(buffer);
  geo.computeVertexNormals();
  geo.computeBoundingBox();
  const bb = geo.boundingBox;
  if (centerOnBed) {
    geo.translate(-(bb.min.x + bb.max.x) / 2, -(bb.min.y + bb.max.y) / 2, -bb.min.z);
    geo.computeBoundingBox();
  }
  part = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ color: 0xff7a1a, roughness: 0.55, metalness: 0.05 }));
  scene.add(part);
  const s = new THREE.Vector3(); geo.boundingBox.getSize(s);
  const r = Math.max(s.x, s.y, s.z, 20);
  controls.target.set(0, 0, s.z / 2);
  camera.position.set(r * 1.6, -r * 1.6, r * 1.3);
  $("#dims").textContent = `${s.x.toFixed(1)} × ${s.y.toFixed(1)} × ${s.z.toFixed(1)} mm`;
}

// ------------------------------------------------------------------ catalog / form
async function api(path, opts) {
  const r = await fetch(path, opts);
  const d = await r.json();
  if (!r.ok || d.error) throw new Error(d.error || r.statusText);
  return d;
}
const saved = JSON.parse(localStorage.getItem("forja3d") || "{}");

async function init() {
  CAT = await api("/api/catalog");
  $("#version").textContent = "v" + CAT.version;
  const sel = $("#printer");
  for (const [id, p] of Object.entries(CAT.printers)) sel.add(new Option(`${p.name} (${p.technology.toUpperCase()})`, id));
  sel.value = saved.printer && CAT.printers[saved.printer] ? saved.printer : "bambu_a1";
  sel.onchange = () => { fillMaterials(); persist(); };
  fillMaterials();
  if (saved.material && CAT.materials[saved.material]?.technology === tech()) $("#material").value = saved.material;
  if (saved.layer) $("#layer").value = saved.layer;
  if (saved.nozzle) $("#nozzle").value = saved.nozzle;
  for (const id of ["material", "layer", "nozzle"]) $("#" + id).onchange = persist;
  renderEngines();
  api("/api/update").then((u) => {
    if (!u.update_available) return;
    const a = $("#update");
    a.hidden = false; a.href = u.url;
    a.textContent = `Versiune nouă: ${u.latest} ↗`;
    a.title = u.notes || "";
  }).catch(() => {});
}
const tech = () => CAT.printers[$("#printer").value].technology;
function fillMaterials() {
  const p = CAT.printers[$("#printer").value];
  const sel = $("#material"); sel.innerHTML = "";
  for (const [id, m] of Object.entries(CAT.materials)) if (m.technology === p.technology) sel.add(new Option(m.name, id));
  $$(".fdm-only").forEach((e) => (e.style.display = p.technology === "fdm" ? "" : "none"));
  if (p.technology === "resin") $("#layer").value = 0.05;
  else if (+$("#layer").value < 0.08) $("#layer").value = 0.2;
  drawBed(p.volume_mm);
}
function persist() {
  localStorage.setItem("forja3d", JSON.stringify({ printer: $("#printer").value, material: $("#material").value,
    layer: $("#layer").value, nozzle: $("#nozzle").value }));
}

$$(".segbtn").forEach((b) => (b.onclick = () => {
  $$(".segbtn").forEach((x) => x.classList.toggle("active", x === b));
  source = b.dataset.src; file = null; $("#go").disabled = true;
  const inp = $("#file");
  if (source === "image") {
    inp.accept = ".png,.jpg,.jpeg,.webp";
    $("#dropText").innerHTML = "Trage aici o poză a obiectului<br><small>fundal simplu, obiectul întreg în cadru</small>";
    if (!$("#size").value) $("#size").value = 50;
  } else {
    inp.accept = ".stl,.obj,.ply,.3mf,.glb,.off";
    $("#dropText").innerHTML = "Trage aici un fișier STL / OBJ / 3MF<br><small>sau apasă ca să alegi</small>";
  }
}));

const drop = $("#drop");
drop.ondragover = (e) => { e.preventDefault(); drop.classList.add("over"); };
drop.ondragleave = () => drop.classList.remove("over");
drop.ondrop = (e) => { e.preventDefault(); drop.classList.remove("over"); pick(e.dataTransfer.files[0]); };
$("#file").onchange = (e) => pick(e.target.files[0]);

async function pick(f) {
  if (!f) return;
  file = f; $("#go").disabled = false;
  $("#dropText").innerHTML = `<b>${esc(f.name)}</b><br><small>${(f.size / 1048576).toFixed(1)} MB</small>`;
  if (!$("#name").value) $("#name").placeholder = f.name.replace(/\.[^.]+$/, "");
  if (source === "model" && f.name.toLowerCase().endsWith(".stl")) {
    try { showMesh(await f.arrayBuffer(), true); } catch { /* preview optional */ }
  }
}

$("#go").onclick = async () => {
  if (!file) return;
  const q = new URLSearchParams({ filename: file.name, printer: $("#printer").value, material: $("#material").value,
    layer: $("#layer").value, nozzle: $("#nozzle").value, size: $("#size").value, name: $("#name").value });
  $("#go").disabled = true;
  $("#status").textContent = source === "image"
    ? "Generez modelul 3D cu AI... pe procesor poate dura câteva minute." : "Repar, orientez și calculez setările...";
  try {
    const r = await api(`/api/${source === "image" ? "generate" : "prepare"}?${q}`, { method: "POST", body: file });
    const stl = await fetch(`/api/file?job=${r.job_id}`).then((x) => x.arrayBuffer());
    showMesh(stl, false);
    renderResult(r);
    $("#status").textContent = "";
  } catch (e) {
    $("#status").innerHTML = `<span style="color:var(--bad)">Eroare: ${esc(e.message)}</span>`;
  } finally { $("#go").disabled = false; }
};

// ------------------------------------------------------------------ results
function fmt(v) { return typeof v === "boolean" ? (v ? "da" : "nu") : v; }

function renderResult(r) {
  const rec = r.recommendation, a = r.analysis, L = CAT.labels;
  const learned = new Set(rec.reasons.filter((x) => x.includes("invatat")).map((x) => x.split(":")[0]));
  let h = `<h2>${esc(r.name)} <span class="muted">· job #${r.job_id}</span></h2>
    <div class="muted">${a.dims_mm.join(" × ")} mm · ${a.volume_cm3 ?? "?"} cm³ · console ${(a.overhang_frac * 100).toFixed(1)}%
    ${a.min_wall_mm ? ` · perete min ~${a.min_wall_mm} mm` : ""}</div>`;
  if (r.repair.removed_fragments || r.repair.holes_filled)
    h += `<div class="reason">🔧 Reparat: ${r.repair.removed_fragments} fragmente șterse${r.repair.holes_filled ? ", găuri umplute" : ""}.</div>`;
  for (const w of [...rec.warnings, ...(r.repair.notes || [])]) h += `<div class="warn">${esc(w)}</div>`;
  h += `<h3>Setări recomandate</h3><table>`;
  for (const [k, v] of Object.entries(rec.settings)) {
    if (k === "nozzle") continue;
    const [name, unit] = L[k] || [k, ""];
    h += `<tr><td>${esc(name)}</td><td class="v ${learned.has(name) ? "changed" : ""}">${esc(fmt(v))} ${typeof v === "boolean" ? "" : esc(unit)}</td></tr>`;
  }
  h += `</table>`;
  if (rec.reasons.length) h += `<h3>De ce</h3>` + rec.reasons.map((x) => `<div class="reason">• ${esc(x)}</div>`).join("");
  if (rec.learned_from.length)
    h += `<div class="reason">🧠 Am folosit ${rec.learned_from.length} print(uri) anterioare similare.</div>`;
  h += `<h3>Fișiere</h3><div class="files">` + r.files.map((f) => {
    const n = f.split(/[\\/]/).pop();
    return `<a href="/api/file?job=${r.job_id}&name=${encodeURIComponent(n)}&download=1">⬇ ${esc(n)}</a>`;
  }).join("") + `</div><div class="muted" style="font-size:12px">În Bambu Studio / OrcaSlicer: File → Import → Import Configs… și alege fișierele .json.<br>Folder: ${esc(r.output_dir)}</div>`;
  const box = $("#result"); box.innerHTML = h;
  box.appendChild(feedbackForm(r.job_id, CAT.printers[rec.printer].technology, rec.settings));
}

function feedbackForm(jobId, techName, settings, onDone) {
  const el = $("#feedbackTpl").content.firstElementChild.cloneNode(true);
  let outcome = null; const issues = new Set();
  $$(".outcomes button", el).forEach((b) => (b.onclick = () => {
    outcome = b.dataset.o; $$(".outcomes button", el).forEach((x) => x.classList.toggle("sel", x === b));
  }));
  for (const [k, label] of Object.entries(CAT.issues[techName] || {})) {
    const c = document.createElement("button"); c.className = "chip"; c.textContent = label;
    c.onclick = () => { issues.has(k) ? issues.delete(k) : issues.add(k); c.classList.toggle("sel"); };
    $(".issues", el).appendChild(c);
  }
  const act = $(".actual", el);
  for (const [k, v] of Object.entries(settings || {})) {
    if (typeof v !== "number" || k === "nozzle" || k === "layer_height") continue;
    act.insertAdjacentHTML("beforeend", `<span>${esc((CAT.labels[k] || [k])[0])}</span><input type="number" step="any" data-k="${k}" placeholder="${v}">`);
  }
  $(".send", el).onclick = async () => {
    if (!outcome) { $(".fbmsg", el).textContent = "Alege mai întâi rezultatul."; return; }
    const actual = {};
    $$("input[data-k]", el).forEach((i) => { if (i.value !== "") actual[i.dataset.k] = +i.value; });
    try {
      await api("/api/feedback", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_id: jobId, outcome, issues: [...issues], rating: +$(".rating", el).value,
          notes: $(".notes", el).value, actual }) });
      $(".fbmsg", el).textContent = "Mulțumesc! Data viitoare țin cont de asta. 🧠";
      onDone && onDone();
    } catch (e) { $(".fbmsg", el).textContent = "Eroare: " + e.message; }
  };
  return el;
}

// ------------------------------------------------------------------ history
const OUT = { ok: "Reușit", partial: "Cu probleme", fail: "Eșuat" };
async function renderHistory() {
  const d = await api("/api/history");
  const s = d.stats;
  $("#stats").innerHTML = [["Proiecte", s.projects], ["Joburi", s.jobs], ["Cu feedback", s.with_feedback],
    ["Reușite", s.ok], ["Eșuate", s.fail]].map(([k, v]) => `<div class="stat"><b>${v}</b>${k}</div>`).join("");
  const tb = $("#histTable tbody"); tb.innerHTML = "";
  for (const j of d.jobs) {
    const tr = document.createElement("tr");
    const res = j.outcome ? `<span class="badge ${j.outcome}">${OUT[j.outcome]}</span> ${j.issues.map((i) =>
      esc(CAT.issues[CAT.materials[j.material_id]?.technology]?.[i] || i)).join(", ")}` : `<span class="badge none">fără feedback</span>`;
    tr.innerHTML = `<td>${j.id}</td><td>${esc(j.project_name)}</td><td>${esc(CAT.printers[j.printer_id]?.name || j.printer_id)}</td>
      <td>${esc(CAT.materials[j.material_id]?.name || j.material_id)}</td><td>${res}</td>
      <td>${j.outcome ? "" : '<button class="chip">Dă feedback</button>'}</td>`;
    const btn = $("button", tr);
    if (btn) btn.onclick = () => {
      const m = document.createElement("div"); m.className = "modal";
      const inner = document.createElement("div"); inner.className = "panel"; m.appendChild(inner);
      inner.innerHTML = `<h2>${esc(j.project_name)} · job #${j.id}</h2>`;
      inner.appendChild(feedbackForm(j.id, CAT.materials[j.material_id].technology, j.settings,
        () => setTimeout(() => { m.remove(); renderHistory(); }, 700)));
      m.onclick = (e) => { if (e.target === m) m.remove(); };
      document.body.appendChild(m);
    };
    tb.appendChild(tr);
  }
}

// ------------------------------------------------------------------ engines
function renderEngines() {
  const box = $("#engines");
  box.innerHTML = `<h2>Motoare AI (poză → 3D)</h2><p class="muted">Se instalează separat ca aplicația de bază să rămână mică.
    Modelele rulează local, pe calculatorul tău. Datele: ${esc(CAT.data_dir)}</p>`;
  for (const [k, e] of Object.entries(CAT.engines)) {
    const d = document.createElement("div"); d.className = "stat"; d.style.marginBottom = "10px";
    d.innerHTML = `<b>${esc(e.name)}</b> <span class="muted">licență ${esc(e.license)}</span><p>${esc(e.info)}</p>
      ${e.installed ? '<span class="badge ok">instalat</span>' : `<button class="primary">Instalează ${esc(e.name)}</button>`}
      <pre class="muted log" style="white-space:pre-wrap"></pre>`;
    const b = $("button", d);
    if (b) b.onclick = async () => {
      b.disabled = true; $(".log", d).textContent = "Se instalează (poate dura 5-15 minute)...";
      try { const r = await api(`/api/engine/install?name=${k}`, { method: "POST" }); $(".log", d).textContent = r.log.join("\n"); }
      catch (err) { $(".log", d).textContent = "Eroare: " + err.message; b.disabled = false; }
    };
    box.appendChild(d);
  }
}

$$(".tab").forEach((t) => (t.onclick = () => {
  $$(".tab").forEach((x) => x.classList.toggle("active", x === t));
  $$(".tabpage").forEach((p) => p.classList.toggle("active", p.id === "tab-" + t.dataset.tab));
  if (t.dataset.tab === "history") renderHistory();
  if (t.dataset.tab === "work") resize();
}));

init().catch((e) => ($("#status").textContent = "Eroare la pornire: " + e.message));
