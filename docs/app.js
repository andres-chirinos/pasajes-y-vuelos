// Dynamic Dashboard Engine for Bolivian Transport Interconnectivity
// MEFP Datalake Analytics Node

let rawData = { pasajes: [], fids: [], metadata: {} };
let filteredPasajes = [];
let filteredFids = [];

// Geographic coordinates map for Bolivian & international connection nodes
const CITY_COORDS = {
  "LA PAZ": { lat: -16.500, lng: -68.150, type: "AIRPORT_CITY", label: "La Paz (El Alto)" },
  "EL ALTO": { lat: -16.510, lng: -68.190, type: "AIRPORT_CITY", label: "El Alto (LPB)" },
  "SANTA CRUZ": { lat: -17.800, lng: -63.180, type: "AIRPORT_CITY", label: "Santa Cruz (VVI)" },
  "COCHABAMBA": { lat: -17.389, lng: -66.160, type: "AIRPORT_CITY", label: "Cochabamba (CBB)" },
  "SUCRE": { lat: -19.033, lng: -65.262, type: "AIRPORT_CITY", label: "Sucre (SRE)" },
  "TARIJA": { lat: -21.535, lng: -64.729, type: "AIRPORT_CITY", label: "Tarija (TJA)" },
  "ORURO": { lat: -17.964, lng: -67.106, type: "CITY", label: "Oruro" },
  "POTOSI": { lat: -19.583, lng: -65.753, type: "CITY", label: "Potosí" },
  "TRINIDAD": { lat: -14.833, lng: -64.900, type: "AIRPORT_CITY", label: "Trinidad (TDD)" },
  "COBIJA": { lat: -11.026, lng: -68.769, type: "AIRPORT_CITY", label: "Cobija (CIJ)" },
  "UYUNI": { lat: -20.459, lng: -66.825, type: "AIRPORT_CITY", label: "Uyuni (UYU)" },
  "RIBERALTA": { lat: -11.006, lng: -66.064, type: "AIRPORT_CITY", label: "Riberalta (RIB)" },
  "GUAYARAMERIN": { lat: -10.836, lng: -65.357, type: "AIRPORT_CITY", label: "Guayaramerín (GYA)" },
  "YACUIBA": { lat: -22.016, lng: -63.677, type: "CITY", label: "Yacuiba" },
  "VILLAZON": { lat: -22.091, lng: -65.596, type: "CITY", label: "Villazón" },
  "PUERTO QUIJARRO": { lat: -19.000, lng: -57.716, type: "CITY", label: "Puerto Quijarro" },
  "CAMARGO": { lat: -20.640, lng: -65.200, type: "CITY", label: "Camargo" },
  "DESAGUADERO": { lat: -16.566, lng: -69.041, type: "CITY", label: "Desaguadero" },
  "BUENOS AIRES": { lat: -34.603, lng: -58.381, type: "INTL", label: "Buenos Aires (EZE)" },
  "SAO PAULO": { lat: -23.550, lng: -46.633, type: "INTL", label: "São Paulo (GRU)" },
  "LIMA": { lat: -12.046, lng: -77.042, type: "INTL", label: "Lima (LIM)" },
  "CUIABA": { lat: -15.601, lng: -56.097, type: "INTL", label: "Cuiabá" }
};

let chartTimeline = null;
let chartPrices = null;
let chartCarriers = null;
let animFrameId = null;
let activeNodeHover = null;

// Initialize Application
document.addEventListener("DOMContentLoaded", () => {
  initTabNavigation();
  initFilterEvents();
  loadData();
});

// Tab Switcher Logic
function initTabNavigation() {
  const btns = document.querySelectorAll(".segmented-btn");
  btns.forEach(btn => {
    btn.addEventListener("click", () => {
      btns.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      
      const tabId = btn.getAttribute("data-tab");
      document.querySelectorAll(".tab-content").forEach(content => {
        content.style.display = content.id === tabId ? "block" : "none";
      });

      if (tabId === "tab-network") {
        setTimeout(renderNetworkGraph, 100);
      }
    });
  });
}

// Filter Event Listeners
function initFilterEvents() {
  document.getElementById("date-filter").addEventListener("change", applyFilters);
  document.getElementById("transport-filter").addEventListener("change", applyFilters);
  document.getElementById("origin-filter").addEventListener("change", applyFilters);
  
  document.getElementById("fids-search")?.addEventListener("input", renderFidsTable);
  document.getElementById("pasajes-search")?.addEventListener("input", renderPasajesTable);
}

