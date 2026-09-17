(function () {
  'use strict';
  const target = document.querySelector('[data-public-method]');
  const kind = document.body.dataset.publicMethod;
  const api = '../../../api/drought/public/release';
  const copy = kind === 'scenario' ? {
    title: 'Scenario Laboratory — candidate review',
    purpose: 'This page explains the public boundary for the 16-case candidate-review method. The method supports structured expert discussion; it does not validate the model, create a forecast, or change a released replay.',
    points: ['Review retained evidence and local knowledge together.', 'Record uncertainty, access, irrigation, displacement and other local confounders before interpreting a case.', 'Treat agreement between indicators as a discussion signal, never as an automated finding.', 'Keep any reviewer submissions and case-level comments in the controlled expert-review process, not in this public release.']
  } : {
    title: 'Model information',
    purpose: 'The public release describes the evidence boundary, not an active decision model. Retrospective C1–C4 codes are stored, neutral replay codes and must not be used as a priority, allocation, or food-security classification.',
    points: ['Indicators remain separate: rainfall, preliminary rainfall, vegetation, soil water, thermal and water-use context are not combined here.', 'FEWS NET remains provider-native context; no class is transferred to a Tabia.', 'Any future calibration requires named practitioner review and a documented decision before a new experimental draft can be prepared.', 'Pipeline configuration, scoring controls, raw source inputs and n8n status remain development-only.']
  };
  function esc(value) { return String(value == null ? '—' : value).replace(/[&<>'"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' })[c]); }
  async function load() {
    let state = 'No approved public release is available yet.';
    try { const response = await fetch(api, { cache: 'no-store' }); if (response.ok) { const release = await response.json(); state = `Approved public release ${release.release_id}. ${release.public_scope}`; } else if (response.status !== 404) state = `Release metadata returned ${response.status}.`; }
    catch (error) { state = 'Release metadata cannot be read right now.'; }
    target.innerHTML = `<section class="public-method-card"><h1>${esc(copy.title)}</h1><div class="public-drought-banner">${esc(state)}</div><p>${esc(copy.purpose)}</p><h2>What participants should understand</h2><ul>${copy.points.map(point => `<li>${esc(point)}</li>`).join('')}</ul><p class="public-drought-footnote">For the released map evidence, use <a href="../../release/">Retrospective Evidence Replay</a>. For the approved public conditions summary, use <a href="../../">Drought Intelligence</a>.</p></section>`;
  }
  load();
}());
