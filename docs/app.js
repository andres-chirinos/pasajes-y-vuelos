/**
 * Monitor de Interconectividad, Movilidad y Consumo Económico - MEFP Bolivia
 * Motor Modular y Escalable con Leaflet GIS de Proporción Real
 */

// ==========================================================================
// 1. Catálogo Geoespacial de Nodos de Bolivia (Coordenadas Reales WGS84)
// ==========================================================================
const CITY_COORDS = {
  "LA PAZ": { lat: -16.500, lng: -68.150, iata: "LPB", label: "La Paz (El Alto)", dept: "La Paz", type: "HUB_AIRPORT", corridor: "TRONCAL" },
  "EL ALTO": { lat: -16.513, lng: -68.192, iata: "LPB", label: "El Alto", dept: "La Paz", type: "HUB_AIRPORT", corridor: "TRONCAL" },
  "SANTA CRUZ": { lat: -17.800, lng: -63.180, iata: "VVI", label: "Santa Cruz (Viru Viru)", dept: "Santa Cruz", type: "HUB_AIRPORT", corridor: "TRONCAL" },
  "COCHABAMBA": { lat: -17.389, lng: -66.160, iata: "CBB", label: "Cochabamba (J. Wilstermann)", dept: "Cochabamba", type: "HUB_AIRPORT", corridor: "TRONCAL" },
  "SUCRE": { lat: -19.033, lng: -65.262, iata: "SRE", label: "Sucre (Alcantarí)", dept: "Chuquisaca", type: "AIRPORT", corridor: "SUR" },
  "TARIJA": { lat: -21.535, lng: -64.729, iata: "TJA", label: "Tarija (Oriel Lea Plaza)", dept: "Tarija", type: "AIRPORT", corridor: "SUR" },
  "ORURO": { lat: -17.964, lng: -67.106, iata: "ORU", label: "Oruro (J. Mendoza)", dept: "Oruro", type: "AIRPORT", corridor: "SUR" },
  "POTOSI": { lat: -19.583, lng: -65.753, iata: "POI", label: "Potosí (Cap. Rojas)", dept: "Potosí", type: "AIRPORT", corridor: "SUR" },
  "TRINIDAD": { lat: -14.833, lng: -64.900, iata: "TDD", label: "Trinidad (J. Busch)", dept: "Beni", type: "AIRPORT", corridor: "NORTE" },
  "COBIJA": { lat: -11.026, lng: -68.769, iata: "CIJ", label: "Cobija (Cap. Aníbal Arab)", dept: "Pando", type: "AIRPORT", corridor: "NORTE" },
  "UYUNI": { lat: -20.459, lng: -66.825, iata: "UYU", label: "Uyuni (Joya Andina)", dept: "Potosí", type: "AIRPORT", corridor: "SUR" },
  "RIBERALTA": { lat: -11.006, lng: -66.064, iata: "RIB", label: "Riberalta (Cap. Selin)", dept: "Beni", type: "AIRPORT", corridor: "NORTE" },
  "GUAYARAMERIN": { lat: -10.836, lng: -65.357, iata: "GYA", label: "Guayaramerín (Cap. E. Galindo)", dept: "Beni", type: "AIRPORT", corridor: "NORTE" },
  "RURRENABAQUE": { lat: -14.442, lng: -67.527, iata: "RBQ", label: "Rurrenabaque", dept: "Beni", type: "AIRPORT", corridor: "NORTE" },
  "PUERTO SUAREZ": { lat: -18.966, lng: -57.797, iata: "PSZ", label: "Puerto Suárez (Cap. Salvador)", dept: "Santa Cruz", type: "AIRPORT", corridor: "FRONTERA" },
  "YACUIBA": { lat: -22.016, lng: -63.677, iata: "BYC", label: "Yacuiba", dept: "Tarija", type: "AIRPORT", corridor: "FRONTERA" },
  "VILLAZON": { lat: -22.091, lng: -65.596, iata: "", label: "Villazón (Frontera)", dept: "Potosí", type: "BUS_TERMINAL", corridor: "FRONTERA" },
  "CAMARGO": { lat: -20.640, lng: -65.200, iata: "", label: "Camargo", dept: "Chuquisaca", type: "BUS_TERMINAL", corridor: "SUR" },
  "DESAGUADERO": { lat: -16.566, lng: -69.041, iata: "", label: "Desaguadero (Frontera)", dept: "La Paz", type: "BUS_TERMINAL", corridor: "FRONTERA" }
};

// ==========================================================================
// 2. Estado Global de la Aplicación
// ==========================================================================
const AppState = {
  rawData: { pasajes: [], fids: [], metadata: {}, tarifas_referencia_aereas: [], bandas_tarifarias_terrestres: [] },
  filteredPasajes: [],
  filteredFids: [],
  activeLayer: "all", // "all", "vuelo", "bus"
  map: null,
  mapLayers: {
    flightLines: null,
    busLines: null,
    nodeMarkers: null
  },
  charts: {
    corridorSpend: null,
    modalShare: null,
    mobilityTimeline: null
  },
  tablePagination: {
    currentPage: 1,
    pageSize: 25,
    totalPages: 1
  }
};

// ==========================================================================
// 3. Inicialización del Sistema
// ==========================================================================
document.addEventListener("DOMContentLoaded", () => {
  initTabs();
  initFilterControls();
  initMap();
  loadData();
});

