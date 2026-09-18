document.addEventListener('DOMContentLoaded', function () {
  initializeApplication('../data/atlas-registry.json?v=20260909b', {
    droughtWorkspace: true,
    droughtDataUrl: '../data/drought-intelligence.dev.json',
    droughtObservedUrl: '../api/drought/development/observed-rainfall/latest?limit=100',
    droughtObservedRunsUrl: '../api/drought/development/observed-rainfall/runs?limit=36',
    droughtObservedRunBaseUrl: '../api/drought/development/observed-rainfall/runs',
    droughtPreliminaryUrl: '../api/drought/development/preliminary-rainfall/latest?limit=748',
    droughtNdviUrl: '../api/drought/development/ndvi/latest?limit=748',
    droughtSwiUrl: '../api/drought/development/swi/latest?limit=748',
    droughtLstUrl: '../api/drought/development/lst/latest?limit=748',
    droughtWaporUrl: '../api/drought/development/wapor/latest?limit=748',
    droughtOutlookUrl: '../api/drought/development/seasonal-outlook',
    droughtPriorityConfigurationUrl: '../api/drought/development/priority/model-configuration',
    droughtPriorityPreviewsUrl: '../api/drought/development/priority/calibration-previews',
    droughtModelReadinessUrl: '../api/drought/development/model-readiness',
    droughtHistoryUrl: '../api/drought/development/history',
    droughtEvidenceBaseUrl: '../api/drought/development/evidence',
    droughtExposureUrl: '../api/drought/development/exposure',
    droughtBoundaryUrl: '../api/boundaries'
  });
});
