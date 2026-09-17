(async function () {
  const target = document.getElementById('model-configuration');
  if (!target) return;
  try {
    const response = await fetch('../../../api/drought/public/dashboard/model-configuration', { cache: 'no-store' });
    const payload = await response.json();
    if (!response.ok) throw new Error('Model information is unavailable');
    target.innerHTML = `<div class="model-readiness model-readiness-warning"><strong>Read-only experimental method</strong><p>${payload.selection_note}</p></div><section class="model-section"><h3>What the released replay shows</h3><p>The Priority Review map displays stored C1–C4 retrospective draft codes alongside retained evidence and optional FEWS NET provider context. Those codes are an explanation aid for review, not a forecast, food-security classification, allocation recommendation or operational decision.</p></section><section class="model-section"><h3>What remains outside the public release</h3><p>Editable factors, candidate scoring, calibration changes, saved drafts, activation, publishing and pipeline controls remain in development. This prevents a public page from changing evidence or model state while allowing specialists to inspect the released material.</p></section><section class="model-section"><h3>How to contribute</h3><p>Use the Expert Evidence Review process to record local interpretation and confounders. Those inputs can inform a later, documented calibration discussion with Tigrayan collaborators.</p></section>`;
  } catch (error) {
    target.innerHTML = `<div class="model-readiness model-readiness-warning"><strong>Released model information is temporarily unavailable.</strong><p>Please return to Priority Review to inspect the retained evidence release.</p></div>`;
  }
}());