// ==========================================================================
// 4. Gestión de Pestañas y Navegación
// ==========================================================================
function initTabs() {
  const btns = document.querySelectorAll(".segmented-btn");
  btns.forEach(btn => {
    btn.addEventListener("click", () => {
      btns.forEach(b => {
        b.classList.remove("active");
        b.setAttribute("aria-selected", "false");
      });
      btn.classList.add("active");
      btn.setAttribute("aria-selected", "true");

      const tabId = btn.getAttribute("data-tab");
      document.querySelectorAll(".tab-content").forEach(content => {
        content.style.display = content.id === tabId ? "block" : "none";
      });

      // Recalcular dimensiones de mapa al mostrar la pestaña
      if (tabId === "tab-map" && AppState.map) {
        setTimeout(() => {
          AppState.map.invalidateSize();
        }, 150);
      }
    });
  });

  // Layer filter buttons on map
  document.querySelectorAll(".layer-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".layer-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      AppState.activeLayer = btn.getAttribute("data-layer");
      renderMapNetwork();
    });
  });

  // Export data button
  document.getElementById("btn-export-data")?.addEventListener("click", exportFilteredData);
}

// ==========================================================================
// 5. Controles y Filtros Dinámicos
// ==========================================================================
function initFilterControls() {
  document.getElementById("date-filter")?.addEventListener("change", applyFilters);
  document.getElementById("transport-filter")?.addEventListener("change", applyFilters);
  document.getElementById("corridor-filter")?.addEventListener("change", applyFilters);
  document.getElementById("origin-filter")?.addEventListener("change", applyFilters);
  document.getElementById("escalas-filter")?.addEventListener("change", applyFilters);

  document.getElementById("fids-search")?.addEventListener("input", renderFidsTable);
  document.getElementById("pasajes-search")?.addEventListener("input", () => {
    AppState.tablePagination.currentPage = 1;
    renderPasajesTable();
  });
}

// ==========================================================================
// 6. Carga y Normalización del Dataset
// ==========================================================================
async function loadData() {
  try {
    const res = await fetch("data_dashboard.json");
    if (!res.ok) throw new Error("HTTP error " + res.status);
    AppState.rawData = await res.json();
  } catch (err) {
    console.warn("Fallo carga de data_dashboard.json, cargando estructura vacía:", err);
  }

  const meta = AppState.rawData.metadata || {};
  const statusLabel = document.getElementById("data-updated-label");
  if (statusLabel) {
    statusLabel.textContent = meta.generated_at ? `Actualizado: ${meta.generated_at}` : "Datalake en Vivo";
  }

  populateFilterSelects();
  applyFilters();
}

function populateFilterSelects() {
  const dateSelect = document.getElementById("date-filter");
  const originSelect = document.getElementById("origin-filter");

  const dates = new Set();
  const origins = new Set();

  (AppState.rawData.pasajes || []).forEach(p => {
    if (p.fecha_salida) dates.add(p.fecha_salida);
    const orig = normalizeCityName(p.origen_nombre || p.origen_codigo);
    if (orig) origins.add(orig);
  });

  (AppState.rawData.fids || []).forEach(f => {
    if (f.FECHA) {
      const d = f.FECHA.split(" ")[0];
      if (d) dates.add(d);
    }
    const aero = normalizeCityName(f.AEROPUERTO);
    if (aero) origins.add(aero);
  });

  if (dateSelect) {
    dateSelect.innerHTML = '<option value="ALL">Todas las Fechas</option>';
    Array.from(dates).sort().forEach(d => {
      const opt = document.createElement("option");
      opt.value = d;
      opt.textContent = `📅 ${d}`;
      dateSelect.appendChild(opt);
    });
  }

  if (originSelect) {
    originSelect.innerHTML = '<option value="ALL">Todos los Orígenes</option>';
    Array.from(origins).sort().forEach(o => {
      const opt = document.createElement("option");
      opt.value = o;
      opt.textContent = `📍 ${o}`;
      originSelect.appendChild(opt);
    });
  }
}

// ==========================================================================
// 7. Motor de Filtrado y Clasificación por Corredores Económicos
// ==========================================================================
function applyFilters() {
  const selectedDate = document.getElementById("date-filter")?.value || "ALL";
  const selectedTransport = document.getElementById("transport-filter")?.value || "ALL";
  const selectedCorridor = document.getElementById("corridor-filter")?.value || "ALL";
  const selectedOrigin = document.getElementById("origin-filter")?.value || "ALL";
  const selectedEscala = document.getElementById("escalas-filter")?.value || "ALL";

  // Filtrar pasajes
  AppState.filteredPasajes = (AppState.rawData.pasajes || []).filter(p => {
    const matchDate = selectedDate === "ALL" || p.fecha_salida === selectedDate;
    const matchTransport = selectedTransport === "ALL" || p.tipo_transporte === selectedTransport;
    
    const orig = normalizeCityName(p.origen_nombre || p.origen_codigo);
    const dest = normalizeCityName(p.destino_nombre || p.destino_codigo);
    const matchOrigin = selectedOrigin === "ALL" || orig === selectedOrigin;

    // Filtro por corredor económico
    let matchCorridor = true;
    if (selectedCorridor !== "ALL") {
      matchCorridor = isRouteInCorridor(orig, dest, selectedCorridor);
    }

    const isEscalaBool = (p.es_escala === true || p.es_escala === "True" || p.es_escala === "true" || parseInt(p.numero_escalas) > 0);
    let matchEscala = true;
    if (selectedEscala === "DIRECTO") matchEscala = !isEscalaBool;
    else if (selectedEscala === "ESCALA") matchEscala = isEscalaBool;

    return matchDate && matchTransport && matchOrigin && matchCorridor && matchEscala;
  });

  // Filtrar FIDS NAABOL
  AppState.filteredFids = (AppState.rawData.fids || []).filter(f => {
    const fDate = f.FECHA ? f.FECHA.split(" ")[0] : "";
    const matchDate = selectedDate === "ALL" || fDate === selectedDate;
    const matchTransport = selectedTransport === "ALL" || selectedTransport === "VUELO";
    const aero = normalizeCityName(f.AEROPUERTO);
    const matchOrigin = selectedOrigin === "ALL" || aero === selectedOrigin;
    return matchDate && matchTransport && matchOrigin;
  });

  // Actualizar todos los módulos
  updateExecutiveKPIs();
  renderMapNetwork();
  renderTopCorridorsAndRoutes();
  renderAnalyticsCharts();
  renderRegulatoryTariffMonitors();
  renderFidsTable();
  renderPasajesTable();
}

