// EnergyIQ - Core Application Controller

const API_BASE = "/api";

const AppState = {
  currentRole: "Plant Operator",
  currentPlant: "PLANT-001",
  dateFilter: "90",
  summary: null,
  trends: null,
  forecast: null,
  anomalies: [],
  recommendations: [],
  productionIntensity: [],
  batches: [],
  dataQuality: null,
  auditLogs: [],
  evaluation: null,
  scadaSimInterval: null,
  isScadaSimulating: false
};

// Initialize Application on Page Load
document.addEventListener("DOMContentLoaded", () => {
  setupEventListeners();
  loadAllData();
});

function setupEventListeners() {
  // Role Switcher
  const roleSelect = document.getElementById("userRoleSelect");
  if (roleSelect) {
    roleSelect.addEventListener("change", (e) => {
      AppState.currentRole = e.target.value;
      updateRoleUI();
      showToast("Role Updated", `Active perspective: ${AppState.currentRole}`);
    });
  }

  // Plant Selector
  const plantSelect = document.getElementById("plantSelect");
  if (plantSelect) {
    plantSelect.addEventListener("change", (e) => {
      AppState.currentPlant = e.target.value;
      loadAllData();
    });
  }

  // Refresh Button
  const btnRefresh = document.getElementById("btnRefresh");
  if (btnRefresh) {
    btnRefresh.addEventListener("click", () => {
      loadAllData();
      showToast("Telemetry Refreshed", "Live industrial readings updated from database.");
    });
  }

  // Run Analytics Trigger
  const btnRunAnalytics = document.getElementById("btnRunAnalytics");
  if (btnRunAnalytics) {
    btnRunAnalytics.addEventListener("click", runAnalyticsPipeline);
  }

  // Run Benchmark Evaluation
  const btnRunEval = document.getElementById("btnRunEval");
  if (btnRunEval) {
    btnRunEval.addEventListener("click", runEvaluationBenchmark);
  }

  // Auto Remediation Trigger
  const btnRemediate = document.getElementById("btnRemediate");
  if (btnRemediate) {
    btnRemediate.addEventListener("click", executeAutoRemediation);
  }

  // SCADA Simulation Toggle
  const btnSimulate = document.getElementById("btnSimulateScada");
  if (btnSimulate) {
    btnSimulate.addEventListener("click", toggleScadaSimulation);
  }

  // Copilot Toggle & Form
  const btnCopilotToggle = document.getElementById("btnCopilotToggle");
  if (btnCopilotToggle) {
    btnCopilotToggle.addEventListener("click", toggleCopilot);
  }

  const copilotForm = document.getElementById("copilotForm");
  if (copilotForm) {
    copilotForm.addEventListener("submit", handleCopilotSubmit);
  }

  // Maintenance Form Submission
  const maintForm = document.getElementById("maintForm");
  if (maintForm) {
    maintForm.addEventListener("submit", handleMaintenanceSubmit);
  }
}

function updateRoleUI() {
  const badge = document.getElementById("activeRoleBadge");
  if (badge) {
    badge.innerText = AppState.currentRole;
  }
  const hint = document.getElementById("rolePerspectiveHint");
  if (hint) {
    if (AppState.currentRole === "Plant Operator") {
      hint.innerText = "Mode: Plant Operator - Monitoring real-time telemetry, shift alert acknowledgements & energy waste.";
    } else if (AppState.currentRole === "Maintenance/Quality Engineer") {
      hint.innerText = "Mode: Maintenance Engineer - Root cause analysis, machine baseline deviations & work orders.";
    } else if (AppState.currentRole === "Production Planner") {
      hint.innerText = "Mode: Production Planner - Energy intensity per unit, batch scheduling & tariff window alignment.";
    } else if (AppState.currentRole === "OT/IT Administrator") {
      hint.innerText = "Mode: OT/IT Administrator - Data quality reconciliation, hierarchy integrity, models & evaluation.";
    }
  }
}

async function loadAllData() {
  showLoading(true);
  try {
    await Promise.all([
      fetchSummary(),
      fetchTrends(),
      fetchForecast(),
      fetchAnomalies(),
      fetchRecommendations(),
      fetchProductionIntensity(),
      fetchDataQuality(),
      fetchAuditLogs()
    ]);
  } catch (err) {
    console.error("Error loading EnergyIQ dashboard data:", err);
  } finally {
    showLoading(false);
  }
}

// ---------------------------------------------------------------------
// API Data Fetchers
// ---------------------------------------------------------------------

async function fetchSummary() {
  const res = await fetch(`${API_BASE}/energy/summary?plant_id=${AppState.currentPlant}`);
  if (!res.ok) throw new Error("Failed to fetch energy summary");
  const data = await res.json();
  AppState.summary = data;
  renderKPIs(data);
}

