// RoadSense frontend: plain JS, talks to the FastAPI backend on the same origin.
// Flow: load provinces -> user picks one -> GET /conditions -> render summary, map, table.

const BAND_COLOR = { good: "#0ca30c", fair: "#fab219", poor: "#ec835a", hazardous: "#d03b3b", unknown: "#9a9a97" };

const $ = (id) => document.getElementById(id);
const fmt = (v, d = 1) => (v === null || v === undefined ? "–" : Number(v).toFixed(d));

// --- map ---
const map = L.map("map").setView([64.5, 26.0], 5); // Finland
L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 18, attribution: "&copy; OpenStreetMap contributors",
}).addTo(map);
const markers = L.layerGroup().addTo(map);

// --- data ---
async function getJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url} -> HTTP ${r.status}`);
  return r.json();
}

async function loadProvinces() {
  const provinces = await getJSON("/provinces");
  const sel = $("province");
  sel.innerHTML = '<option value="">All Finland</option>' +
    provinces.map((p) => `<option value="${p}">${p}</option>`).join("");
  // Remember the last choice per browser - a convenience, not state.
  try { sel.value = localStorage.getItem("province") || ""; } catch (_) {}
}

async function loadConditions() {
  const province = $("province").value;
  try { localStorage.setItem("province", province); } catch (_) {}
  $("status").textContent = "Loading…";
  const url = province ? `/conditions?province=${encodeURIComponent(province)}` : "/conditions";
  try {
    render(await getJSON(url));
    $("status").textContent = "";
  } catch (e) {
    $("status").textContent = `Error: ${e.message}`;
  }
}

// --- rendering ---
function bandTag(index) {
  const score = index.score === null ? "–" : index.score;
  return `<span class="band ${index.band}">${score} ${index.band}</span>`;
}

function whyText(index) {
  if (index.score === null) return "no surface data";
  if (!index.factors.length) return "no penalties";
  return index.factors.map((f) => `${f.name.replaceAll("_", " ")} −${f.penalty} (${f.detail})`).join(", ");
}

function render(data) {
  const rows = [...data.stations].sort((a, b) => (a.index.score ?? 101) - (b.index.score ?? 101));

  // summary tiles
  const scored = rows.filter((r) => r.index.score !== null);
  const latest = rows.map((r) => r.latest?.measured_at).filter(Boolean).sort().at(-1);
  $("s-count").textContent = data.station_count;
  $("s-avg").textContent = data.average_score ?? "–";
  $("s-worst").innerHTML = scored.length ? bandTag(scored[0].index) : "–";
  $("s-updated").textContent = latest ? new Date(latest).toLocaleTimeString("fi-FI", { hour: "2-digit", minute: "2-digit" }) : "–";
  $("summary").hidden = false;

  // table
  $("stations").querySelector("tbody").innerHTML = rows.map((r) => `
    <tr>
      <td>${r.station.name}</td>
      <td>${r.station.municipality ?? ""}</td>
      <td>${bandTag(r.index)}</td>
      <td>${r.latest?.road_condition ?? "–"}</td>
      <td class="num">${fmt(r.latest?.air_temp_c)}</td>
      <td class="num">${fmt(r.latest?.road_temp_c)}</td>
      <td class="why">${whyText(r.index)}</td>
    </tr>`).join("");

  // map markers (>= 8px, white ring so overlapping marks stay separable)
  markers.clearLayers();
  const bounds = [];
  for (const r of rows) {
    const { lat, lon } = r.station;
    bounds.push([lat, lon]);
    L.circleMarker([lat, lon], {
      radius: 7, color: "#fff", weight: 2, fillColor: BAND_COLOR[r.index.band], fillOpacity: 0.95,
    }).bindPopup(`<b>${r.station.name}</b><br>${bandTag(r.index)}<br>
      ${r.latest?.road_condition ?? "–"}, air ${fmt(r.latest?.air_temp_c)} °C, road ${fmt(r.latest?.road_temp_c)} °C<br>
      <span class="why">${whyText(r.index)}</span>`).addTo(markers);
  }
  if (bounds.length) map.fitBounds(bounds, { padding: [20, 20], maxZoom: 9 });
}

// --- wire up ---
$("province").addEventListener("change", loadConditions);
$("refresh").addEventListener("click", loadConditions);
$("docs-link").href = "/docs";
loadProvinces().then(loadConditions).catch((e) => ($("status").textContent = `Error: ${e.message}`));