function normalizeCityName(str) {
  if (!str) return "";
  const s = String(str).toUpperCase().trim();
  if (s.includes("PAZ") || s.includes("ALTO") || s === "LPB") return "LA PAZ";
  if (s.includes("SANTA CRUZ") || s.includes("VIRU") || s === "VVI") return "SANTA CRUZ";
  if (s.includes("COCHABAMBA") || s.includes("WILSTERMANN") || s === "CBB" || s === "CBBA") return "COCHABAMBA";
  if (s.includes("SUCRE") || s.includes("ALCANTARI") || s === "SRE") return "SUCRE";
  if (s.includes("TARIJA") || s.includes("ORIEL") || s === "TJA") return "TARIJA";
  if (s.includes("ORURO") || s.includes("MENDOZA") || s === "ORU") return "ORURO";
  if (s.includes("POTOSI") || s.includes("POTOSÍ") || s === "POI") return "POTOSI";
  if (s.includes("TRINIDAD") || s.includes("BUSCH") || s === "TDD") return "TRINIDAD";
  if (s.includes("COBIJA") || s.includes("ANIBAL") || s === "CIJ") return "COBIJA";
  if (s.includes("UYUNI") || s.includes("JOYA") || s === "UYU") return "UYUNI";
  if (s.includes("RIBERALTA") || s === "RIB") return "RIBERALTA";
  if (s.includes("GUAYARAMERIN") || s.includes("GUAYARAMERÍN") || s === "GYA") return "GUAYARAMERIN";
  if (s.includes("RURRENABAQUE") || s === "RBQ") return "RURRENABAQUE";
  if (s.includes("PUERTO SUAREZ") || s.includes("PUERTO SUÁREZ") || s === "PSZ") return "PUERTO SUAREZ";
  if (s.includes("YACUIBA") || s === "BYC") return "YACUIBA";
  if (s.includes("VILLAZON") || s.includes("VILLAZÓN")) return "VILLAZON";
  if (s.includes("CAMARGO")) return "CAMARGO";
  if (s.includes("DESAGUADERO")) return "DESAGUADERO";
  return s;
}

function isRouteInCorridor(orig, dest, corridor) {
  const troncalCities = ["LA PAZ", "COCHABAMBA", "SANTA CRUZ"];
  const surCities = ["SUCRE", "TARIJA", "POTOSI", "UYUNI", "CAMARGO", "ORURO"];
  const norteCities = ["TRINIDAD", "COBIJA", "RIBERALTA", "GUAYARAMERIN", "RURRENABAQUE"];
  const fronteraCities = ["YACUIBA", "PUERTO SUAREZ", "VILLAZON", "DESAGUADERO"];

  if (corridor === "TRONCAL") {
    return troncalCities.includes(orig) && troncalCities.includes(dest);
  } else if (corridor === "SUR") {
    return surCities.includes(orig) || surCities.includes(dest);
  } else if (corridor === "NORTE") {
    return norteCities.includes(orig) || norteCities.includes(dest);
  } else if (corridor === "FRONTERA") {
    return fronteraCities.includes(orig) || fronteraCities.includes(dest);
  }
  return true;
}

// ==========================================================================
// 8. Cálculo de Métricas e Índice de Movilidad como Proxy de Consumo Económico
// ==========================================================================
function updateExecutiveKPIs() {
  const totalPasajes = AppState.filteredPasajes.length;
  const totalFids = AppState.filteredFids.length;
  const totalOps = totalPasajes + totalFids;

  const flightPasajes = AppState.filteredPasajes.filter(p => p.tipo_transporte === "VUELO");
  const busPasajes = AppState.filteredPasajes.filter(p => p.tipo_transporte === "BUS");

  // Estimación de pasajeros: ~120 pax por vuelo comercial, ~38 pax por bus interdepartamental
  const totalPaxEst = (flightPasajes.length + totalFids) * 120 + busPasajes.length * 38;

  // Cálculo de gasto total estimado en movilidad (Proxy de consumo económico)
  let totalEconomicSpend = 0;
  
  const flightPrices = [];
  flightPasajes.forEach(p => {
    const pr = parseFloat(p.precio_bob) || 0;
    if (pr > 0) {
      flightPrices.push(pr);
      totalEconomicSpend += pr * 120;
    }
  });

  const busPrices = [];
  busPasajes.forEach(p => {
    const pr = parseFloat(p.precio_bob) || 0;
    if (pr > 0) {
      busPrices.push(pr);
      totalEconomicSpend += pr * 38;
    }
  });

  const avgFlightPrice = flightPrices.length > 0 ? (flightPrices.reduce((a, b) => a + b, 0) / flightPrices.length) : 0;
  const avgBusPrice = busPrices.length > 0 ? (busPrices.reduce((a, b) => a + b, 0) / busPrices.length) : 0;

  // Índice General de Movilidad (Base 100 normalizado)
  const baseFactor = 250; // Factor de normalización estándar
  const mobilityIndex = Math.min(150, Math.max(10, (totalOps / baseFactor) * 100));

  // Renderizar valores en el DOM
  document.getElementById("kpi-mobility-index").textContent = mobilityIndex.toFixed(1);
  const gradeBadge = document.getElementById("kpi-mobility-grade");
  if (gradeBadge) {
    if (mobilityIndex >= 90) {
      gradeBadge.textContent = "Dinamismo Alto";
      gradeBadge.className = "kpi-badge badge-emerald";
    } else if (mobilityIndex >= 50) {
      gradeBadge.textContent = "Dinamismo Moderado";
      gradeBadge.className = "kpi-badge badge-cyan";
    } else {
      gradeBadge.textContent = "Dinamismo Reducido";
      gradeBadge.className = "kpi-badge badge-amber";
    }
  }

  document.getElementById("kpi-total-ops").textContent = totalOps.toLocaleString();
  document.getElementById("kpi-pax-est").textContent = `${(totalPaxEst / 1000).toFixed(1)}k pax est.`;
  document.getElementById("kpi-ops-breakdown").textContent = `${flightPasajes.length + totalFids} vuelos • ${busPasajes.length} flotas`;

  // Gasto económico en Millones de Bs.
  const spendMillions = (totalEconomicSpend / 1_000_000).toFixed(2);
  document.getElementById("kpi-economic-spend").textContent = `Bs. ${spendMillions} M`;

  document.getElementById("kpi-avg-flight-price").textContent = `Bs. ${avgFlightPrice.toFixed(0)}`;
  document.getElementById("kpi-flight-tmr-diff").textContent = `TMR Ref: ~Bs. 850`;

  document.getElementById("kpi-avg-bus-price").textContent = `Bs. ${avgBusPrice.toFixed(0)}`;
  document.getElementById("kpi-bus-att-diff").textContent = `Banda ATT: Activa`;
}