async function fetchTrends() {
  const res = await fetch(`${API_BASE}/energy/trends?plant_id=${AppState.currentPlant}`);
  if (!res.ok) throw new Error("Failed to fetch energy trends");
  const data = await res.json();
  AppState.trends = data;

  renderDailyTrendChart("chartDailyTrend", data.daily);
  renderHourlyProfileChart("chartHourlyProfile", data.hourly);
  renderMachineBreakdownChart("chartMachineBreakdown", data.machines);
  renderTariffDonutChart("chartTariffBreakdown", data.tariffs);
  renderWeatherCorrelationChart("chartWeatherCorr", data.weather_correlation);
}

async function fetchForecast() {
  const res = await fetch(`${API_BASE}/energy/forecast?plant_id=${AppState.currentPlant}`);
  if (!res.ok) return;
  const data = await res.json();
  AppState.forecast = data;
  renderForecast(data);
}

async function fetchAnomalies() {
  const res = await fetch(`${API_BASE}/anomalies?plant_id=${AppState.currentPlant}&limit=80`);
  if (!res.ok) throw new Error("Failed to fetch anomalies");
  const data = await res.json();
  AppState.anomalies = data;
  renderAnomaliesTable(data);
}

async function fetchRecommendations() {
  const res = await fetch(`${API_BASE}/recommendations?plant_id=${AppState.currentPlant}`);
  if (!res.ok) throw new Error("Failed to fetch recommendations");
  const data = await res.json();
  AppState.recommendations = data;
  renderRecommendations(data);
}

async function fetchProductionIntensity() {
  const res = await fetch(`${API_BASE}/production/intensity?plant_id=${AppState.currentPlant}`);
  if (!res.ok) throw new Error("Failed to fetch production intensity");
  const data = await res.json();
  AppState.productionIntensity = data;
  renderIntensityTable(data);
}

async function fetchDataQuality() {
  const res = await fetch(`${API_BASE}/data-quality?plant_id=${AppState.currentPlant}`);
  if (!res.ok) throw new Error("Failed to fetch data quality issues");
  const data = await res.json();
  AppState.dataQuality = data;
  renderDataQualityHub(data);
}

async function fetchAuditLogs() {
  const res = await fetch(`${API_BASE}/audit-logs?limit=50`);
  if (!res.ok) return;
  const data = await res.json();
  AppState.auditLogs = data;
  renderAuditLogs(data);
}

// ---------------------------------------------------------------------
// DOM Renderers
// ---------------------------------------------------------------------

