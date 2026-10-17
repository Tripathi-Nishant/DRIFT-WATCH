let report = null;
const $ = (s) => document.querySelector(s);
async function loadReport() { const response = await fetch('/api/demo'); report = await response.json(); renderReport(); }
function renderReport() {
  const { summary, features } = report;
  $('#drifted-stat').textContent = summary.drifted_features;
  $('#quality-stat').textContent = `${summary.quality_score}%`;
  $('#quality-big').textContent = summary.quality_score;
  $('#nav-count').textContent = summary.drifted_features;
  $('#signals-table').innerHTML = `<table class="signal-table"><thead><tr><th>FEATURE</th><th>TYPE</th><th>DRIFT SCORE</th><th>STATUS</th></tr></thead><tbody>${features.slice(0, 4).map(f => `<tr><td>${f.name}</td><td>${f.kind}</td><td class="drift-num">${f.drift_score.toFixed(3)}</td><td><span class="signal-chip ${f.drift_score < .2 ? 'moderate' : ''}">${f.drifted ? 'Drift detected' : 'Within range'}</span></td></tr>`).join('')}</tbody></table>`;
  $('#monitor-list').innerHTML = [['Checkout conversion','Production · v2.4','status-red','Drift detected'],['Recommendation API','Production · v1.8','status-red','Drift detected'],['Churn predictor','Production · v3.1','status-green','Healthy'],['Fraud detection','Production · v1.2','status-red','Drift detected']].map((m,i) => `<div class="monitor"><span class="monitor-symbol ${i === 2 ? 'green' : 'red'}">${i === 2 ? '✓' : '⌁'}</span><div class="monitor-info"><strong>${m[0]}</strong><small>${m[1]}</small></div><span class="status ${m[2]}">${m[3]}</span></div>`).join('');
  const vals = [7, 14, 10, 24, 19, 31, Math.max(10, summary.drifted_features * 10)];
  $('#bars').innerHTML = vals.map((value, i) => `<div class="bar-group"><i class="bar monitor" style="height:${Math.min(95, value * 2.4)}%"></i><i class="bar drift" style="height:${Math.min(95, (i > 2 ? value * 1.25 : value * .5))}%"></i></div>`).join('');
}
$('#refresh').addEventListener('click', loadReport);
$('#new-monitor').addEventListener('click', () => alert('Monitor creation is ready for your reference and current CSV datasets. Connect the API endpoint /api/analyze to create a monitor.'));
document.addEventListener('click', (event) => { if (event.target.matches('.small')) { const blob = new Blob([JSON.stringify(report, null, 2)], {type:'application/json'}); const link = document.createElement('a'); link.href = URL.createObjectURL(blob); link.download = 'driftwatch-report.json'; link.click(); } });
loadReport();