// ==========================================================================
// 9. Mapa Geoespacial con Leaflet (Escala y Proporción Real de Bolivia)
// ==========================================================================
function initMap() {
  const mapContainer = document.getElementById("leaflet-map");
  if (!mapContainer) return;

  // Centro exacto de Bolivia con proyección real WGS84
  AppState.map = L.map("leaflet-map", {
    center: [-16.6, -64.7],
    zoom: 6,
    minZoom: 5,
    maxZoom: 11,
    zoomControl: true,
    attributionControl: false
  });

  // Capa base CartoDB Dark Matter (Ultra-limpia, de alto contraste)
  L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
    subdomains: "abcd",
    maxZoom: 19
  }).addTo(AppState.map);

  // Grupos de capas
  AppState.mapLayers.flightLines = L.layerGroup().addTo(AppState.map);
  AppState.mapLayers.busLines = L.layerGroup().addTo(AppState.map);
  AppState.mapLayers.nodeMarkers = L.layerGroup().addTo(AppState.map);
}

function renderMapNetwork() {
  if (!AppState.map) return;

  AppState.mapLayers.flightLines.clearLayers();
  AppState.mapLayers.busLines.clearLayers();
  AppState.mapLayers.nodeMarkers.clearLayers();

  const routeAgg = {};
  const nodeActivity = {};

  // Inicializar actividad de nodos
  Object.keys(CITY_COORDS).forEach(c => {
    nodeActivity[c] = { vuelos: 0, buses: 0, totalPax: 0, totalSpend: 0, prices: [] };
  });

  // Agregar vuelos de FIDS NAABOL
  AppState.filteredFids.forEach(f => {
    const orig = normalizeCityName(f.AEROPUERTO);
    let dest = normalizeCityName(f.RUTA0);
    if (!dest && orig === "LA PAZ") dest = "SANTA CRUZ";
    if (!dest && orig === "SANTA CRUZ") dest = "COCHABAMBA";

    if (CITY_COORDS[orig] && CITY_COORDS[dest] && orig !== dest) {
      const key = `VUELO:${orig}->${dest}`;
      if (!routeAgg[key]) {
        routeAgg[key] = { orig, dest, type: "VUELO", count: 0, prices: [] };
      }
      routeAgg[key].count++;
      if (nodeActivity[orig]) nodeActivity[orig].vuelos++;
      if (nodeActivity[dest]) nodeActivity[dest].vuelos++;
    }
  });

  // Agregar pasajes comerciales
  AppState.filteredPasajes.forEach(p => {
    const orig = normalizeCityName(p.origen_nombre || p.origen_codigo);
    const dest = normalizeCityName(p.destino_nombre || p.destino_codigo);
    const type = p.tipo_transporte;
    const pr = parseFloat(p.precio_bob) || 0;

    if (CITY_COORDS[orig] && CITY_COORDS[dest] && orig !== dest) {
      const key = `${type}:${orig}->${dest}`;
      if (!routeAgg[key]) {
        routeAgg[key] = { orig, dest, type, count: 0, prices: [] };
      }
      routeAgg[key].count++;
      if (pr > 0) routeAgg[key].prices.push(pr);

      if (nodeActivity[orig]) {
        if (type === "VUELO") nodeActivity[orig].vuelos++;
        else nodeActivity[orig].buses++;
        if (pr > 0) nodeActivity[orig].prices.push(pr);
      }
      if (nodeActivity[dest]) {
        if (type === "VUELO") nodeActivity[dest].vuelos++;
        else nodeActivity[dest].buses++;
      }
    }
  });

  // Dibujar Rutas Geográficas con Arcos y Curvatura Geodésica
  Object.values(routeAgg).forEach(r => {
    if (AppState.activeLayer === "vuelo" && r.type !== "VUELO") return;
    if (AppState.activeLayer === "bus" && r.type !== "BUS") return;

    const c1 = CITY_COORDS[r.orig];
    const c2 = CITY_COORDS[r.dest];
    if (!c1 || !c2) return;

    // Calcular punto de arco intermedio para dar efecto de curvatura
    const midLat = (c1.lat + c2.lat) / 2 + (r.type === "VUELO" ? 0.35 : -0.15);
    const midLng = (c1.lng + c2.lng) / 2 + (r.type === "VUELO" ? -0.35 : 0.2);

    const latlngs = [
      [c1.lat, c1.lng],
      [midLat, midLng],
      [c2.lat, c2.lng]
    ];

    const isFlight = r.type === "VUELO";
    const avgPrice = r.prices.length ? (r.prices.reduce((a, b) => a + b, 0) / r.prices.length).toFixed(0) : "Ref";
    const strokeWidth = Math.min(7, Math.max(1.8, Math.log2(r.count + 1) * 1.5));
    const strokeColor = isFlight ? "#06b6d4" : "#f59e0b";
    const strokeOpacity = isFlight ? 0.75 : 0.65;

    const polyline = L.polyline(latlngs, {
      color: strokeColor,
      weight: strokeWidth,
      opacity: strokeOpacity,
      smoothFactor: 1.5,
      dashArray: isFlight ? null : "4, 6"
    });

    const popupHtml = `
      <div class="map-popup-header">${isFlight ? "✈️ Vuelo" : "🚌 Flota"}: ${r.orig} ➔ ${r.dest}</div>
      <div class="map-popup-stat"><span>Frecuencias:</span> <strong>${r.count} salidas</strong></div>
      <div class="map-popup-stat"><span>Tarifa Promedio:</span> <strong>Bs. ${avgPrice}</strong></div>
      <div class="map-popup-stat"><span>Estimación Flujo:</span> <strong>~${r.count * (isFlight ? 120 : 38)} pasajeros</strong></div>
      <div class="map-popup-stat"><span>Gasto Est. Ruta:</span> <strong>Bs. ${(r.count * (isFlight ? 120 : 38) * (parseFloat(avgPrice) || 50)).toLocaleString()}</strong></div>
    `;

    polyline.bindPopup(popupHtml);
    if (isFlight) polyline.addTo(AppState.mapLayers.flightLines);
    else polyline.addTo(AppState.mapLayers.busLines);
  });

  // Dibujar Marcadores y Nodos Urbanos de Bolivia
  let activeNodesCount = 0;
  Object.keys(CITY_COORDS).forEach(key => {
    const node = CITY_COORDS[key];
    const act = nodeActivity[key] || { vuelos: 0, buses: 0, prices: [] };
    const totalOps = act.vuelos + act.buses;
    if (totalOps > 0) activeNodesCount++;

    const isHub = node.corridor === "TRONCAL";
    const radius = isHub ? Math.min(14, Math.max(7, 6 + Math.log2(totalOps + 1) * 1.8)) : 6;
    const nodeColor = isHub ? "#3b82f6" : (node.type === "AIRPORT" ? "#06b6d4" : "#10b981");

    const marker = L.circleMarker([node.lat, node.lng], {
      radius,
      fillColor: nodeColor,
      color: "#ffffff",
      weight: 1.5,
      opacity: 1,
      fillOpacity: 0.9
    });

    const avgP = act.prices.length ? (act.prices.reduce((a, b) => a + b, 0) / act.prices.length).toFixed(0) : "N/D";
    const popupHtml = `
      <div class="map-popup-header">📍 ${node.label} (${node.dept})</div>
      <div class="map-popup-stat"><span>Salidas Aéreas:</span> <strong>${act.vuelos} vuelos</strong></div>
      <div class="map-popup-stat"><span>Salidas Terrestres:</span> <strong>${act.buses} flotas</strong></div>
      <div class="map-popup-stat"><span>Total Operaciones:</span> <strong>${totalOps} frecuencias</strong></div>
      <div class="map-popup-stat"><span>Tarifa Prom. Nodo:</span> <strong>Bs. ${avgP}</strong></div>
      <div class="map-popup-stat"><span>Corredor:</span> <strong>${node.corridor}</strong></div>
    `;

    marker.bindPopup(popupHtml);
    marker.addTo(AppState.mapLayers.nodeMarkers);
  });

  const nodeBadge = document.getElementById("map-nodes-badge");
  if (nodeBadge) {
    nodeBadge.textContent = `${activeNodesCount} Nodos Activos`;
  }
}