function renderKPIs(s) {
  document.getElementById("kpiTotalKwh").innerText = `${Number(s.total_energy_kwh).toLocaleString(undefined, { maximumFractionDigits: 0 })} kWh`;
  document.getElementById("kpiTotalCost").innerText = `$${Number(s.total_cost_usd).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
  document.getElementById("kpiPeakDemand").innerText = `${Number(s.peak_demand_kw).toFixed(1)} kW`;
  document.getElementById("kpiIntensity").innerText = `${Number(s.avg_energy_intensity_kwh_per_unit).toFixed(3)} kWh/u`;
  document.getElementById("kpiIdleWaste").innerText = `${Number(s.total_idle_energy_kwh).toLocaleString(undefined, { maximumFractionDigits: 0 })} kWh`;
  document.getElementById("kpiIdleWasteSub").innerText = `${s.idle_percentage}% total (${Number(s.idle_energy_waste_usd).toLocaleString(undefined, {style: 'currency', currency: 'USD'})} waste)`;
  document.getElementById("kpiSavings").innerText = `$${Number(s.total_potential_savings_usd).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
  document.getElementById("kpiSavingsSub").innerText = `~${Number(s.total_potential_savings_kwh).toLocaleString(undefined, { maximumFractionDigits: 0 })} kWh verifiable`;
}

function renderForecast(fc) {
  renderForecastChart("chartForecast", fc);
  const banner = document.getElementById("forecastAlertBanner");
  if (banner) {
    banner.innerText = fc.peak_shaving_recommendation;
  }
}

function renderAnomaliesTable(anomalies) {
  const tbody = document.getElementById("anomaliesTableBody");
  if (!tbody) return;

  if (anomalies.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" class="text-center py-4 text-muted">No anomalies matching current criteria.</td></tr>`;
    return;
  }

  tbody.innerHTML = anomalies.map(a => {
    let badgeClass = "badge-medium";
    if (a.severity === "CRITICAL") badgeClass = "badge-critical";
    else if (a.severity === "HIGH") badgeClass = "badge-high";
    else if (a.severity === "LOW") badgeClass = "badge-low";

    const isResolved = a.status === "RESOLVED";
    const isAck = a.status === "ACKNOWLEDGED";

    return `
      <tr>
        <td class="mono-cell fw-bold text-white">${a.anomaly_id}</td>
        <td><span class="badge ${badgeClass}">${a.severity}</span></td>
        <td class="fw-semibold">${a.anomaly_type.replace(/_/g, " ")}</td>
        <td class="mono-cell">
          ${a.machine_id ? `<span class="machine-link" onclick="openMachineDiagnostics('${a.machine_id}')">${a.machine_id}</span>` : (a.meter_id || "Plant")}
        </td>
        <td class="mono-cell text-muted">${a.timestamp.substring(0, 16).replace("T", " ")}</td>
        <td style="max-width: 380px;">${a.evidence}</td>
        <td>
          ${isResolved ? `<span class="badge badge-low"><i class="bi bi-check-circle"></i> Resolved</span>` :
            isAck ? `<button class="btn btn-sm btn-outline-success" onclick="resolveAnomaly('${a.anomaly_id}')"><i class="bi bi-check-all"></i> Mark Resolved</button>` :
            `<button class="btn btn-sm btn-outline-warning" onclick="acknowledgeAnomaly('${a.anomaly_id}')"><i class="bi bi-bell"></i> Acknowledge</button>`
          }
        </td>
      </tr>
    `;
  }).join("");
}

function renderRecommendations(recs) {
  const container = document.getElementById("recommendationsContainer");
  if (!container) return;

  if (recs.length === 0) {
    container.innerHTML = `<div class="text-center py-5 text-muted">No pending recommendations. System fully optimized.</div>`;
    return;
  }

  container.innerHTML = recs.map(r => {
    const isApproved = r.status === "approved";
    const isRejected = r.status === "rejected";

    return `
      <div class="rec-card" id="card-${r.recommendation_id}">
        <div class="d-flex justify-content-between align-items-start mb-2">
          <div>
            <span class="badge bg-primary text-uppercase me-2">${r.category.replace(/_/g, " ")}</span>
            <span class="mono-cell text-muted">${r.recommendation_id}</span>
            <h6 class="mt-2 mb-1 fw-bold text-white">Target: ${r.machine_id ? `<span class="machine-link" onclick="openMachineDiagnostics('${r.machine_id}')">${r.machine_id}</span>` : (r.meter_id || "Plant Operations")}</h6>
          </div>
          <div>
            ${isApproved ? `<span class="badge badge-approved fs-6"><i class="bi bi-check-circle-fill"></i> Approved</span>` :
              isRejected ? `<span class="badge badge-rejected fs-6"><i class="bi bi-x-circle-fill"></i> Rejected</span>` :
              `<span class="badge badge-high">Status: Open</span>`
            }
          </div>
        </div>

        <p class="text-light mb-3" style="font-size: 0.92rem; line-height: 1.5;">${r.rationale}</p>

        <div class="row g-2 mb-3 align-items-center">
          <div class="col-md-3">
            <div class="rec-savings">
              <div class="text-muted small">Expected Savings ($)</div>
              <div class="rec-savings-val">$${Number(r.expected_savings_usd).toLocaleString()}</div>
            </div>
          </div>
          <div class="col-md-3">
            <div class="rec-savings">
              <div class="text-muted small">Energy Reduction</div>
              <div class="rec-savings-val" style="color: #38bdf8;">${Number(r.expected_savings_kwh).toLocaleString()} <span style="font-size:0.75rem;">kWh</span></div>
            </div>
          </div>
          <div class="col-md-3">
            <div class="p-2 border rounded" style="background: rgba(255,255,255,0.03); border-color: rgba(255,255,255,0.08)!important;">
              <div class="text-muted small">Verified Baseline</div>
              <div class="mono-cell fw-bold text-white">${Number(r.baseline_value).toLocaleString()} kWh</div>
            </div>
          </div>
          <div class="col-md-3">
            <div class="p-2 border rounded" style="background: rgba(255,255,255,0.03); border-color: rgba(255,255,255,0.08)!important;">
              <div class="text-muted small">Confidence Score</div>
              <div class="fw-bold text-white">${Math.round(r.confidence * 100)}% (High Evidence)</div>
            </div>
          </div>
        </div>

        <div class="d-flex justify-content-end gap-2 border-top pt-2" style="border-color: rgba(255,255,255,0.08)!important;">
          ${!isApproved && !isRejected ? `
            <button class="btn btn-sm btn-dark-outline text-danger border-danger" onclick="rejectRecommendation('${r.recommendation_id}')">
              <i class="bi bi-x-lg"></i> Reject Action
            </button>
            <button class="btn btn-sm btn-cyan" onclick="approveRecommendation('${r.recommendation_id}')">
              <i class="bi bi-check-lg"></i> Approve & Deploy Action
            </button>
          ` : `
            <span class="text-muted small">Action recorded in immutable audit log.</span>
          `}
        </div>
      </div>
    `;
  }).join("");
}

function renderIntensityTable(items) {
  const tbody = document.getElementById("intensityTableBody");
  if (!tbody) return;

  tbody.innerHTML = items.map((m, idx) => `
    <tr>
      <td class="mono-cell fw-bold">${idx + 1}</td>
      <td class="fw-semibold">
        <span class="machine-link" onclick="openMachineDiagnostics('${m.machine_id}')">${m.machine_name}</span>
        <span class="badge bg-dark border border-secondary ms-1 small" style="font-size:0.65rem;">${m.machine_id}</span>
      </td>
      <td><span class="badge bg-secondary text-uppercase">${m.machine_type}</span></td>
      <td class="mono-cell">${m.rated_kw} kW</td>
      <td class="mono-cell">${m.completed_batches}</td>
      <td class="mono-cell">${Number(m.total_output_units).toLocaleString()}</td>
      <td class="mono-cell">${Number(m.productive_kwh).toLocaleString()}</td>
      <td class="mono-cell fw-bold ${m.energy_intensity_kwh_per_unit > 1.5 ? 'text-warning' : 'text-info'}">
        ${m.energy_intensity_kwh_per_unit} kWh/u
      </td>
      <td class="mono-cell">${m.scrap_percentage}%</td>
    </tr>
  `).join("");
}

function renderDataQualityHub(dq) {
  document.getElementById("dqTotalCount").innerText = dq.total_issues;
  document.getElementById("dqRecCount").innerText = dq.reconciliation_mismatches_count;
  document.getElementById("dqUnitCount").innerText = dq.unit_confusions_count;
  document.getElementById("dqTzCount").innerText = dq.timezone_mismatches_count;
  document.getElementById("dqDupCount").innerText = dq.duplicates_count;
  document.getElementById("dqHierCount").innerText = dq.hierarchy_mismatches_count;
  document.getElementById("dqGapCount").innerText = dq.meter_gaps_count;

  // Scenario A Table
  const tbodyA = document.getElementById("tbodyScenarioA");
  if (tbodyA) {
    tbodyA.innerHTML = dq.reconciliation_items.map(r => `
      <tr>
        <td class="mono-cell text-white">${r.affected_meter}</td>
        <td class="mono-cell">${r.date}</td>
        <td class="mono-cell text-danger fw-bold">${r.reported_kwh}</td>
        <td class="mono-cell text-success fw-bold">${r.calculated_interval_sum_kwh}</td>
        <td class="mono-cell text-warning fw-bold">+${r.discrepancy_kwh} (${r.discrepancy_pct}%)</td>
        <td>${r.decision}</td>
      </tr>
    `).join("");
  }

  // Scenario B Table
  const tbodyB = document.getElementById("tbodyScenarioB");
  if (tbodyB) {
    tbodyB.innerHTML = dq.unit_confusion_items.map(r => `
      <tr>
        <td class="mono-cell text-white">${r.record_id}</td>
        <td class="mono-cell">${r.affected_meter}</td>
        <td class="mono-cell">${r.timestamp.substring(0, 16).replace("T", " ")}</td>
        <td class="mono-cell text-danger fw-bold">${r.recorded_kwh}</td>
        <td class="mono-cell text-success fw-bold">${r.expected_kwh}</td>
        <td class="mono-cell text-warning fw-bold">${r.error_factor}x Error</td>
        <td>${r.decision}</td>
      </tr>
    `).join("");
  }

  // Scenario C Table
  const tbodyC = document.getElementById("tbodyScenarioC");
  if (tbodyC) {
    tbodyC.innerHTML = dq.timezone_items.map(r => `
      <tr>
        <td class="mono-cell text-white">${r.record_id}</td>
        <td>${r.tariff_name}</td>
        <td class="mono-cell text-danger fw-bold">${r.configured_timezone}</td>
        <td class="mono-cell text-success fw-bold">${r.plant_timezone}</td>
        <td class="mono-cell text-warning fw-bold">${r.hour_shift_offset} Hours Shift</td>
        <td>${r.decision}</td>
      </tr>
    `).join("");
  }

  // Scenario D Table
  const tbodyD = document.getElementById("tbodyScenarioD");
  if (tbodyD) {
    tbodyD.innerHTML = dq.duplicate_items.map(r => `
      <tr>
        <td class="mono-cell text-white">${r.record_id}</td>
        <td class="mono-cell">${r.affected_meter}</td>
        <td class="mono-cell">${r.timestamp.substring(0, 16).replace("T", " ")}</td>
        <td class="mono-cell text-danger">${r.duplicate_kwh} kWh</td>
        <td>${r.decision}</td>
      </tr>
    `).join("");
  }

  // Scenario E Table
  const tbodyE = document.getElementById("tbodyScenarioE");
  if (tbodyE) {
    tbodyE.innerHTML = dq.hierarchy_items.map(r => `
      <tr>
        <td class="mono-cell text-white">${r.record_id}</td>
        <td class="mono-cell text-info fw-bold">${r.affected_machine}</td>
        <td class="mono-cell text-danger fw-bold">${r.reading_meter}</td>
        <td class="mono-cell text-success fw-bold">${r.registered_machine_meter}</td>
        <td class="mono-cell">${r.timestamp.substring(0, 16).replace("T", " ")}</td>
        <td>${r.decision}</td>
      </tr>
    `).join("");
  }
}

function renderAuditLogs(logs) {
  const tbody = document.getElementById("auditTableBody");
  if (!tbody) return;

  tbody.innerHTML = logs.map(l => `
    <tr>
      <td class="mono-cell text-muted">${l.timestamp.substring(0, 19).replace("T", " ")}</td>
      <td class="fw-bold text-white">${l.event_type}</td>
      <td><span class="badge bg-secondary">${l.user_role}</span></td>
      <td class="mono-cell text-info">${l.entity_type}: ${l.entity_id}</td>
      <td>${l.details}</td>
    </tr>
  `).join("");
}

// ---------------------------------------------------------------------
// Actions & Workflow Handlers
// ---------------------------------------------------------------------

async function openMachineDiagnostics(machineId) {
  try {
    const res = await fetch(`${API_BASE}/machines/${machineId}/diagnostics`);
    if (!res.ok) throw new Error("Could not load machine diagnostics");
    const d = await res.json();

    document.getElementById("diagMachineName").innerText = `${d.machine_name} (${d.machine_id})`;
    document.getElementById("diagMachineType").innerText = d.machine_type.toUpperCase();
    document.getElementById("diagHealthScore").innerText = `${d.health_score_pct}%`;
    document.getElementById("diagHealthStatus").innerText = d.health_status;
    document.getElementById("diagHealthStatus").className = `badge ${d.health_score_pct > 85 ? 'badge-low' : (d.health_score_pct > 70 ? 'badge-high' : 'badge-critical')}`;

    document.getElementById("diagRatedKw").innerText = `${d.rated_kw} kW`;
    document.getElementById("diagIdleBase").innerText = `${d.idle_kw_baseline} kW`;
    document.getElementById("diagWearDrift").innerText = `+${d.wear_drift_pct}% drift`;
    document.getElementById("diagTotKwh").innerText = `${Number(d.total_energy_kwh).toLocaleString()} kWh`;
    document.getElementById("diagIdleKwh").innerText = `${Number(d.idle_energy_kwh).toLocaleString()} kWh (${d.idle_percentage}%)`;
    document.getElementById("diagPeakKw").innerText = `${d.peak_power_kw} kW`;

    // Render machine diagnostic chart
    renderMachineDiagnosticChart("chartMachineDiagnostics", d.hourly_profile);

    // Populate recent batches
    const batchList = document.getElementById("diagBatchList");
    if (batchList) {
      batchList.innerHTML = d.recent_batches.slice(0, 5).map(b => `
        <li class="list-group-item bg-transparent border-secondary text-white small d-flex justify-content-between">
          <span>${b.batch_id} (${b.actual_start_ts.substring(0, 10)})</span>
          <span class="text-info">${b.output_qty} units (${b.status})</span>
        </li>
      `).join("");
    }

    // Show Modal
    const modal = new bootstrap.Modal(document.getElementById("modalMachineDiag"));
    modal.show();
  } catch (err) {
    showToast("Error", err.message, "danger");
  }
}

async function executeAutoRemediation() {
  const btn = document.getElementById("btnRemediate");
  if (btn) btn.disabled = true;
  showToast("Remediation Running", "Executing automated SCADA self-healing algorithms...");

  try {
    const res = await fetch(`${API_BASE}/data-quality/remediate?plant_id=${AppState.currentPlant}&user_role=${encodeURIComponent(AppState.currentRole)}`, {
      method: "POST"
    });
    if (!res.ok) throw new Error("Remediation failed");
    const r = await res.json();

    // Show banner with exact financial impact
    const card = document.getElementById("remediationResultCard");
    if (card) {
      card.style.display = "block";
      document.getElementById("remSavedUsd").innerText = `$${Number(r.billing_overstatement_eliminated_usd).toLocaleString()}`;
      document.getElementById("remSavedKwh").innerText = `${Number(r.kwh_overstatement_eliminated).toLocaleString()} kWh`;
      document.getElementById("remUnitsCount").innerText = r.unit_confusions_corrected;
      document.getElementById("remDupsCount").innerText = r.duplicates_quarantined;
    }

    showToast("Self-Healing Complete", `Eliminated $${r.billing_overstatement_eliminated_usd} in billing errors!`);
    await loadAllData();
  } catch (err) {
    showToast("Error", err.message, "danger");
  } finally {
    if (btn) btn.disabled = false;
  }
}

function toggleScadaSimulation() {
  const dot = document.getElementById("scadaPulseDot");
  const btn = document.getElementById("btnSimulateScada");

  if (AppState.isScadaSimulating) {
    clearInterval(AppState.scadaSimInterval);
    AppState.isScadaSimulating = false;
    if (dot) dot.style.display = "none";
    if (btn) btn.innerText = "Simulate SCADA Ticks";
    showToast("Simulator Paused", "SCADA telemetry simulation stopped.");
  } else {
    AppState.isScadaSimulating = true;
    if (dot) dot.style.display = "inline-block";
    if (btn) btn.innerText = "Stop Telemetry Ticks";
    showToast("Simulator Active", "Simulating live 15-minute telemetry interval pulses...");

    AppState.scadaSimInterval = setInterval(() => {
      // Simulate live random fluctuation on peak kW tile
      const currentPeak = AppState.summary ? AppState.summary.peak_demand_kw : 260.0;
      const jitter = (Math.random() * 4 - 2).toFixed(1);
      const simulatedVal = (parseFloat(currentPeak) + parseFloat(jitter)).toFixed(1);
      document.getElementById("kpiPeakDemand").innerText = `${simulatedVal} kW`;
    }, 2500);
  }
}

function toggleCopilot() {
  const drawer = document.getElementById("copilotDrawer");
  if (drawer) {
    drawer.classList.toggle("hidden");
  }
}

async function handleCopilotSubmit(e) {
  e.preventDefault();
  const input = document.getElementById("copilotInput");
  const query = input.value.trim();
  if (!query) return;

  input.value = "";
  appendCopilotMessage(query, "user");

  try {
    const res = await fetch(`${API_BASE}/copilot/query?query=${encodeURIComponent(query)}&plant_id=${AppState.currentPlant}`, {
      method: "POST"
    });
    if (!res.ok) throw new Error("Copilot response error");
    const data = await res.json();
    appendCopilotMessage(data.answer, "bot");
  } catch (err) {
    appendCopilotMessage("Error connecting to Industrial AI Copilot engine: " + err.message, "bot");
  }
}

function sendPresetQuery(q) {
  const input = document.getElementById("copilotInput");
  if (input) {
    input.value = q;
    document.getElementById("copilotForm").dispatchEvent(new Event("submit"));
  }
}

function appendCopilotMessage(text, sender) {
  const container = document.getElementById("copilotMessages");
  if (!container) return;

  const bubble = document.createElement("div");
  bubble.className = `copilot-bubble ${sender}`;
  bubble.innerHTML = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  container.appendChild(bubble);
  container.scrollTop = container.scrollHeight;
}

async function approveRecommendation(recId) {
  try {
    const res = await fetch(`${API_BASE}/recommendations/${recId}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_role: AppState.currentRole, reason: "Approved via EnergyIQ Executive Dashboard" })
    });
    if (!res.ok) throw new Error("Approval failed");
    showToast("Action Approved", `Recommendation ${recId} approved and logged.`);
    await fetchRecommendations();
    await fetchAuditLogs();
  } catch (err) {
    showToast("Error", err.message, "danger");
  }
}

async function rejectRecommendation(recId) {
  try {
    const res = await fetch(`${API_BASE}/recommendations/${recId}/reject`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_role: AppState.currentRole, reason: "Rejected during engineering review" })
    });
    if (!res.ok) throw new Error("Rejection failed");
    showToast("Action Rejected", `Recommendation ${recId} rejected.`);
    await fetchRecommendations();
    await fetchAuditLogs();
  } catch (err) {
    showToast("Error", err.message, "danger");
  }
}

async function acknowledgeAnomaly(anomId) {
  try {
    const res = await fetch(`${API_BASE}/anomalies/${anomId}/acknowledge`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_role: AppState.currentRole, notes: "Alert acknowledged by on-duty operator." })
    });
    if (!res.ok) throw new Error("Acknowledgement failed");
    showToast("Alert Acknowledged", `Anomaly ${anomId} status changed to ACKNOWLEDGED.`);
    await fetchAnomalies();
    await fetchAuditLogs();
  } catch (err) {
    showToast("Error", err.message, "danger");
  }
}

async function resolveAnomaly(anomId) {
  try {
    const res = await fetch(`${API_BASE}/anomalies/${anomId}/resolve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_role: AppState.currentRole, notes: "Physical verification complete; nominal power restored." })
    });
    if (!res.ok) throw new Error("Resolution failed");
    showToast("Anomaly Resolved", `Anomaly ${anomId} marked RESOLVED.`);
    await fetchAnomalies();
    await fetchAuditLogs();
  } catch (err) {
    showToast("Error", err.message, "danger");
  }
}

