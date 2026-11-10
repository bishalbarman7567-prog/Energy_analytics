// EnergyIQ - High-Performance Chart.js Visualizations

let chartDaily = null;
let chartHourly = null;
let chartMachines = null;
let chartTariffs = null;
let chartWeather = null;
let chartForecast = null;
let chartMachineDiag = null;

// Chart.js Theme Defaults for Industrial Dark Mode
Chart.defaults.color = "#9ca3af";
Chart.defaults.borderColor = "rgba(255, 255, 255, 0.08)";
Chart.defaults.font.family = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';

function renderDailyTrendChart(canvasId, dailyData) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;

  if (chartDaily) chartDaily.destroy();

  chartDaily = new Chart(ctx, {
    type: "line",
    data: {
      labels: dailyData.labels,
      datasets: [
        {
          label: "Total Daily Energy (kWh)",
          data: dailyData.total_kwh,
          borderColor: "#00f2fe",
          backgroundColor: "rgba(0, 242, 254, 0.08)",
          fill: true,
          tension: 0.25,
          borderWidth: 2,
          pointRadius: 1,
          yAxisID: "y"
        },
        {
          label: "Idle Energy Waste (kWh)",
          data: dailyData.idle_kwh,
          borderColor: "#f59e0b",
          backgroundColor: "transparent",
          borderDash: [4, 4],
          borderWidth: 1.5,
          pointRadius: 0,
          tension: 0.25,
          yAxisID: "y"
        },
        {
          label: "Peak Demand (kW)",
          data: dailyData.peak_kw,
          borderColor: "#ef4444",
          backgroundColor: "transparent",
          borderWidth: 1.5,
          pointRadius: 1,
          yAxisID: "y1"
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { position: "top", labels: { boxWidth: 12, font: { size: 11 } } },
        tooltip: {
          backgroundColor: "rgba(17, 24, 39, 0.95)",
          titleColor: "#ffffff",
          bodyColor: "#e5e7eb",
          borderColor: "rgba(255, 255, 255, 0.15)",
          borderWidth: 1
        }
      },
      scales: {
        x: { grid: { display: false }, ticks: { maxTicksLimit: 12, font: { size: 10 } } },
        y: {
          type: "linear",
          display: true,
          position: "left",
          title: { display: true, text: "Energy (kWh)", color: "#00f2fe", font: { size: 11 } },
          grid: { color: "rgba(255, 255, 255, 0.05)" }
        },
        y1: {
          type: "linear",
          display: true,
          position: "right",
          title: { display: true, text: "Peak Demand (kW)", color: "#ef4444", font: { size: 11 } },
          grid: { drawOnChartArea: false }
        }
      }
    }
  });
}

function renderHourlyProfileChart(canvasId, hourlyData) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;

  if (chartHourly) chartHourly.destroy();

  chartHourly = new Chart(ctx, {
    type: "bar",
    data: {
      labels: hourlyData.labels,
      datasets: [
        {
          type: "line",
          label: "Avg Power Demand (kW)",
          data: hourlyData.avg_power_kw,
          borderColor: "#38bdf8",
          backgroundColor: "rgba(56, 189, 248, 0.12)",
          fill: true,
          tension: 0.3,
          borderWidth: 2,
          yAxisID: "y"
        },
        {
          type: "bar",
          label: "Peak Tariff Window (kWh)",
          data: hourlyData.peak_window_kwh,
          backgroundColor: "rgba(239, 68, 68, 0.4)",
          borderColor: "#ef4444",
          borderWidth: 1,
          yAxisID: "y1"
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: "top", labels: { boxWidth: 12, font: { size: 11 } } }
      },
      scales: {
        x: { grid: { display: false } },
        y: {
          title: { display: true, text: "Power (kW)", color: "#38bdf8" },
          grid: { color: "rgba(255, 255, 255, 0.05)" }
        },
        y1: {
          position: "right",
          title: { display: true, text: "Peak Window (kWh)", color: "#ef4444" },
          grid: { drawOnChartArea: false }
        }
      }
    }
  });
}

function renderMachineBreakdownChart(canvasId, machinesData) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;

  if (chartMachines) chartMachines.destroy();

  const labels = machinesData.map(m => m.machine_name);
  const productiveKwh = machinesData.map(m => Math.max(0, m.total_kwh - m.idle_kwh));
  const idleKwh = machinesData.map(m => m.idle_kwh);

  chartMachines = new Chart(ctx, {
    type: "bar",
    data: {
      labels: labels,
      datasets: [
        {
          label: "Productive Energy (kWh)",
          data: productiveKwh,
          backgroundColor: "#3b82f6",
          borderRadius: 4
        },
        {
          label: "Idle Waste (kWh)",
          data: idleKwh,
          backgroundColor: "#f59e0b",
          borderRadius: 4
        }
      ]
    },
    options: {
      indexAxis: "y",
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          stacked: true,
          title: { display: true, text: "Energy (kWh)" },
          grid: { color: "rgba(255, 255, 255, 0.05)" }
        },
        y: {
          stacked: true,
          grid: { display: false },
          ticks: { font: { size: 10 } }
        }
      },
      plugins: {
        legend: { position: "top", labels: { boxWidth: 12, font: { size: 11 } } }
      }
    }
  });
}