// ==========================================================================
// 10. Corredores de Mayor Movilidad y Rutas Principales
// ==========================================================================
function renderTopCorridorsAndRoutes() {
  const corridorStats = {
    "TRONCAL": { name: "Eje Troncal (LPZ-CBB-SCZ)", ops: 0, spend: 0, pax: 0 },
    "SUR": { name: "Corredor Sur (Chuquisaca/Tarija/Potosí/Oruro)", ops: 0, spend: 0, pax: 0 },
    "NORTE": { name: "Corredor Norte & Amazonía (Beni/Pando)", ops: 0, spend: 0, pax: 0 },
    "FRONTERA": { name: "Corredores de Integración y Frontera", ops: 0, spend: 0, pax: 0 }
  };

  const routeMap = {};

  AppState.filteredPasajes.forEach(p => {
    const orig = normalizeCityName(p.origen_nombre || p.origen_codigo);
    const dest = normalizeCityName(p.destino_nombre || p.destino_codigo);
    const type = p.tipo_transporte;
    const price = parseFloat(p.precio_bob) || 0;
    const paxFactor = type === "VUELO" ? 120 : 38;

    // Acumular por corredor
    Object.keys(corridorStats).forEach(cKey => {
      if (isRouteInCorridor(orig, dest, cKey)) {
        corridorStats[cKey].ops++;
        corridorStats[cKey].pax += paxFactor;
        corridorStats[cKey].spend += price * paxFactor;
      }
    });

    const routeKey = `${orig} ➔ ${dest} [${type}]`;
    if (!routeMap[routeKey]) {
      routeMap[routeKey] = { orig, dest, type, count: 0, prices: [] };
    }
    routeMap[routeKey].count++;
    if (price > 0) routeMap[routeKey].prices.push(price);
  });

  // Renderizar tarjetas de corredores
  const corridorsContainer = document.getElementById("top-corridors-container");
  if (corridorsContainer) {
    corridorsContainer.innerHTML = "";
    Object.keys(corridorStats).forEach(key => {
      const c = corridorStats[key];
      const spendM = (c.spend / 1_000_000).toFixed(2);
      const card = document.createElement("div");
      card.className = "corridor-card";
      card.innerHTML = `
        <div class="corridor-info">
          <div class="corridor-name">${c.name}</div>
          <div class="corridor-meta">${c.ops} frecuencias registradas • ${(c.pax / 1000).toFixed(1)}k pasajeros est.</div>
        </div>
        <div class="corridor-metrics">
          <span class="corridor-spend">Bs. ${spendM} M</span>
          <span class="corridor-index-pill">Gasto Estimado</span>
        </div>
      `;
      card.addEventListener("click", () => {
        const corrSelect = document.getElementById("corridor-filter");
        if (corrSelect) {
          corrSelect.value = key;
          applyFilters();
        }
      });
      corridorsContainer.appendChild(card);
    });
  }

  // Renderizar tabla de rutas top
  const sortedRoutes = Object.values(routeMap).sort((a, b) => b.count - a.count).slice(0, 7);
  const tbody = document.getElementById("top-routes-tbody");
  if (!tbody) return;
  tbody.innerHTML = "";

  if (sortedRoutes.length === 0) {
    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; color: var(--text-muted);">No hay rutas que coincidan con los filtros</td></tr>';
    return;
  }

  sortedRoutes.forEach(r => {
    const avgP = r.prices.length ? (r.prices.reduce((a, b) => a + b, 0) / r.prices.length).toFixed(0) : "N/D";
    const badgeClass = r.type === "VUELO" ? "badge-vuelo" : "badge-bus";
    const flowScore = Math.min(100, Math.round(r.count * 4.5));
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><strong>${r.orig}</strong> ➔ <strong>${r.dest}</strong></td>
      <td><span class="badge ${badgeClass}">${r.type}</span></td>
      <td>${r.count}</td>
      <td><span class="price-tag">Bs. ${avgP}</span></td>
      <td><span class="badge badge-status-ok">${flowScore}/100</span></td>
    `;
    tbody.appendChild(tr);
  });
}

// ==========================================================================
// 11. Gráficos de Analítica y Dinamismo Económico (Chart.js)
// ==========================================================================
function renderAnalyticsCharts() {
  renderCorridorSpendChart();
  renderModalShareChart();
  renderMobilityTimelineChart();
  renderDepartamentalRankingTable();
}

function renderCorridorSpendChart() {
  const ctx = document.getElementById("chart-corridor-spend")?.getContext("2d");
  if (!ctx) return;

  const spendByCorridor = { "Eje Troncal": 0, "Corredor Sur": 0, "Corredor Norte": 0, "Fronteras": 0 };

  AppState.filteredPasajes.forEach(p => {
    const orig = normalizeCityName(p.origen_nombre || p.origen_codigo);
    const dest = normalizeCityName(p.destino_nombre || p.destino_codigo);
    const pr = parseFloat(p.precio_bob) || 0;
    const paxFactor = p.tipo_transporte === "VUELO" ? 120 : 38;
    const spend = pr * paxFactor;

    if (isRouteInCorridor(orig, dest, "TRONCAL")) spendByCorridor["Eje Troncal"] += spend;
    else if (isRouteInCorridor(orig, dest, "SUR")) spendByCorridor["Corredor Sur"] += spend;
    else if (isRouteInCorridor(orig, dest, "NORTE")) spendByCorridor["Corredor Norte"] += spend;
    else spendByCorridor["Fronteras"] += spend;
  });

  const labels = Object.keys(spendByCorridor);
  const data = labels.map(l => (spendByCorridor[l] / 1_000_000).toFixed(2));

  if (AppState.charts.corridorSpend) AppState.charts.corridorSpend.destroy();

  AppState.charts.corridorSpend = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [{
        label: "Gasto Estimado (Millones BOB)",
        data,
        backgroundColor: ["#3b82f6", "#06b6d4", "#10b981", "#f59e0b"],
        borderRadius: 6
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false }
      },
      scales: {
        x: { ticks: { color: "#94a3b8" }, grid: { color: "rgba(255,255,255,0.05)" } },
        y: { ticks: { color: "#94a3b8" }, grid: { color: "rgba(255,255,255,0.05)" } }
      }
    }
  });
}

function renderModalShareChart() {
  const ctx = document.getElementById("chart-modal-share")?.getContext("2d");
  if (!ctx) return;

  let vueloOps = AppState.filteredFids.length;
  let busOps = 0;

  AppState.filteredPasajes.forEach(p => {
    if (p.tipo_transporte === "VUELO") vueloOps++;
    else busOps++;
  });

  if (AppState.charts.modalShare) AppState.charts.modalShare.destroy();

  AppState.charts.modalShare = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: ["Transporte Aéreo", "Flotas Terrestres"],
      datasets: [{
        data: [vueloOps, busOps],
        backgroundColor: ["#06b6d4", "#f59e0b"],
        borderWidth: 0
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: "#94a3b8" }, position: "bottom" }
      }
    }
  });
}

function renderMobilityTimelineChart() {
  const ctx = document.getElementById("chart-mobility-timeline")?.getContext("2d");
  if (!ctx) return;

  const datesMap = {};
  AppState.filteredPasajes.forEach(p => {
    const d = p.fecha_salida || "Sin fecha";
    if (!datesMap[d]) datesMap[d] = { vuelos: 0, buses: 0 };
    if (p.tipo_transporte === "VUELO") datesMap[d].vuelos++;
    else datesMap[d].buses++;
  });

  const labels = Object.keys(datesMap).sort();
  const vuelosData = labels.map(l => datesMap[l].vuelos);
  const busesData = labels.map(l => datesMap[l].buses);

  if (AppState.charts.mobilityTimeline) AppState.charts.mobilityTimeline.destroy();

  AppState.charts.mobilityTimeline = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [
        { label: "Vuelos Comerciales", data: vuelosData, backgroundColor: "#06b6d4", borderRadius: 4 },
        { label: "Flotas Terrestres", data: busesData, backgroundColor: "#f59e0b", borderRadius: 4 }
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

function renderDepartamentalRankingTable() {
  const deptMap = {
    "La Paz": { vuelos: 0, buses: 0, spend: 0 },
    "Santa Cruz": { vuelos: 0, buses: 0, spend: 0 },
    "Cochabamba": { vuelos: 0, buses: 0, spend: 0 },
    "Chuquisaca": { vuelos: 0, buses: 0, spend: 0 },
    "Tarija": { vuelos: 0, buses: 0, spend: 0 },
    "Beni": { vuelos: 0, buses: 0, spend: 0 },
    "Potosí": { vuelos: 0, buses: 0, spend: 0 },
    "Oruro": { vuelos: 0, buses: 0, spend: 0 },
    "Pando": { vuelos: 0, buses: 0, spend: 0 }
  };

  AppState.filteredPasajes.forEach(p => {
    const orig = normalizeCityName(p.origen_nombre || p.origen_codigo);
    const node = CITY_COORDS[orig];
    if (node && deptMap[node.dept]) {
      const pr = parseFloat(p.precio_bob) || 0;
      const isFlight = p.tipo_transporte === "VUELO";
      const paxFactor = isFlight ? 120 : 38;
      
      if (isFlight) deptMap[node.dept].vuelos++;
      else deptMap[node.dept].buses++;
      deptMap[node.dept].spend += pr * paxFactor;
    }
  });

  const tbody = document.getElementById("departamentos-ranking-tbody");
  if (!tbody) return;
  tbody.innerHTML = "";

  Object.keys(deptMap).forEach(dept => {
    const d = deptMap[dept];
    const totalOps = d.vuelos + d.buses;
    const totalPax = d.vuelos * 120 + d.buses * 38;
    const spendM = (d.spend / 1_000_000).toFixed(2);
    const score = Math.min(100, Math.round(totalOps * 1.5 + (d.spend / 2_000_000) * 10));

    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><strong>${dept}</strong></td>
      <td>${d.vuelos}</td>
      <td>${d.buses}</td>
      <td><strong>${totalOps}</strong></td>
      <td>~${totalPax.toLocaleString()}</td>
      <td><span class="price-tag">Bs. ${spendM} M</span></td>
      <td><span class="badge badge-status-ok">${score}/100</span></td>
    `;
    tbody.appendChild(tr);
  });
}

