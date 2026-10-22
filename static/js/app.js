/* ═══════════════════════════════════════════════════════════════
   StudyPredict – app.js
   Updated feature set:
     study_hours, sleep_hours, screen_time, sports_hours,
     other_activities, attendance, previous_marks
   ═══════════════════════════════════════════════════════════════ */

// ── Theme toggle ─────────────────────────────────────────────────────────────
const themeBtn = document.getElementById('themeToggle');
themeBtn.addEventListener('click', () => {
  const html = document.documentElement;
  html.dataset.theme = html.dataset.theme === 'dark' ? 'light' : 'dark';
  // Refresh chart colours after theme switch
  if (chartTime)   applyChartTheme(chartTime);
  if (chartGoal)   applyChartTheme(chartGoal);
  if (chartHabits) applyChartTheme(chartHabits);
});

// ── Nav highlight ─────────────────────────────────────────────────────────────
document.querySelectorAll('.nav-item').forEach(item => {
  item.addEventListener('click', () => {
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    item.classList.add('active');
  });
});

// ── Chart helpers ─────────────────────────────────────────────────────────────
function isDark() {
  return document.documentElement.dataset.theme !== 'light';
}
function legendColor()  { return isDark() ? '#9aa3c7' : '#5a6391'; }
function titleColor()   { return isDark() ? '#e9ecf8' : '#10162f'; }
function gridColor()    { return isDark() ? 'rgba(255,255,255,.05)' : 'rgba(20,30,80,.06)'; }

function applyChartTheme(chart) {
  const legend = chart.options.plugins.legend;
  if (legend && legend.labels) legend.labels.color = legendColor();
  const title  = chart.options.plugins.title;
  if (title) title.color = titleColor();
  const scales = chart.options.scales || {};
  Object.values(scales).forEach(ax => {
    if (ax.ticks) ax.ticks.color = legendColor();
    if (ax.grid)  ax.grid.color  = gridColor();
  });
  chart.update();
}

// ── Initialise charts (with placeholder data) ─────────────────────────────────
let chartTime, chartGoal, chartHabits;

function initCharts() {
  // ── Doughnut: daily time distribution ──────────────────────────────────────
  chartTime = new Chart(document.getElementById('chartTime').getContext('2d'), {
    type: 'doughnut',
    data: {
      labels: ['Study', 'Sleep', 'Screen Time', 'Sports', 'Other Activities'],
      datasets: [{
      data: [0, 0, 0, 0, 0],
        backgroundColor: ['#6366f1','#22d3ee','#f59e0b','#10b981','#a855f7'],
        borderWidth: 0
      }]
    },
    options: {
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'bottom', labels: { color: legendColor() } },
        title:  { display: true, text: 'Daily Time Distribution (hours)', color: titleColor() }
      }
    }
  });

  // ── Bar: predicted vs target ────────────────────────────────────────────────
  chartGoal = new Chart(document.getElementById('chartGoal').getContext('2d'), {
    type: 'bar',
    data: {
      labels: ['Predicted', 'Target'],
      datasets: [{
        label: 'Score (%)',
        data: [0, 80],
        backgroundColor: ['#6366f1', '#22d3ee'],
        borderRadius: 8
      }]
    },
    options: {
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        title:  { display: true, text: 'Predicted vs Target', color: titleColor() }
      },
      scales: {
        y: {
          beginAtZero: true, max: 100,
          ticks: { color: legendColor() },
          grid:  { color: gridColor()  }
        },
        x: { ticks: { color: legendColor() }, grid: { display: false } }
      }
    }
  });

  // ── Horizontal bar: habit breakdown ─────────────────────────────────────────
  chartHabits = new Chart(document.getElementById('chartHabits').getContext('2d'), {
    type: 'bar',
    data: {
      labels: ['Study Hours', 'Sleep Hours', 'Screen Time', 'Sports', 'Other Activities'],
      datasets: [
        {
          label: 'Your Hours',
          data: [0, 0, 0, 0, 0],
          backgroundColor: ['#6366f1','#22d3ee','#f59e0b','#10b981','#a855f7'],
          borderRadius: 6
        },
        {
          label: 'Recommended',
          data: [8, 8, 2, 1, 2],
          backgroundColor: 'rgba(255,255,255,.12)',
          borderRadius: 6
        }
      ]
    },
    options: {
      indexAxis: 'y',
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: legendColor() } },
        title:  { display: true, text: 'Your Habits vs Recommended', color: titleColor() }
      },
      scales: {
        x: {
          beginAtZero: true,
          ticks: { color: legendColor() },
          grid:  { color: gridColor()  }
        },
        y: { ticks: { color: legendColor() }, grid: { display: false } }
      }
    }
  });
}

initCharts();

