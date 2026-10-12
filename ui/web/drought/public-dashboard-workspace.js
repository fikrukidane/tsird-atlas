/* The public workspace deliberately has a small, self-contained map shell.
 * It does not boot the Atlas layer catalogue, TOC, or GetFeatureInfo system:
 * public retained evidence is drawn from versioned release assets by
 * DroughtDashboard, and loading unrelated WMS layers delays first use. */
const PUBLIC_DROUGHT_ATLAS = {
  canonical_crs: 'EPSG:4326', view_crs: 'EPSG:3857',
  center: [38.0, 13.6], zoom: 10, extent: [36.3, 12.2, 40.3, 14.9]
};

function addPublicDroughtToolbar(map) {
  HighlightOverlay.init(map);
  const toolbar = document.createElement('div');
  toolbar.className = 'tsird-phase3-toolbar';
  map.getViewport().appendChild(toolbar);
  new SearchControl(toolbar, map);
  const full = document.createElement('button');
  full.className = 'tsird-toolbar-btn';
  full.title = 'Zoom to full Tigray extent';
  full.textContent = '⛶ Full';
  full.addEventListener('click', () => {
    map.getView().fit(ol.proj.transformExtent(PUBLIC_DROUGHT_ATLAS.extent, 'EPSG:4326', 'EPSG:3857'), {
      padding: [40, 40, 40, 40], duration: 400
    });
    HighlightOverlay.clear();
  });
  toolbar.appendChild(full);
}

async function bootPublicDroughtWorkspace() {
  const mapController = new MapController('map', PUBLIC_DROUGHT_ATLAS, '../ogc');
  mapController.initialize();
  // A narrow test hook lets the committed browser harness select a real
  // rendered Tabia instead of relying on a viewport-specific screen offset.
  // It contains no evidence values and is not used by application behavior.
  window.TSIRD_PUBLIC_DROUGHT_MAP = mapController.map;
  mapController.addLayer(new ol.layer.Tile({ source: new ol.source.OSM(), zIndex: 0 }));
  addPublicDroughtToolbar(mapController.map);
  const dashboard = new DroughtDashboard(mapController.map, {
    publicMode: true,
    dataUrl: '../api/drought/public/dashboard/overview',
    observedUrl: '../api/drought/public/dashboard/indicator/observed',
    observedRunsUrl: '../api/drought/public/dashboard/observed-rainfall/runs',
    observedRunBaseUrl: '../api/drought/public/dashboard/observed-rainfall/runs',
    preliminaryUrl: '../api/drought/public/dashboard/indicator/rapid',
    ndviUrl: '../api/drought/public/dashboard/indicator/vegetation',
    swiUrl: '../api/drought/public/dashboard/indicator/soil_water',
    lstUrl: '../api/drought/public/dashboard/indicator/thermal',
    waporUrl: '../api/drought/public/dashboard/indicator/water_use',
    outlookUrl: '../api/drought/public/dashboard/seasonal-outlook',
    priorityConfigurationUrl: '../api/drought/public/dashboard/model-configuration',
    priorityPreviewsUrl: '../api/drought/public/dashboard/priority/previews',
    priorityReplaysUrl: '../api/drought/public/dashboard/priority/replays',
    fewsNetRunsUrl: '../api/drought/public/dashboard/fews-net/runs',
    fewsNetRunBaseUrl: '../api/drought/public/dashboard/fews-net/runs',
    modelReadinessUrl: '../api/drought/public/dashboard/model-readiness',
    historyUrl: '../api/drought/public/dashboard/history',
    evidenceBaseUrl: '../api/drought/public/dashboard/evidence',
    exposureUrl: '../api/drought/public/dashboard/exposure',
    publicGeometryUrl: '../api/drought/public/dashboard/geometry',
    boundaryUrl: '../api/boundaries',
    wmsBaseUrl: '../ogc'
  });
  await dashboard.initialize();
}

// The overlay is host-mounted in production. Depending on cache/network timing,
// this small bootstrap can load after DOMContentLoaded. Start immediately in
// that case instead of leaving the shared Atlas shell without its dashboard.
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', bootPublicDroughtWorkspace, { once: true });
} else {
  bootPublicDroughtWorkspace();
}