// ==========================================================================
// 12. Monitoreo de Tarifas vs Techos Regulatorios (TMR y ATT)
// ==========================================================================
function renderRegulatoryTariffMonitors() {
  // 1. Monitoreo de Tarifas Aéreas vs TMR
  const tbodyAir = document.getElementById("tbody-air-tmr");
  if (tbodyAir) {
    tbodyAir.innerHTML = "";
    const refAir = AppState.rawData.tarifas_referencia_aereas || [];

    refAir.slice(0, 18).forEach(r => {
      const tmr = parseFloat(r.tmr) || 0;
      const dua = parseFloat(r.dua) || 15;
      const totalTecho = parseFloat(r.valor_billete) || (tmr + dua);

      // Calcular precio de mercado observado
      const matches = AppState.filteredPasajes.filter(p => {
        const orig = normalizeCityName(p.origen_nombre || p.origen_codigo);
        const dest = normalizeCityName(p.destino_nombre || p.destino_codigo);
        return p.tipo_transporte === "VUELO" && orig.includes(r.origen_codigo) && dest.includes(r.destino_codigo);
      });

      const prices = matches.map(m => parseFloat(m.precio_bob)).filter(p => p > 0);
      const avgPrice = prices.length ? (prices.reduce((a, b) => a + b, 0) / prices.length).toFixed(0) : totalTecho.toFixed(0);
      const isUnderCap = parseFloat(avgPrice) <= totalTecho;

      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><strong>${r.origen || r.origen_codigo} ➔ ${r.destino || r.destino_codigo}</strong></td>
        <td>Bs. ${tmr.toFixed(0)}</td>
        <td>Bs. ${dua.toFixed(0)}</td>
        <td><span class="price-tag">Bs. ${totalTecho.toFixed(0)}</span></td>
        <td><span class="price-tag">Bs. ${avgPrice}</span></td>
        <td>
          <span class="badge ${isUnderCap ? "badge-status-ok" : "badge-status-alert"}">
            ${isUnderCap ? "✓ Conforme a TMR" : "⚠️ Excede Techo"}
          </span>
        </td>
      `;
      tbodyAir.appendChild(tr);
    });
  }

  // 2. Monitoreo de Tarifas Terrestres vs ATT
  const tbodyBus = document.getElementById("tbody-bus-att");
  if (tbodyBus) {
    tbodyBus.innerHTML = "";
    const refBus = AppState.rawData.bandas_tarifarias_terrestres || [];

    refBus.slice(0, 18).forEach(b => {
      const normal = b.normal || [0, 0];
      const semicama = b.semicama || [0, 0];
      const cama = b.cama || [0, 0];

      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><strong>${b.origen} ➔ ${b.destino}</strong> ${b.detalle ? `<small>(${b.detalle})</small>` : ""}</td>
        <td>Bs. ${normal[0]} - ${normal[1]}</td>
        <td>Bs. ${semicama[0]} - ${semicama[1]}</td>
        <td>Bs. ${cama[0]} - ${cama[1]}</td>
        <td><span class="price-tag">Bs. ${((normal[1] + semicama[1]) / 2).toFixed(0)}</span></td>
        <td><span class="badge badge-status-ok">✓ Regulado ATT</span></td>
      `;
      tbodyBus.appendChild(tr);
    });
  }
}