async function runAnalyticsPipeline() {
  const btn = document.getElementById("btnRunAnalytics");
  if (btn) btn.disabled = true;
  showToast("Analytics Running", "Executing hybrid anomaly detector & recommendation engine...");

  try {
    const res = await fetch(`${API_BASE}/analytics/run?plant_id=${AppState.currentPlant}`, { method: "POST" });
    if (!res.ok) throw new Error("Analytics run failed");
    const data = await res.json();
    showToast("Analytics Complete", `Found ${data.anomalies_detected} anomalies, synced ${data.recommendations_synchronized} recommendations.`);
    await loadAllData();
  } catch (err) {
    showToast("Error", err.message, "danger");
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function runEvaluationBenchmark() {
  const btn = document.getElementById("btnRunEval");
  if (btn) btn.disabled = true;
  showToast("Evaluation In Progress", "Evaluating ground-truth labels and integrity checks...");

  try {
    const res = await fetch(`${API_BASE}/analytics/evaluation?plant_id=${AppState.currentPlant}`);
    if (!res.ok) throw new Error("Evaluation failed");
    const report = await res.json();
    AppState.evaluation = report;
    renderEvaluationReport(report);
    showToast("Evaluation Finished", `Overall Status: ${report.overall_status} (F1: ${(report.benchmark_summary.overall_f1_score * 100).toFixed(1)}%)`);
  } catch (err) {
    showToast("Error", err.message, "danger");
  } finally {
    if (btn) btn.disabled = false;
  }
}

function renderEvaluationReport(r) {
  const container = document.getElementById("evaluationReportContainer");
  if (!container) return;

  const isPass = r.overall_status === "PASS";
  const bm = r.benchmark_summary;

  let html = `
    <div class="iq-card mb-4 border-${isPass ? 'success' : 'danger'}">
      <div class="d-flex justify-content-between align-items-center">
        <div>
          <h4 class="mb-1 fw-bold text-white">System Benchmark Evaluation Verdict</h4>
          <p class="text-muted small mb-0">Ground-truth validation across 5 industrial exception scenarios + PK/FK integrity</p>
        </div>
        <div>
          <span class="badge ${isPass ? 'badge-approved' : 'badge-rejected'} fs-4 px-3 py-2">
            ${isPass ? '<i class="bi bi-patch-check-fill"></i> ACCEPTANCE CRITERIA PASSED' : '<i class="bi bi-x-octagon-fill"></i> CRITERIA FAILED'}
          </span>
        </div>
      </div>
    </div>

    <div class="row g-3 mb-4">
      <div class="col-md-3">
        <div class="kpi-card" style="--card-accent: #10b981;">
          <div class="kpi-label">Overall Precision</div>
          <div class="kpi-val text-success">${(bm.overall_precision * 100).toFixed(1)}%</div>
          <div class="kpi-sub">TP: ${bm.true_positives} / FP: ${bm.false_positives}</div>
        </div>
      </div>
      <div class="col-md-3">
        <div class="kpi-card" style="--card-accent: #3b82f6;">
          <div class="kpi-label">Overall Recall</div>
          <div class="kpi-val text-primary">${(bm.overall_recall * 100).toFixed(1)}%</div>
          <div class="kpi-sub">FN: ${bm.false_negatives} missed</div>
        </div>
      </div>
      <div class="col-md-3">
        <div class="kpi-card" style="--card-accent: #00f2fe;">
          <div class="kpi-label">F1-Score Benchmark</div>
          <div class="kpi-val" style="color: #00f2fe;">${(bm.overall_f1_score * 100).toFixed(1)}%</div>
          <div class="kpi-sub">Target >= 90.0%</div>
        </div>
      </div>
      <div class="col-md-3">
        <div class="kpi-card" style="--card-accent: #8b5cf6;">
          <div class="kpi-label">Ground Truth Cases</div>
          <div class="kpi-val text-white">${bm.total_ground_truth_cases}</div>
          <div class="kpi-sub">Deterministic Seed 20261022</div>
        </div>
      </div>
    </div>

    <h5 class="fw-bold text-white mb-3">Anomaly Detection Performance by Scenario</h5>
    <div class="table-responsive mb-4">
      <table class="table table-custom">
        <thead>
          <tr>
            <th>Industrial Scenario</th>
            <th>Ground Truth</th>
            <th>Detected</th>
            <th>TP</th>
            <th>FP</th>
            <th>FN</th>
            <th>Precision</th>
            <th>Recall</th>
            <th>F1-Score</th>
            <th>Verdict</th>
          </tr>
        </thead>
        <tbody>
  `;

  for (const [name, sc] of Object.entries(r.scenario_evaluations)) {
    html += `
      <tr>
        <td class="fw-bold text-white">${name}</td>
        <td class="mono-cell">${sc.ground_truth_count}</td>
        <td class="mono-cell">${sc.detected_count}</td>
        <td class="mono-cell text-success">${sc.true_positives}</td>
        <td class="mono-cell text-warning">${sc.false_positives}</td>
        <td class="mono-cell text-danger">${sc.false_negatives}</td>
        <td class="mono-cell">${(sc.precision * 100).toFixed(1)}%</td>
        <td class="mono-cell">${(sc.recall * 100).toFixed(1)}%</td>
        <td class="mono-cell fw-bold text-info">${(sc.f1_score * 100).toFixed(1)}%</td>
        <td>
          <span class="badge ${sc.passed ? 'badge-low' : 'badge-critical'}">${sc.passed ? 'PASS' : 'FAIL'}</span>
        </td>
      </tr>
    `;
  }

  html += `
        </tbody>
      </table>
    </div>

    <h5 class="fw-bold text-white mb-3">Relational Integrity & Schema Validation</h5>
    <div class="table-responsive">
      <table class="table table-custom">
        <thead>
          <tr>
            <th>Integrity Check</th>
            <th>Criteria</th>
            <th>Result Status</th>
          </tr>
        </thead>
        <tbody>
  `;

  for (const [chk, val] of Object.entries(r.structural_integrity_checks)) {
    html += `
      <tr>
        <td class="mono-cell text-white">${chk}</td>
        <td class="text-muted small">${JSON.stringify(val)}</td>
        <td>
          <span class="badge ${val.passed ? 'badge-low' : 'badge-critical'}">${val.passed ? 'PASSED' : 'FAILED'}</span>
        </td>
      </tr>
    `;
  }

  html += `
        </tbody>
      </table>
    </div>
  `;

  container.innerHTML = html;
}

async function handleMaintenanceSubmit(e) {
  e.preventDefault();
  const machine_id = document.getElementById("maintMachineSelect").value;
  const event_type = document.getElementById("maintTypeSelect").value;
  const start_ts = document.getElementById("maintStartTs").value;
  const end_ts = document.getElementById("maintEndTs").value;
  const description = document.getElementById("maintDesc").value;
  const impact = document.getElementById("maintImpact").value;

  try {
    const res = await fetch(`${API_BASE}/maintenance/events?user_role=${encodeURIComponent(AppState.currentRole)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        plant_id: AppState.currentPlant,
        machine_id,
        event_type,
        start_ts,
        end_ts,
        description,
        impact
      })
    });
    if (!res.ok) throw new Error("Failed to record maintenance event");
    const data = await res.json();
    showToast("Maintenance Logged", `Work order ${data.maintenance_id} registered for ${machine_id}.`);

    const modal = bootstrap.Modal.getInstance(document.getElementById("modalMaintenance"));
    if (modal) modal.hide();
    await fetchAuditLogs();
  } catch (err) {
    showToast("Error", err.message, "danger");
  }
}

function exportData(entity, format) {
  const url = `${API_BASE}/export/${entity}/${format}`;
  window.open(url, "_blank");
  showToast("Export Initiated", `Downloading ${entity} as ${format.toUpperCase()}...`);
}

function showToast(title, msg, type = "info") {
  const container = document.getElementById("toastContainer");
  if (!container) return;

  const id = `toast-${Date.now()}`;
  const el = document.createElement("div");
  el.id = id;
  el.className = `toast align-items-center text-white bg-dark border border-${type === 'danger' ? 'danger' : 'info'} shadow-lg`;
  el.setAttribute("role", "alert");
  el.setAttribute("aria-live", "assertive");
  el.setAttribute("aria-atomic", "true");

  el.innerHTML = `
    <div class="d-flex">
      <div class="toast-body">
        <strong class="d-block ${type === 'danger' ? 'text-danger' : 'text-info'}">${title}</strong>
        ${msg}
      </div>
      <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
    </div>
  `;

  container.appendChild(el);
  const toast = new bootstrap.Toast(el, { delay: 4000 });
  toast.show();
  el.addEventListener("hidden.bs.toast", () => el.remove());
}

function showLoading(isLoading) {
  const spinner = document.getElementById("globalSpinner");
  if (spinner) {
    spinner.style.display = isLoading ? "inline-block" : "none";
  }
}