// Load Dataset
async function loadData() {
  try {
    const res = await fetch("data_dashboard.json");
    if (!res.ok) throw new Error("HTTP error " + res.status);
    rawData = await res.json();
  } catch (err) {
    console.warn("Could not load data_dashboard.json, attempting fallback parse", err);
  }

  if (rawData.metadata && rawData.metadata.generated_at) {
    document.getElementById("data-updated-label").textContent = `Actualizado: ${rawData.metadata.generated_at}`;
  } else {
    document.getElementById("data-updated-label").textContent = "En Vivo (Datalake)";
  }

  populateFilterOptions();
  applyFilters();
}

// Populate Filter Options
function populateFilterOptions() {
  const dateSelect = document.getElementById("date-filter");
  const originSelect = document.getElementById("origin-filter");

  const dates = new Set();
  const origins = new Set();

  (rawData.pasajes || []).forEach(p => {
    if (p.fecha_salida) dates.add(p.fecha_salida);
    if (p.origen_nombre) origins.add(p.origen_nombre.toUpperCase());
  });

  (rawData.fids || []).forEach(f => {
    if (f.FECHA) {
      const d = f.FECHA.split(" ")[0];
      if (d) dates.add(d);
    }
    if (f.AEROPUERTO) origins.add(f.AEROPUERTO.toUpperCase());
  });

  // Dates dropdown
  dateSelect.innerHTML = '<option value="ALL">Todas las Fechas</option>';
  Array.from(dates).sort().forEach(d => {
    const opt = document.createElement("option");
    opt.value = d;
    opt.textContent = d;
    dateSelect.appendChild(opt);
  });

  // Origin dropdown
  originSelect.innerHTML = '<option value="ALL">Todos los Orígenes</option>';
  Array.from(origins).sort().forEach(o => {
    const opt = document.createElement("option");
    opt.value = o;
    opt.textContent = o;
    originSelect.appendChild(opt);
  });
}

// Apply Filters
function applyFilters() {
  const selectedDate = document.getElementById("date-filter").value;
  const selectedTransport = document.getElementById("transport-filter").value;
  const selectedOrigin = document.getElementById("origin-filter").value;

  // Filter pasajes
  filteredPasajes = (rawData.pasajes || []).filter(p => {
    const matchDate = selectedDate === "ALL" || p.fecha_salida === selectedDate;
    const matchTransport = selectedTransport === "ALL" || p.tipo_transporte === selectedTransport;
    const matchOrigin = selectedOrigin === "ALL" || (p.origen_nombre && p.origen_nombre.toUpperCase().includes(selectedOrigin));
    return matchDate && matchTransport && matchOrigin;
  });

  // Filter FIDS
  filteredFids = (rawData.fids || []).filter(f => {
    const fDate = f.FECHA ? f.FECHA.split(" ")[0] : "";
    const matchDate = selectedDate === "ALL" || fDate === selectedDate;
    const matchTransport = selectedTransport === "ALL" || selectedTransport === "VUELO";
    const matchOrigin = selectedOrigin === "ALL" || (f.AEROPUERTO && f.AEROPUERTO.toUpperCase().includes(selectedOrigin));
    return matchDate && matchTransport && matchOrigin;
  });

  updateKPIs();
  renderNetworkGraph();
  renderTopRoutes();
  renderAnalyticsCharts();
  renderFidsTable();
  renderPasajesTable();
}

// Update KPI Summary Metrics
function updateKPIs() {
  const totalOps = filteredPasajes.length + filteredFids.length;
  document.getElementById("kpi-total-ops").textContent = totalOps.toLocaleString();
  document.getElementById("kpi-fids-count").textContent = filteredFids.length.toLocaleString();

  const busRecords = filteredPasajes.filter(p => p.tipo_transporte === "BUS");
  const flightPasajes = filteredPasajes.filter(p => p.tipo_transporte === "VUELO");
  
  document.getElementById("kpi-bus-count").textContent = busRecords.length.toLocaleString();

  // Average flight price
  const flightPrices = flightPasajes.map(p => parseFloat(p.precio_bob) || 0).filter(v => v > 0);
  const avgFlightPrice = flightPrices.length > 0 ? (flightPrices.reduce((a, b) => a + b, 0) / flightPrices.length) : 0;
  document.getElementById("kpi-avg-flight-price").textContent = `Bs. ${avgFlightPrice.toFixed(0)}`;

  // Average bus price
  const busPrices = busRecords.map(p => parseFloat(p.precio_bob) || 0).filter(v => v > 0);
  const avgBusPrice = busPrices.length > 0 ? (busPrices.reduce((a, b) => a + b, 0) / busPrices.length) : 0;
  document.getElementById("kpi-avg-bus-price").textContent = `Bs. ${avgBusPrice.toFixed(0)}`;
}