// ==========================================================================
// 13. Tablas de Detalle: FIDS NAABOL y Registro General Paginado
// ==========================================================================
function renderFidsTable() {
  const tbody = document.getElementById("fids-table-tbody");
  if (!tbody) return;
  tbody.innerHTML = "";

  const query = (document.getElementById("fids-search")?.value || "").toUpperCase();
  const list = AppState.filteredFids.filter(f => {
    if (!query) return true;
    return (
      (f.AEROPUERTO && f.AEROPUERTO.toUpperCase().includes(query)) ||
      (f.NOMBRE_AEROLINEA && f.NOMBRE_AEROLINEA.toUpperCase().includes(query)) ||
      (f.NRO_VUELO && f.NRO_VUELO.toUpperCase().includes(query)) ||
      (f.RUTA0 && f.RUTA0.toUpperCase().includes(query))
    );
  });

  if (list.length === 0) {
    tbody.innerHTML = '<tr><td colspan="9" style="text-align:center; color: var(--text-muted);">No hay itinerarios FIDS disponibles</td></tr>';
    return;
  }

  list.slice(0, 40).forEach(f => {
    const estado = f.OBSERVACION || "A TIEMPO";
    const isLate = estado.toUpperCase().includes("DEMOR") || estado.toUpperCase().includes("CANCEL");
    const badgeClass = isLate ? "badge-status-alert" : "badge-status-ok";

    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><strong>${f.AEROPUERTO || "NAABOL"}</strong></td>
      <td><span class="badge badge-vuelo">${f.TIPO_OPERACION || "SALIDA"}</span></td>
      <td><strong>${f.NRO_VUELO || "N/D"}</strong></td>
      <td>${f.NOMBRE_AEROLINEA || "Línea Aérea"}</td>
      <td>${f.RUTA0 || "Directo"}</td>
      <td>${f.HORA_ESTIMADA || f.FECHA_HORA || "-"}</td>
      <td>${f.HORA_REAL || "-"}</td>
      <td>${f.NRO_PUERTA || "-"}</td>
      <td><span class="badge ${badgeClass}">${estado}</span></td>
    `;
    tbody.appendChild(tr);
  });
}

function renderPasajesTable() {
  const tbody = document.getElementById("pasajes-table-tbody");
  if (!tbody) return;
  tbody.innerHTML = "";

  const query = (document.getElementById("pasajes-search")?.value || "").toUpperCase();
  const list = AppState.filteredPasajes.filter(p => {
    if (!query) return true;
    return (
      (p.empresa_aerolinea && p.empresa_aerolinea.toUpperCase().includes(query)) ||
      (p.origen_nombre && p.origen_nombre.toUpperCase().includes(query)) ||
      (p.destino_nombre && p.destino_nombre.toUpperCase().includes(query)) ||
      (p.numero_vuelo_bus && p.numero_vuelo_bus.toUpperCase().includes(query))
    );
  });

  const totalItems = list.length;
  const pageSize = AppState.tablePagination.pageSize;
  AppState.tablePagination.totalPages = Math.ceil(totalItems / pageSize) || 1;
  const current = AppState.tablePagination.currentPage;

  const startIdx = (current - 1) * pageSize;
  const pageItems = list.slice(startIdx, startIdx + pageSize);

  if (pageItems.length === 0) {
    tbody.innerHTML = '<tr><td colspan="11" style="text-align:center; color: var(--text-muted);">No se encontraron pasajes</td></tr>';
    renderPaginationControls(totalItems);
    return;
  }

  pageItems.forEach(p => {
    const isFlight = p.tipo_transporte === "VUELO";
    const badgeClass = isFlight ? "badge-vuelo" : "badge-bus";
    const pr = parseFloat(p.precio_bob) || 0;

    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${p.fecha_salida || "-"}</td>
      <td><span class="badge ${badgeClass}">${p.tipo_transporte}</span></td>
      <td><strong>${p.origen_nombre || p.origen_codigo}</strong></td>
      <td><strong>${p.destino_nombre || p.destino_codigo}</strong></td>
      <td>${p.empresa_aerolinea || "Empresa"}</td>
      <td>${p.numero_vuelo_bus || "-"}</td>
      <td>${p.fecha_hora_salida || "-"}</td>
      <td>${p.fecha_hora_llegada || "-"}</td>
      <td>${p.categoria_cabina || "-"}</td>
      <td>${p.escalas_duracion || "-"}</td>
      <td><span class="price-tag">Bs. ${pr > 0 ? pr.toFixed(0) : "N/D"}</span></td>
    `;
    tbody.appendChild(tr);
  });

  renderPaginationControls(totalItems);
}

