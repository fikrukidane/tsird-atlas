/* Production uses the same Atlas and DroughtDashboard components as development.
 * Only its data URLs are switched to the approved-release adapter. */
document.addEventListener('DOMContentLoaded', function () {
  initializeApplication('../data/atlas-registry.json?v=20260909b', {
    droughtWorkspace: true,
    droughtPublicMode: true,
    droughtDataUrl: '../api/drought/public/dashboard/overview',
    droughtObservedUrl: '../api/drought/public/dashboard/indicator/observed',
    droughtObservedRunsUrl: '../api/drought/public/dashboard/observed-rainfall/runs',
    droughtObservedRunBaseUrl: '../api/drought/public/dashboard/observed-rainfall/runs',
    droughtPreliminaryUrl: '../api/drought/public/dashboard/indicator/rapid',
    droughtNdviUrl: '../api/drought/public/dashboard/indicator/vegetation',
    droughtSwiUrl: '../api/drought/public/dashboard/indicator/soil_water',
    droughtLstUrl: '../api/drought/public/dashboard/indicator/thermal',
    droughtWaporUrl: '../api/drought/public/dashboard/indicator/water_use',
    droughtOutlookUrl: '../api/drought/public/dashboard/seasonal-outlook',
    droughtPriorityConfigurationUrl: '../api/drought/public/dashboard/model-configuration',
    droughtPriorityPreviewsUrl: '../api/drought/public/dashboard/priority/previews',
    droughtPriorityReplaysUrl: '../api/drought/public/dashboard/priority/replays',
    droughtFewsNetRunsUrl: '../api/drought/public/dashboard/fews-net/runs',
    droughtFewsNetRunBaseUrl: '../api/drought/public/dashboard/fews-net/runs',
    droughtModelReadinessUrl: '../api/drought/public/dashboard/model-readiness',
    droughtHistoryUrl: '../api/drought/public/dashboard/history',
    droughtEvidenceBaseUrl: '../api/drought/public/dashboard/evidence',
    droughtPublicGeometryUrl: '../api/drought/public/dashboard/geometry',
    droughtBoundaryUrl: '../api/boundaries'
  });
});