// Render Top Routes Table
function renderTopRoutes() {
  const routeMap = {};
  filteredPasajes.forEach(p => {
    const orig = (p.origen_nombre || p.origen_codigo || "N/A").toUpperCase();
    const dest = (p.destino_nombre || p.destino_codigo || "N/A").toUpperCase();
    const key = `${orig} -> ${dest} [${p.tipo_transporte}]`;
    if (!routeMap[key]) {
      routeMap[key] = { orig, dest, type: p.tipo_transporte, count: 0, prices: [] };
    }
    routeMap[key].count++;
    const price = parseFloat(p.precio_bob);
    if (price > 0) routeMap[key].prices.push(price);
  });

  const sortedRoutes = Object.values(routeMap).sort((a, b) => b.count - a.count).slice(0, 8);
  const tbody = document.getElementById("top-routes-tbody");
  tbody.innerHTML = "";

  if (sortedRoutes.length === 0) {
    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;">No hay rutas registradas</td></tr>';
    return;
  }

  sortedRoutes.forEach(r => {
    const avgP = r.prices.length ? (r.prices.reduce((a, b) => a + b, 0) / r.prices.length).toFixed(0) : "N/D";
    const badgeClass = r.type === "VUELO" ? "badge-vuelo" : "badge-bus";
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><strong>${r.orig}</strong></td>
      <td><strong>${r.dest}</strong></td>
      <td><span class="badge ${badgeClass}">${r.type}</span></td>
      <td>${r.count}</td>
      <td><span class="price-tag">Bs. ${avgP}</span></td>
    `;
    tbody.appendChild(tr);
  });
}

// Interactive Network Graph Canvas Renderer
function renderNetworkGraph() {
  const canvas = document.getElementById("network-canvas");
  if (!canvas) return;
  const container = canvas.parentElement;
  
  canvas.width = container.clientWidth;
  canvas.height = container.clientHeight;
  const ctx = canvas.getContext("2d");

  // Calculate geo bounding box for Bolivia canvas projection
  const minLat = -23.5, maxLat = -9.5;
  const minLng = -70.0, maxLng = -57.0;

  function project(lat, lng) {
    const x = ((lng - minLng) / (maxLng - minLng)) * (canvas.width - 120) + 60;
    const y = ((maxLat - lat) / (maxLat - minLat)) * (canvas.height - 120) + 60;
    return { x, y };
  }

  // Aggregate active routes
  const routes = [];
  const activeNodes = new Set();

  filteredPasajes.forEach(p => {
    const orig = (p.origen_nombre || "").toUpperCase();
    const dest = (p.destino_nombre || "").toUpperCase();
    
    let origCoord = null;
    let destCoord = null;

    Object.keys(CITY_COORDS).forEach(c => {
      if (orig.includes(c)) origCoord = CITY_COORDS[c];
      if (dest.includes(c)) destCoord = CITY_COORDS[c];
    });

    if (origCoord && destCoord) {
      routes.push({
        origCoord,
        destCoord,
        type: p.tipo_transporte,
        origName: orig,
        destName: dest
      });
      activeNodes.add(origCoord);
      activeNodes.add(destCoord);
    }
  });

  document.getElementById("nodes-count-badge").textContent = `${activeNodes.size} Ciudades / Aeropuertos`;

  let progress = 0;
  if (animFrameId) cancelAnimationFrame(animFrameId);

  function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Draw background grid effect
    ctx.strokeStyle = "rgba(255, 255, 255, 0.03)";
    ctx.lineWidth = 1;
    for (let x = 0; x < canvas.width; x += 40) {
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, canvas.height); ctx.stroke();
    }
    for (let y = 0; y < canvas.height; y += 40) {
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(canvas.width, y); ctx.stroke();
    }

    // Draw curved route arcs
    routes.forEach((r, idx) => {
      const p1 = project(r.origCoord.lat, r.origCoord.lng);
      const p2 = project(r.destCoord.lat, r.destCoord.lng);
      
      const midX = (p1.x + p2.x) / 2;
      const midY = (p1.y + p2.y) / 2 - 30; // Curve elevation

      ctx.beginPath();
      ctx.moveTo(p1.x, p1.y);
      ctx.quadraticCurveTo(midX, midY, p2.x, p2.y);

      if (r.type === "VUELO") {
        ctx.strokeStyle = "rgba(6, 182, 212, 0.35)";
        ctx.lineWidth = 1.8;
      } else {
        ctx.strokeStyle = "rgba(245, 158, 11, 0.25)";
        ctx.lineWidth = 1.2;
      }
      ctx.stroke();

      // Animated moving pulse particle along arc
      const t = (progress + idx * 0.15) % 1;
      const pulseX = (1 - t) * (1 - t) * p1.x + 2 * (1 - t) * t * midX + t * t * p2.x;
      const pulseY = (1 - t) * (1 - t) * p1.y + 2 * (1 - t) * t * midY + t * t * p2.y;

      ctx.beginPath();
      ctx.arc(pulseX, pulseY, r.type === "VUELO" ? 3.5 : 2.5, 0, Math.PI * 2);
      ctx.fillStyle = r.type === "VUELO" ? "#60a5fa" : "#fbbf24";
      ctx.shadowColor = r.type === "VUELO" ? "#3b82f6" : "#f59e0b";
      ctx.shadowBlur = 8;
      ctx.fill();
      ctx.shadowBlur = 0;
    });

    // Draw city/airport nodes
    Object.keys(CITY_COORDS).forEach(key => {
      const city = CITY_COORDS[key];
      const pos = project(city.lat, city.lng);

      ctx.beginPath();
      ctx.arc(pos.x, pos.y, 6, 0, Math.PI * 2);
      ctx.fillStyle = city.type.includes("AIRPORT") ? "#3b82f6" : "#10b981";
      ctx.fill();
      ctx.lineWidth = 2;
      ctx.strokeStyle = "#ffffff";
      ctx.stroke();

      // Label text
      ctx.font = "500 11px Inter, sans-serif";
      ctx.fillStyle = "#cbd5e1";
      ctx.fillText(city.label, pos.x + 10, pos.y + 4);
    });

    progress += 0.005;
    animFrameId = requestAnimationFrame(draw);
  }

  draw();
}

// Render Analytics Charts (Chart.js)
function renderAnalyticsCharts() {
  renderTimelineChart();
  renderPricesChart();
  renderCarriersChart();
}

function renderTimelineChart() {
  const ctx = document.getElementById("timeline-chart")?.getContext("2d");
  if (!ctx) return;

  const dateCounts = {};
  filteredPasajes.forEach(p => {
    const d = p.fecha_salida || "Desconocida";
    if (!dateCounts[d]) dateCounts[d] = { vuelo: 0, bus: 0 };
    if (p.tipo_transporte === "VUELO") dateCounts[d].vuelo++;
    else dateCounts[d].bus++;
  });

  const labels = Object.keys(dateCounts).sort();
  const vueloData = labels.map(l => dateCounts[l].vuelo);
  const busData = labels.map(l => dateCounts[l].bus);

  if (chartTimeline) chartTimeline.destroy();

  chartTimeline = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [
        { label: "Vuelos", data: vueloData, backgroundColor: "#3b82f6", borderRadius: 6 },
        { label: "Flotas Terrestres", data: busData, backgroundColor: "#f59e0b", borderRadius: 6 }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { labels: { color: "#94a3b8" } } },
      scales: {
        x: { ticks: { color: "#94a3b8" }, grid: { color: "rgba(255,255,255,0.05)" } },
        y: { ticks: { color: "#94a3b8" }, grid: { color: "rgba(255,255,255,0.05)" } }
      }
    }
  });
}

function renderPricesChart() {
  const ctx = document.getElementById("prices-chart")?.getContext("2d");
  if (!ctx) return;

  const routePrices = {};
  filteredPasajes.forEach(p => {
    const r = `${p.origen_codigo || p.origen_nombre} ➔ ${p.destino_codigo || p.destino_nombre}`;
    const price = parseFloat(p.precio_bob);
    if (price > 0) {
      if (!routePrices[r]) routePrices[r] = [];
      routePrices[r].push(price);
    }
  });

  const labels = Object.keys(routePrices).slice(0, 6);
  const avgPrices = labels.map(l => {
    const arr = routePrices[l];
    return (arr.reduce((a, b) => a + b, 0) / arr.length).toFixed(0);
  });

  if (chartPrices) chartPrices.destroy();

  chartPrices = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [{
        label: "Tarifa Promedio (BOB)",
        data: avgPrices,
        borderColor: "#10b981",
        backgroundColor: "rgba(16, 185, 129, 0.15)",
        fill: true,
        tension: 0.4
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { labels: { color: "#94a3b8" } } },
      scales: {
        x: { ticks: { color: "#94a3b8" }, grid: { color: "rgba(255,255,255,0.05)" } },
        y: { ticks: { color: "#94a3b8" }, grid: { color: "rgba(255,255,255,0.05)" } }
      }
    }
  });
}

function renderCarriersChart() {
  const ctx = document.getElementById("carriers-chart")?.getContext("2d");
  if (!ctx) return;

  const carriersMap = {};
  filteredPasajes.forEach(p => {
    const emp = (p.empresa_aerolinea || "Otra Empresa").trim();
    carriersMap[emp] = (carriersMap[emp] || 0) + 1;
  });

  const sortedCarriers = Object.entries(carriersMap).sort((a, b) => b[1] - a[1]).slice(0, 7);
  const labels = sortedCarriers.map(c => c[0]);
  const counts = sortedCarriers.map(c => c[1]);

  if (chartCarriers) chartCarriers.destroy();

  chartCarriers = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [{
        label: "Frecuencias de Operación",
        data: counts,
        backgroundColor: ["#3b82f6", "#06b6d4", "#8b5cf6", "#f59e0b", "#10b981", "#ec4899", "#64748b"],
        borderRadius: 6
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: "#94a3b8" }, grid: { color: "rgba(255,255,255,0.05)" } },
        y: { ticks: { color: "#94a3b8" }, grid: { color: "rgba(255,255,255,0.05)" } }
      }
    }
  });
}

// Render FIDS Table
function renderFidsTable() {
  const tbody = document.getElementById("fids-table-tbody");
  if (!tbody) return;

  const searchTerm = (document.getElementById("fids-search")?.value || "").toLowerCase();
  
  const records = filteredFids.filter(f => {
    const text = `${f.AEROPUERTO} ${f.NRO_VUELO} ${f.NOMBRE_AEROLINEA} ${f.RUTA0} ${f.OBSERVACION}`.toLowerCase();
    return text.includes(searchTerm);
  }).slice(0, 50);

  tbody.innerHTML = "";

  if (records.length === 0) {
    tbody.innerHTML = '<tr><td colspan="9" style="text-align:center;">No hay datos de operaciones FIDS NAABOL</td></tr>';
    return;
  }

  records.forEach(f => {
    const tr = document.createElement("tr");
    const isSalida = f.TIPO_OPERACION === "S";
    const opBadge = isSalida ? '<span class="badge badge-vuelo">SALIDA</span>' : '<span class="badge badge-bus">LLEGADA</span>';
    
    tr.innerHTML = `
      <td><strong>${f.AEROPUERTO}</strong></td>
      <td>${opBadge}</td>
      <td><code>${f.NRO_VUELO}</code></td>
      <td>${f.NOMBRE_AEROLINEA}</td>
      <td>${f.RUTA0}</td>
      <td>${f.HORA_ESTIMADA || f.FECHA_HORA_FORMAT || 'N/D'}</td>
      <td>${f.HORA_REAL || '-'}</td>
      <td>${f.NRO_PUERTA || '-'}</td>
      <td><span class="status-badge">${f.OBSERVACION || 'EN HORA'}</span></td>
    `;
    tbody.appendChild(tr);
  });
}

// Render Pasajes Table
function renderPasajesTable() {
  const tbody = document.getElementById("pasajes-table-tbody");
  if (!tbody) return;

  const searchTerm = (document.getElementById("pasajes-search")?.value || "").toLowerCase();
  
  const records = filteredPasajes.filter(p => {
    const text = `${p.origen_nombre} ${p.destino_nombre} ${p.empresa_aerolinea} ${p.numero_vuelo_bus} ${p.tipo_transporte}`.toLowerCase();
    return text.includes(searchTerm);
  }).slice(0, 100);

  tbody.innerHTML = "";

  if (records.length === 0) {
    tbody.innerHTML = '<tr><td colspan="10" style="text-align:center;">No se encontraron registros de pasajes</td></tr>';
    return;
  }

  records.forEach(p => {
    const tr = document.createElement("tr");
    const badgeClass = p.tipo_transporte === "VUELO" ? "badge-vuelo" : "badge-bus";
    const price = parseFloat(p.precio_bob) || 0;

    tr.innerHTML = `
      <td>${p.fecha_salida}</td>
      <td><span class="badge ${badgeClass}">${p.tipo_transporte}</span></td>
      <td><strong>${p.origen_nombre || p.origen_codigo}</strong></td>
      <td><strong>${p.destino_nombre || p.destino_codigo}</strong></td>
      <td>${p.empresa_aerolinea || '-'}</td>
      <td><code>${p.numero_vuelo_bus || '-'}</code></td>
      <td>${p.fecha_hora_salida || '-'}</td>
      <td>${p.fecha_hora_llegada || '-'}</td>
      <td><span class="price-tag">Bs. ${price.toFixed(0)}</span></td>
      <td>Bs. ${p.precio_minimo_bob || price} - ${p.precio_max_bob || price}</td>
    `;
    tbody.appendChild(tr);
  });
}