function renderPaginationControls(totalItems) {
  const container = document.getElementById("pasajes-pagination");
  if (!container) return;

  const { currentPage, totalPages, pageSize } = AppState.tablePagination;
  const startItem = totalItems > 0 ? (currentPage - 1) * pageSize + 1 : 0;
  const endItem = Math.min(currentPage * pageSize, totalItems);

  container.innerHTML = `
    <div>Mostrando <strong>${startItem} - ${endItem}</strong> de <strong>${totalItems.toLocaleString()}</strong> pasajes</div>
    <div class="pagination-btns">
      <button class="page-btn" ${currentPage === 1 ? "disabled" : ""} onclick="changePage(${currentPage - 1})">◀ Anterior</button>
      <span style="padding: 0.3rem 0.6rem;">Pág. ${currentPage} / ${totalPages}</span>
      <button class="page-btn" ${currentPage === totalPages ? "disabled" : ""} onclick="changePage(${currentPage + 1})">Siguiente ▶</button>
    </div>
  `;
}

window.changePage = function(page) {
  if (page >= 1 && page <= AppState.tablePagination.totalPages) {
    AppState.tablePagination.currentPage = page;
    renderPasajesTable();
  }
};

// ==========================================================================
// 14. Exportador de Datos
// ==========================================================================
function exportFilteredData() {
  const exportPayload = {
    metadata: {
      generated_at: new Date().toISOString(),
      total_pasajes_filtrados: AppState.filteredPasajes.length,
      total_fids_filtrados: AppState.filteredFids.length
    },
    pasajes: AppState.filteredPasajes,
    fids: AppState.filteredFids
  };

  const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(exportPayload, null, 2));
  const downloadAnchor = document.createElement("a");
  downloadAnchor.setAttribute("href", dataStr);
  downloadAnchor.setAttribute("download", `mefp_movilidad_bolivia_${new Date().toISOString().split("T")[0]}.json`);
  document.body.appendChild(downloadAnchor);
  downloadAnchor.click();
  downloadAnchor.remove();
}