function renderTariffDonutChart(canvasId, tariffData) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;

  if (chartTariffs) chartTariffs.destroy();

  const labels = tariffData.map(t => `${t.tariff_name} ($${t.cost_usd.toLocaleString()})`);
  const values = tariffData.map(t => t.cost_usd);
  const colors = ["#ef4444", "#f59e0b", "#10b981", "#3b82f6"];

  chartTariffs = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: labels,
      datasets: [
        {
          data: values,
          backgroundColor: colors.slice(0, labels.length),
          borderColor: "#111827",
          borderWidth: 2
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: "right", labels: { boxWidth: 12, font: { size: 11 } } }
      },
      cutout: "65%"
    }
  });
}

function renderWeatherCorrelationChart(canvasId, weatherData) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;

  if (chartWeather) chartWeather.destroy();

  const labels = weatherData.map(w => w.temp_bucket);
  const avgKw = weatherData.map(w => w.avg_power_kw);

  chartWeather = new Chart(ctx, {
    type: "bar",
    data: {
      labels: labels,
      datasets: [
        {
          label: "Average Plant Power (kW)",
          data: avgKw,
          backgroundColor: "rgba(16, 185, 129, 0.4)",
          borderColor: "#10b981",
          borderWidth: 1.5,
          borderRadius: 6
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { grid: { display: false } },
        y: {
          title: { display: true, text: "Power (kW)" },
          grid: { color: "rgba(255, 255, 255, 0.05)" }
        }
      },
      plugins: {
        legend: { position: "top", labels: { boxWidth: 12 } }
      }
    }
  });
}

function renderForecastChart(canvasId, forecastData) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;

  if (chartForecast) chartForecast.destroy();

  const labels = forecastData.intervals.map(p => p.hour_label);
  const projectedKw = forecastData.intervals.map(p => p.projected_kw);
  const upperBound = forecastData.intervals.map(p => p.upper_bound_kw);
  const threshold = Array(labels.length).fill(forecastData.demand_alert_threshold_kw);

  chartForecast = new Chart(ctx, {
    type: "line",
    data: {
      labels: labels,
      datasets: [
        {
          label: "Projected Demand (kW)",
          data: projectedKw,
          borderColor: "#00f2fe",
          backgroundColor: "rgba(0, 242, 254, 0.12)",
          fill: true,
          tension: 0.35,
          borderWidth: 2,
          pointRadius: 1
        },
        {
          label: "Upper Bound (+18%)",
          data: upperBound,
          borderColor: "rgba(56, 189, 248, 0.4)",
          borderDash: [3, 3],
          pointRadius: 0,
          fill: false,
          borderWidth: 1
        },
        {
          label: "Peak Demand Alert Limit (220 kW)",
          data: threshold,
          borderColor: "#ef4444",
          borderDash: [6, 4],
          borderWidth: 1.5,
          pointRadius: 0,
          fill: false
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { ticks: { maxTicksLimit: 12, font: { size: 10 } }, grid: { display: false } },
        y: {
          title: { display: true, text: "Projected Power (kW)", color: "#00f2fe" },
          grid: { color: "rgba(255, 255, 255, 0.05)" }
        }
      },
      plugins: {
        legend: { position: "top", labels: { boxWidth: 12, font: { size: 11 } } }
      }
    }
  });
}

function renderMachineDiagnosticChart(canvasId, hourlyProfile) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;

  if (chartMachineDiag) chartMachineDiag.destroy();

  chartMachineDiag = new Chart(ctx, {
    type: "bar",
    data: {
      labels: hourlyProfile.map(h => h.hour),
      datasets: [
        {
          label: "Asset Diurnal Power Profile (kW)",
          data: hourlyProfile.map(h => h.kw),
          backgroundColor: "rgba(59, 130, 246, 0.4)",
          borderColor: "#3b82f6",
          borderWidth: 1.5,
          borderRadius: 4
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { grid: { display: false } },
        y: {
          title: { display: true, text: "Average Power (kW)" },
          grid: { color: "rgba(255, 255, 255, 0.05)" }
        }
      },
      plugins: {
        legend: { position: "top", labels: { boxWidth: 12 } }
      }
    }
  });
}
