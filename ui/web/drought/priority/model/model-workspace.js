(function () {
  const target = document.getElementById('model-configuration');
  const endpoint = '../../../api/drought/development/priority/model-configuration';
  const scenarioEndpoint = '../../../api/drought/development/priority/scenario-laboratory/cases';
  const months = ['January','February','March','April','May','June','July','August','September','October','November','December'];
  const esc = v => String(v == null ? '' : v).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const field = (name, value) => `<input name="${name}" value="${esc(value)}">`;
  const profiles = () => months.map((label, index) => ({month:index + 1,label,rainfall_window:index >= 5 && index <= 8 ? 'Current month + previous month':'Current month',rainfall_threshold:'Below 20th percentile',vegetation_role:index >= 4 && index <= 10 ? 'Core when baseline is valid':'Supporting context',water_use_role:index >= 4 && index <= 10 ? 'Core when baseline is valid':'Supporting context',outlook_horizon:'Next 1–3 months'}));
  const factors = () => [
    ['Rainfall condition','Observed stress','Seasonal percentile','Below 20th percentile → high stress',true],
    ['Vegetation (NDVI)','Observed stress','Seasonal anomaly','Below local baseline → stress signal',false],
    ['Crop water use','Observed stress','Dekadal anomaly','Below crop-season baseline → stress signal',false],
    ['Soil-water context','Supporting context','Relative wetness','Low wetness corroborates; does not rank alone',true],
    ['Population exposure','Exposure','Tabia decile','Upper deciles raise response relevance',true],
    ['Cropland exposure','Exposure','Tabia decile','Upper deciles raise agricultural relevance',true],
    ['Accessibility context','Planning constraint','Road + terrain context','Constrained access adds logistics attention',true],
    ['Seasonal outlook','Forward context','Woreda probability','Reviewed below-normal signal raises planning concern',false]
  ].map(([name,role,method,condition,enabled]) => ({name,role,method,condition,enabled}));
  const rules = () => [
    {priority:'Critical',condition:'Very high observed stress AND high cropland or population exposure AND adequate evidence',action:'Immediate verification and coordinated response planning'},
    {priority:'High',condition:'High observed stress AND elevated agricultural or population exposure',action:'Targeted verification and Woreda planning review'},
    {priority:'Moderate',condition:'Elevated stress OR high exposure with an adverse forward context',action:'Monitor closely and prepare contingency options'},
    {priority:'Watch',condition:'One adverse stress signal or incomplete corroboration',action:'Continue monitoring and verify evidence'},
    {priority:'Insufficient evidence',condition:'Required evidence is stale, incomplete, or unavailable',action:'Do not rank; resolve evidence gap'}
  ];
  function normalize(payload) {
    const row = payload.configuration, stored = row.configuration || {};
    return {version:row.version,active:row.active_for_review,horizon_months:stored.horizon_months || row.horizon_months || 3,
      monthly_profiles:Array.isArray(stored.monthly_profiles) && stored.monthly_profiles.length === 12 ? stored.monthly_profiles : profiles(),
      factors:Array.isArray(stored.factors) && stored.factors.length ? stored.factors : factors(),
      priority_rules:Array.isArray(stored.priority_rules) && stored.priority_rules.length ? stored.priority_rules : rules()};
  }
  function render(model) {
    target.innerHTML = `<div class="model-status"><span class="model-pill">${model.active ? 'ACTIVE FOR PRIORITY REVIEW' : 'SAVED DRAFT'}</span><span>Version ${esc(model.version)} · Tabia first, Woreda roll-up · next ${esc(model.horizon_months)} months</span></div>
      <div class="model-intro"><strong>How this works</strong><span>Period changes how each factor is interpreted. The priority runner will use the target month’s profile, then apply the factor conditions and priority rules below.</span></div>
      <form id="priority-model-form">
      <section class="model-section"><div class="model-section-heading"><h3>1. Decision window</h3><p>Target months use their own seasonal profile. A configuration is versioned when saved.</p></div><label class="model-field">Planning horizon <select name="horizon_months"><option value="1" ${model.horizon_months == 1 ? 'selected':''}>Next month</option><option value="2" ${model.horizon_months == 2 ? 'selected':''}>Next two months</option><option value="3" ${model.horizon_months == 3 ? 'selected':''}>Next three months</option></select></label></section>
      <section class="model-section"><div class="model-section-heading"><h3>2. Monthly seasonal profiles</h3><p>These settings make the same measured value mean different things at different times of year.</p></div><div class="model-table-wrap"><table class="model-table"><thead><tr><th>Target month</th><th>Rainfall window</th><th>Rainfall condition</th><th>NDVI role</th><th>Crop-water role</th><th>Outlook</th></tr></thead><tbody>${model.monthly_profiles.map((p,i) => `<tr data-profile="${i}"><td><strong>${esc(p.label || months[i])}</strong></td><td>${field('rainfall_window',p.rainfall_window)}</td><td>${field('rainfall_threshold',p.rainfall_threshold)}</td><td>${field('vegetation_role',p.vegetation_role)}</td><td>${field('water_use_role',p.water_use_role)}</td><td>${field('outlook_horizon',p.outlook_horizon)}</td></tr>`).join('')}</tbody></table></div></section>
      <section class="model-section"><div class="model-section-heading"><h3>3. Factor matrix</h3><p>Each factor has one job: stress, exposure, planning constraint, or forward context. This prevents double-counting.</p></div><div class="model-table-wrap"><table class="model-table"><thead><tr><th>Use</th><th>Factor</th><th>Role</th><th>Measure</th><th>If…then condition</th></tr></thead><tbody>${model.factors.map((f,i) => `<tr data-factor="${i}"><td><input type="checkbox" name="enabled" ${f.enabled ? 'checked':''} aria-label="Enable ${esc(f.name)}"></td><td>${field('name',f.name)}</td><td>${field('role',f.role)}</td><td>${field('method',f.method)}</td><td>${field('condition',f.condition)}</td></tr>`).join('')}</tbody></table></div></section>
      <section class="model-section"><div class="model-section-heading"><h3>4. Scenario Laboratory <span class="model-pill">SEPARATE · NOT SAVED</span></h3><p>Experimental discussion controls now live outside this save form, so no one can mistake them for a model setting.</p></div><p><a class="model-lab-link" href="../scenario/">Open the separate Scenario Laboratory</a></p></section>
      <section class="model-section"><div class="model-section-heading"><h3>5. Priority rules and planning cues</h3><p>The map must state why a Tabia is prioritized—not merely display a number.</p></div><div class="model-rules">${model.priority_rules.map((r,i) => `<article data-rule="${i}"><label>Priority class ${field('priority',r.priority)}</label><label>IF ${field('condition',r.condition)}</label><label>THEN ${field('action',r.action)}</label></article>`).join('')}</div></section>
      <section class="model-section"><div class="model-section-heading"><h3>6. Save a transparent draft</h3><p>Saving creates a new immutable version. It becomes the active configuration for the next draft Priority Review calculation, but never publishes a decision map automatically.</p></div><label class="model-field model-rationale">Rationale ${field('rationale','Seasonal factor matrix prepared for local expert review and historical calibration.')}</label><label class="model-checkbox"><input type="checkbox" name="activate" checked> Make this version active for Priority Review</label><div class="model-actions"><button type="submit">Save new draft version</button><span id="model-save-status" role="status"></span></div></section></form>`;
    document.getElementById('priority-model-form').addEventListener('submit', event => save(event, model));
  }
  const scenarioNumber = value => Number.isFinite(Number(value)) ? Number(value).toFixed(1) : 'unavailable';
  function scenarioFinding(caseData, settings) {
    const referenceYears = Math.min(Number(caseData.ndvi_reference_year_count), Number(caseData.wapor_reference_year_count));
    const rainfallMet = Number(caseData.rainfall_percentile) <= Number(settings.rainfall);
    const ndviMet = Number(caseData.ndvi_deviation_pct) <= Number(settings.ndvi);
    const waporMet = Number(caseData.wapor_deviation_pct) <= Number(settings.wapor);
    const supports = Number(ndviMet) + Number(waporMet);
    if (!Number.isFinite(referenceYears) || referenceYears < 6) return ['Insufficient reference evidence', 'A candidate reference has fewer than six valid years. The laboratory will not infer a signal.'];
    if (settings.confounder !== 'cleared') return ['Unresolved pending local confounder review', 'The evidence is displayed, but a possible conflict, displacement, irrigation, land-cover, pest, hail, or crop-calendar confounder has not been cleared by reviewers.'];
    if (rainfallMet && settings.logic === 'rainfall') return ['Rainfall-only discussion signal', 'The selected rainfall-only comparison deliberately makes no claim of biophysical corroboration. Investigate local context before drawing any conclusion.'];
    if (rainfallMet && ((settings.logic === 'both' && supports === 2) || (settings.logic === 'either' && supports >= 1))) return ['Corroborated observed land signal', 'The selected assumptions find a rainfall signal with the required biophysical context. This is not a priority class or a statement about households.'];
    if (rainfallMet && supports === 0) return ['Rainfall signal without corroboration', 'Investigate timing, irrigation, source uncertainty, crop stage, or other local explanations before drawing any conclusion.'];
    if (!rainfallMet && supports >= 1) return ['Biophysical divergence to review', 'Vegetation or water-use differs from its reference without the selected rainfall trigger. Do not average the indicators into a score.'];
    return ['No selected discussion trigger', 'The selected rules are not met for this case. This says nothing about household conditions or response need.'];
  }
  function renderScenarioLaboratory(payload) {
    const lab = document.getElementById('scenario-laboratory');
    if (!lab) return;
    const cases = payload.cases || [];
    if (!cases.length) { lab.innerHTML = '<p class="drought-unavailable">No retained candidate-review cases are available.</p>'; return; }
    lab.innerHTML = `<div class="scenario-lab-notice"><strong>Discussion-only guardrail.</strong> ${esc(payload.selection_note)} ${esc(payload.safeguard)}</div><div class="scenario-lab-grid"><label>Review case <select data-scenario-case>${cases.map((item,index) => `<option value="${index}">${esc(item.review_group)} — ${esc(item.tabia_name)} (${esc(item.woreda_name)})</option>`).join('')}</select></label><label>Rainfall trigger: bottom <output data-rainfall-output>20</output>%<input data-scenario-rainfall type="range" min="5" max="40" step="5" value="20"></label><label>NDVI corroboration at or below <output data-ndvi-output>-20</output>%<input data-scenario-ndvi type="range" min="-50" max="-5" step="5" value="-20"></label><label>WaPOR corroboration at or below <output data-wapor-output>-25</output>%<input data-scenario-wapor type="range" min="-60" max="-5" step="5" value="-25"></label><label>Agreement rule <select data-scenario-logic><option value="either">Rainfall + either NDVI or WaPOR</option><option value="both">Rainfall + both NDVI and WaPOR</option><option value="rainfall">Rainfall only (for comparison)</option></select></label><label>Local confounder review <select data-scenario-confounder><option value="unreviewed">Not reviewed — block interpretation</option><option value="flagged">Potential/known confounder — block interpretation</option><option value="cleared">No known confounder after reviewer check</option></select></label></div><div class="scenario-lab-observed" data-scenario-observed></div><div class="scenario-lab-result" data-scenario-result></div><p class="scenario-lab-footnote">NDVI and WaPOR are related biophysical evidence, not independent votes. Their apparent agreement may support a land-surface plausibility discussion only; it cannot establish food insecurity, response priority, or allocation.</p>`;
    const controls = {case:lab.querySelector('[data-scenario-case]'),rainfall:lab.querySelector('[data-scenario-rainfall]'),ndvi:lab.querySelector('[data-scenario-ndvi]'),wapor:lab.querySelector('[data-scenario-wapor]'),logic:lab.querySelector('[data-scenario-logic]'),confounder:lab.querySelector('[data-scenario-confounder]')};
    const update = () => {
      const item = cases[Number(controls.case.value)];
      const settings = {rainfall:controls.rainfall.value,ndvi:controls.ndvi.value,wapor:controls.wapor.value,logic:controls.logic.value,confounder:controls.confounder.value};
      lab.querySelector('[data-rainfall-output]').textContent = settings.rainfall;
      lab.querySelector('[data-ndvi-output]').textContent = settings.ndvi;
      lab.querySelector('[data-wapor-output]').textContent = settings.wapor;
      const [title, explanation] = scenarioFinding(item, settings);
      lab.querySelector('[data-scenario-observed]').innerHTML = `<strong>Observed August 2026 evidence</strong><span>Rainfall: ${scenarioNumber(item.rainfall_mm)} mm · ${scenarioNumber(item.rainfall_percentile)}th percentile</span><span>NDVI: ${scenarioNumber(item.ndvi_value)} · ${scenarioNumber(item.ndvi_deviation_pct)}% from candidate median (${esc(item.ndvi_reference_year_count)} valid years)</span><span>WaPOR T: ${scenarioNumber(item.wapor_value)} mm · ${scenarioNumber(item.wapor_deviation_pct)}% from candidate median (${esc(item.wapor_reference_year_count)} valid years)</span>`;
      lab.querySelector('[data-scenario-result]').innerHTML = `<strong>Scenario finding: ${esc(title)}</strong><span>${esc(explanation)}</span><small>Client-side only · no configuration change · no priority map recalculation</small>`;
    };
    Object.values(controls).forEach(control => control.addEventListener(control.tagName === 'INPUT' ? 'input' : 'change', update));
    update();
  }
  function loadScenarioLaboratory() {
    fetch(scenarioEndpoint,{cache:'no-store'}).then(response => response.ok ? response.json() : response.json().then(body => Promise.reject(new Error(body.detail || 'scenario evidence unavailable')))).then(renderScenarioLaboratory).catch(error => { const lab=document.getElementById('scenario-laboratory'); if (lab) lab.innerHTML=`<p class="drought-unavailable">Scenario Laboratory unavailable: ${esc(error.message)}.</p>`; });
  }
  function readRows(form, selector, checkbox) { return Array.from(form.querySelectorAll(selector)).map((row,index) => { const values = Object.fromEntries(Array.from(row.querySelectorAll('input:not([type=checkbox])')).map(el => [el.name,el.value])); if (checkbox) values.enabled = row.querySelector('[name=enabled]').checked; return values; }); }
  function save(event, model) {
    event.preventDefault(); const form = event.currentTarget, status = document.getElementById('model-save-status');
    const monthly_profiles = readRows(form,'[data-profile]').map((row,index) => ({month:index + 1,label:months[index],...row}));
    const configuration = {horizon_months:Number(form.horizon_months.value),monthly_profiles,factors:readRows(form,'[data-factor]',true),priority_rules:readRows(form,'[data-rule]'),safeguard:'No priority is published automatically. Incomplete evidence is labelled and capped by the runner.',output_contract:'Tabia explanation must show triggered conditions, inputs, evidence quality, and configuration version.',previous_configuration_version:model.version};
    status.textContent = 'Saving draft…';
    fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({purpose:'Transparent seasonal agricultural-stress and response-planning aid; not a food-security classification.',rationale:form.rationale.value,activate_for_review:form.activate.checked,configuration})})
      .then(response => response.ok ? response.json() : response.json().then(body => Promise.reject(new Error(body.detail || 'save failed'))))
      .then(() => window.location.reload()).catch(error => { status.textContent = `Could not save: ${error.message}`; });
  }
  fetch(endpoint,{cache:'no-store'}).then(r => r.ok ? r.json() : Promise.reject(new Error(`configuration unavailable (${r.status})`))).then(payload => render(normalize(payload))).catch(error => { target.innerHTML = `<p class="drought-unavailable">Model configuration unavailable: ${esc(error.message)}.</p>`; });
}());
