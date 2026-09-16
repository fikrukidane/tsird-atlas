(function () {
  const endpoint = '../../api/drought/development/control';
  const $ = (selector) => document.querySelector(selector);
  const safe = (value) => String(value == null ? '—' : value).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const bytes = (value) => value == null ? '—' : ['B', 'KB', 'MB', 'GB', 'TB'].reduce((text, unit, index) => Number(value) >= 1024 ** index ? `${(Number(value) / 1024 ** index).toFixed(index ? 1 : 0)} ${unit}` : text, '0 B');
  const stamp = (value) => value ? new Date(value).toLocaleString() : '—';
  const badge = (status) => `<span class="status status-${safe(status || 'inactive')}">${safe(status || 'unknown')}</span>`;
  const deliveryPlan = [
    ['1. Data engine', 'in_progress', 'Six safe local schedules are active: calendar-aware final CHIRPS, rapid CHIRPS, NDVI and SWI metadata probes, WaPOR’s provider-gated refresh, and monthly storage inventory. Thermal, Outlook, and forecast experiments remain blocked pending their separate data contracts.'],
    ['2. Static decision layers', 'in_progress', 'Terrain, soils, cropland, people, and ERAA/TRRA road context documented in Atlas with valid Tabia summaries where appropriate.'],
    ['3. Historical evidence workspace', 'ready', 'Ready for local acceptance: select final rain, Rapid rain, NDVI, SWI, LST, or WaPOR; view a dated Tabia-average map, compare two retained dates, and chart a selected Tabia.'],
    ['4. Priority-model draft', 'in_progress', 'Draft configuration and a January–August 2026 rainfall calibration review are available. Combined scoring, practitioner calibration, and an approved Outlook remain deliberately unavailable.'],
    ['5. Seasonal Outlook research', 'blocked', 'A reviewed provider release or a calibrated, passing Woreda-scale probability method. Current C3S August test is not suitable.'],
    ['6. Production package', 'not_started', 'Dev acceptance, Git review, release package, and low-impact file-transfer deployment plan.']
  ];

  function card(title, body) { return `<article class="control-card"><h3>${safe(title)}</h3>${body}</article>`; }

  function render(data) {
    const storage = data.storage || {};
    const capacity = storage.capacity || {};
    $('[data-banner]').className = 'control-banner';
    $('[data-banner]').textContent = `Development snapshot generated ${stamp(data.generated_at)}. Runner: ${data.runner && data.runner.status || 'unknown'}; active jobs: ${data.runner && data.runner.active_jobs || 0}.`;
    $('[data-summary]').innerHTML = [
      card('Managed drought storage', `<span class="control-value">${bytes(storage.total_managed_bytes)}</span><p>Known drought data only</p>`),
      card('Free local filesystem', `<span class="control-value">${bytes(storage.filesystem_free_bytes)}</span><p>Capacity available to the mounted development data store</p>`),
      card('Capacity safeguard', `${badge(capacity.status || 'unknown')}<p>${safe(capacity.free_percent)}% free</p><p>${safe(capacity.operator_action || 'No capacity classification is available.')}</p>`),
      card('Controlled workflows', `<span class="control-value">${(data.workflow_policy || []).length}</span><p>${(data.workflow_policy || []).filter(item => item.policy_state === 'active').length} active local schedules; the rest remain deliberately blocked or manual</p>`)
    ].join('');
    const receipts = data.provider_receipts || {};
    const c3sPilot = receipts.c3s_skill_pilot;
    const c3sLeadComparison = receipts.c3s_august_lead_comparison;
    const c3sMetrics = c3sPilot && c3sPilot.metrics;
    const c3sScore = (name) => c3sMetrics && c3sMetrics[name] && c3sMetrics[name].brier_skill_score;
    const c3sNegative = ['below', 'near', 'above'].every(name => Number(c3sScore(name)) < 0);
    const c3sPilotSummary = c3sPilot
      ? `${badge(c3sNegative ? 'blocked' : 'review_required')}<p>${c3sNegative ? 'Technical test only: not suitable for an Outlook map.' : 'Technical result requires scientific review before any Outlook decision.'}</p><p>August target · 1-month lead · 1993–2016</p><p>Below ${safe(c3sScore('below'))} · near ${safe(c3sScore('near'))} · above ${safe(c3sScore('above'))}</p><p>Negative scores mean worse than historical-normal rainfall.</p>`
      : '<p>No C3S skill-pilot result yet.</p>';
    const c3sLeadSummary = c3sLeadComparison && Array.isArray(c3sLeadComparison.cases)
      ? `${badge('blocked')}<p>August target comparison; no Outlook map is published.</p>${c3sLeadComparison.cases.map(item => {
          const metrics = item.metrics || {};
          const score = name => metrics[name] && metrics[name].brier_skill_score;
          return `<p>${safe(item.case)}<br>Below ${safe(score('below'))} · near ${safe(score('near'))} · above ${safe(score('above'))}</p>`;
        }).join('')}<p>All recorded scores are negative: each test was worse than historical-normal rainfall probabilities.</p>`
      : '<p>Two- and three-month lead comparison has not run yet.</p>';
    const waporArtifact = data.artifacts && data.artifacts.wapor;
    const baselineAvailability = receipts.seasonal_baseline_preflight;
    const baselinePilot = receipts.seasonal_baseline_pilot;
    const seasonalReferenceHistory = receipts.seasonal_reference_history;
    const seasonalReferenceBuild = receipts.seasonal_reference_build;
    const availabilitySummary = baselineAvailability && baselineAvailability.ndvi && baselineAvailability.wapor
      ? `NDVI: ${safe(baselineAvailability.ndvi.status).replaceAll('_', ' ')} for 2016–2025.<br>WaPOR: ${safe(baselineAvailability.wapor.status).replaceAll('_', ' ')}; matching records begin in 2018, so the shared candidate is 2018–2025.`
      : '';
    const readiness = data.model_readiness || {};
    const decision = readiness.decision || {};
    const baselinePreflight = readiness.seasonal_baseline_preflight || {};
    const retainedBaselines = baselinePreflight.retained_evidence || {};
    const retainedSummary = ['ndvi', 'wapor'].map(key => {
      const source = retainedBaselines[key] || {};
      return `${key.toUpperCase()}: ${safe(source.retained_months || 0)} retained month(s)${source.first_observation ? ` (${safe(source.first_observation)} to ${safe(source.latest_observation)})` : ''}`;
    }).join('<br>');
    const sourceStates = (readiness.sources || []).map(item => `${item.source_id}: ${item.state}`).join(' · ');
    $('[data-readiness]').innerHTML = readiness.status === 'unavailable'
      ? card('Readiness inspection', `${badge('unavailable')}<p>${safe(readiness.reason)}</p>`)
      : [
        card('Draft gate', `${badge(decision.status || 'unknown')}<p>Draft evidence matrix: ${decision.draft_matrix_allowed ? 'allowed' : 'blocked'}</p><p>Automated publication: disabled</p>`),
        card('Observed-stress ceiling', `<span class="control-value">${safe(decision.maximum_observed_stress_class || '—')}</span><p>Until fresh, baseline-normalized core evidence is available.</p>`),
        card('Boundary contract', `<span class="control-value">${safe(readiness.boundary && readiness.boundary.canonical_tabias)}</span><p>Canonical Tabias · ${safe(readiness.boundary && readiness.boundary.identity_version)}</p><p>${safe(readiness.boundary && readiness.boundary.duplicate_source_t8id_review_required)} repeated source T8IDs remain flagged for review; they are not excluded.</p>`),
        card('Evidence state', `<p>${safe(sourceStates || 'No source state available.')}</p><p>${safe((decision.reasons || [])[0] || '')}</p>`),
        card('Seasonal-baseline preflight', `${badge(baselinePreflight.status || 'unavailable')}<p>${retainedSummary}</p><p>${safe(baselinePreflight.next_safe_action || 'Baseline inventory unavailable.')}</p>`)
      ].join('');
    $('[data-roadmap]').innerHTML = deliveryPlan.map(([title, status, evidence]) =>
      card(title, `${badge(status)}<p>${safe(evidence)}</p>`)
    ).join('');
    $('[data-providers]').innerHTML = [
      card('CHIRPS final monthly rainfall', receipts.chirps_final ? `${badge(receipts.chirps_final.status)}<p>${safe(receipts.chirps_final.reason)}</p><p>Candidate: ${safe(receipts.chirps_final.analysis_year)}-${safe(String(receipts.chirps_final.month || '').padStart(2, '0'))}</p>` : '<p>No final-month discovery receipt yet.</p>'),
      card('CHIRPS rapid rainfall', receipts.chirps_rapid ? `${badge(receipts.chirps_rapid.status)}<p>${safe(receipts.chirps_rapid.reason)}</p><p>Latest pentad ends: ${safe(receipts.chirps_rapid.period && receipts.chirps_rapid.period.end_date)} · age: ${safe(receipts.chirps_rapid.age_days)} days</p>` : '<p>No probe receipt yet.</p>'),
      card('Copernicus vegetation (NDVI)', receipts.ndvi ? `${badge(receipts.ndvi.status)}<p>${safe(receipts.ndvi.reason)}</p><p>Observation: ${safe(receipts.ndvi.observation_timestamp)} · age: ${safe(receipts.ndvi.age_days)} days</p>` : '<p>No source-state receipt yet.</p>'),
      card('Copernicus soil water (SWI)', receipts.swi ? `${badge(receipts.swi.status)}<p>${safe(receipts.swi.reason)}</p><p>Observation: ${safe(receipts.swi.observation_timestamp)} · age: ${safe(receipts.swi.age_days)} days</p>` : '<p>No source-state receipt yet.</p>'),
      card('WaPOR crop water-use', receipts.wapor ? `${badge(receipts.wapor.status)}<p>${safe(receipts.wapor.reason)}</p><p>Provider period: ${safe(receipts.wapor.period_start)} to ${safe(receipts.wapor.period_end)}</p>` : '<p>No probe receipt yet.</p>'),
      card('Historical baseline availability', baselineAvailability ? `${badge(baselineAvailability.status)}<p>Candidate checked: ${safe(baselineAvailability.candidate_period)}</p><p>${availabilitySummary}</p><p>${safe(baselineAvailability.next_step)}</p>` : '<p>Not yet checked. This fixed manual preflight reads provider catalogue metadata only; it never downloads historical rasters.</p>'),
      card('Seasonal-baseline technical pilot', baselinePilot ? `${badge(baselinePilot.status)}<p>Fixed sample: ${safe((baselinePilot.fixed_years || []).join(', '))} · ${safe((baselinePilot.fixed_months || []).join(', '))}</p><p>${safe((baselinePilot.slots || []).length)} completed slot(s); baseline-pilot only: ${safe(baselinePilot.baseline_pilot_only)}</p><p>${safe(baselinePilot.next_step)}</p>` : '<p>Implemented but not run. It is manual, fixed to 2018/2021/2025 × February/August/November, and cannot calculate a baseline or alter Priority replay.</p>'),
      card('Seasonal-reference candidate history', seasonalReferenceHistory ? `${badge(seasonalReferenceHistory.status)}<p>Fixed candidate: ${safe(seasonalReferenceHistory.candidate_period)} · ${safe(seasonalReferenceHistory.slot_count)} monthly slots.</p><p>Candidate-only: ${safe(seasonalReferenceHistory.seasonal_reference_candidate_only)}. It cannot publish or change Priority replay.</p><p>${safe(seasonalReferenceHistory.next_step)}</p>` : '<p>Manual-only fixed 2018–2025 × all calendar months retrieval. It has no schedule and cannot change Priority replay.</p>'),
      card('Observed seasonal-reference build', seasonalReferenceBuild ? `${badge(seasonalReferenceBuild.status)}<p>${safe(seasonalReferenceBuild.reference_id)}</p><p>NDVI: ${safe(seasonalReferenceBuild.ndvi_reference_rows)} Tabia-month rows · WaPOR: ${safe(seasonalReferenceBuild.wapor_reference_rows)} Tabia-month rows.</p><p>Minimum valid years: ${safe(seasonalReferenceBuild.minimum_valid_years)}. Review required; not a forecast or classification.</p>` : '<p>Runs only after the fixed history completes. It creates a separate observed same-month reference, never a priority score.</p>'),
      card('Latest WaPOR artifact', waporArtifact ? `${badge(waporArtifact.status)}<p>${safe(waporArtifact.run_id)}</p><p>${safe(waporArtifact.source_period_start)} to ${safe(waporArtifact.source_period_end)}</p>` : '<p>No local WaPOR artifact found.</p>'),
      card('C3S rainfall outlook suitability', c3sPilotSummary),
      card('C3S August lead comparison', c3sLeadSummary)
    ].join('');
    $('[data-workflows]').innerHTML = (data.workflow_policy || []).map(item => card(item.label, `${badge(item.policy_state)}<p>${safe(item.cadence)}</p><p>Key: <code>${safe(item.key)}</code></p>`)).join('') || '<p>No workflow policy is available.</p>';
    const jobs = data.recent_jobs || [];
    $('[data-jobs]').innerHTML = jobs.length ? `<table><thead><tr><th>Workflow</th><th>Status</th><th>Requested</th><th>Finished</th><th>Result</th></tr></thead><tbody>${jobs.slice().reverse().map(job => `<tr><td>${safe(job.workflow)}<br><code>${safe(job.job_id)}</code></td><td>${badge(job.status)}</td><td>${safe(stamp(job.requested_at))}</td><td>${safe(stamp(job.finished_at))}</td><td>${safe(job.error || '—')}</td></tr>`).join('')}</tbody></table>` : '<p class="control-muted">No runner jobs are retained since the current runner start.</p>';
    $('[data-limitations]').innerHTML = (data.limitations || []).map(item => `<li>${safe(item)}</li>`).join('');
  }

  async function refresh() {
    $('[data-banner]').textContent = 'Refreshing control status…';
    try { const response = await fetch(endpoint, { cache: 'no-store' }); if (!response.ok) throw new Error(`HTTP ${response.status}`); render(await response.json()); }
    catch (error) { $('[data-banner]').className = 'control-banner is-error'; $('[data-banner]').textContent = `Control status is unavailable: ${error.message}.`; }
  }
  $('[data-refresh]').addEventListener('click', refresh);
  refresh();
}());