// ── Counter animation ──────────────────────────────────────────────────────────
function animateCount(el, target, suffix = '') {
  const dur = 800;
  const t0  = performance.now();
  (function tick(t) {
    const p   = Math.min(1, (t - t0) / dur);
    const val = target * p;
    el.innerHTML = (Number.isInteger(target) ? Math.round(val) : val.toFixed(1)) + suffix;
    if (p < 1) requestAnimationFrame(tick);
  })(t0);
}

// ── Progress-bar animation ─────────────────────────────────────────────────────
function animateBar(id, pct) {
  const el = document.getElementById(id);
  if (!el) return;
  el.style.transition = 'width .8s ease';
  el.style.width = Math.min(100, Math.max(0, pct)) + '%';
}

// ── Form submit ───────────────────────────────────────────────────────────────
let lastResult = null;
const form    = document.getElementById('predictForm');
const btn     = document.getElementById('predictBtn');
const btnText = btn.querySelector('.btn-text');
const spinner = btn.querySelector('.spinner');

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  btnText.textContent = 'Analysing with AI…';
  spinner.hidden = false;
  btn.disabled   = true;

  const data = Object.fromEntries(new FormData(form).entries());

  try {
    const r      = await fetch('/predict', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    const result = await r.json();
    if (result.error) throw new Error(result.error);
    lastResult = result;
    renderResults(result, data);
  } catch (err) {
    alert('Prediction failed: ' + err.message);
  } finally {
    btnText.textContent = '⚡ Predict Performance';
    spinner.hidden = true;
    btn.disabled   = false;
  }
});

// ── Render all results ────────────────────────────────────────────────────────
function renderResults(r, inputs) {
  // ── Stat cards ──────────────────────────────────────────────────────────────
  animateCount(document.getElementById('statScore'), r.predicted_score);
  animateCount(document.getElementById('statSgpa'),  r.predicted_sgpa);
  document.getElementById('statProb').innerHTML = r.success_probability + '<small>%</small>';
  document.getElementById('statLevel').textContent = r.level;

  const badge = document.getElementById('statBadge');
  badge.className = 'badge ' + (
    r.level === 'Excellent'          ? 'good' :
    r.level === 'Average'            ? 'warn' : 'bad'
  );
  badge.textContent =
    r.level === 'Excellent' ? '🟢 On Track'      :
    r.level === 'Average'   ? '🟡 Keep Improving' : '🔴 Action Needed';

  // ── Doughnut: time distribution ─────────────────────────────────────────────
  chartTime.data.datasets[0].data = [
    +inputs.study_hours,
    +inputs.sleep_hours,
    +inputs.screen_time,
    +inputs.sports_hours,
    +inputs.other_activities
  ];
  chartTime.update();

  // ── Bar: predicted vs target ─────────────────────────────────────────────────
  chartGoal.data.datasets[0].data = [r.predicted_score, r.target];
  chartGoal.update();

  // ── Habits horizontal bar ────────────────────────────────────────────────────
  chartHabits.data.datasets[0].data = [
    +inputs.study_hours,
    +inputs.sleep_hours,
    +inputs.screen_time,
    +inputs.sports_hours,
    +inputs.other_activities
  ];
  chartHabits.update();

  // ── Progress bars ────────────────────────────────────────────────────────────
  // Goal progress
  animateBar('barGoal',   Math.min(100, (r.predicted_score / r.target) * 100));
  // Attendance
  animateBar('barAttend', +inputs.attendance);
  // Study hours vs 8 h target
  animateBar('barStudy',  Math.min(100, (+inputs.study_hours / 8) * 100));
  // Screen-time control: invert — 0 screen = 100% bar full (green), max screen = 0%
  // Show how much of 10h screen budget is *used* — warn bar grows as usage rises
  animateBar('barScreen', Math.min(100, (+inputs.screen_time / 10) * 100));

  // ── Goal analysis text ───────────────────────────────────────────────────────
  document.getElementById('goalAnalysis').textContent = r.goal_analysis;

  // ── Timetable ─────────────────────────────────────────────────────────────────
  document.getElementById('timetable-list').innerHTML =
    r.timetable.map(t => `
      <div class="tt-item">
        <span class="tt-time">${t.time}</span>
        <span>${t.activity}</span>
      </div>`).join('');

  // ── Recommendations ───────────────────────────────────────────────────────────
  document.getElementById('recos-list').innerHTML =
    r.recommendations.map(rec => `<div class="reco">✅ ${rec}</div>`).join('');

  // Enable PDF download
  document.getElementById('downloadBtn').disabled = false;
}

// ── PDF download ───────────────────────────────────────────────────────────────
document.getElementById('downloadBtn').addEventListener('click', async () => {
  if (!lastResult) return;
  try {
    const r = await fetch('/report', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(lastResult)
    });
    if (!r.ok) throw new Error('PDF generation not available.');
    const blob = await r.blob();
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href = url;
    a.download = 'performance_report.pdf';
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } catch (err) {
    alert(err.message);
  }
});
