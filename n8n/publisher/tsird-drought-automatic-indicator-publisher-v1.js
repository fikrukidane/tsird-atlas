#!/usr/bin/env node
/*
 * Fixed-purpose automatic publisher for retained TSIRD indicator evidence.
 * It deliberately accepts only a verified VPS host.  All API paths, raster
 * names, local staging paths, SSH identities and remote action are fixed.
 */
"use strict";

const childProcess = require("child_process");
const crypto = require("crypto");
const fs = require("fs");
const os = require("os");
const path = require("path");

const API_BASE = "http://tsird-edge:8080";
const STAGING_ROOT = "/home/node/.n8n/tsird-drought-indicator-staging";
const NATIVE_ROOT = "/opt/tsird-drought-native-rasters";
const KEY_ROOT = "/home/node/.n8n/tsird-drought-publisher-keys";
const UPLOAD_USER = "tsird-release-upload";
const ACTIVATE_USER = "tsird-release-activate";
const INDICATORS = {
  observed: "/map/api/drought/development/observed-rainfall/latest?limit=748",
  rapid: "/map/api/drought/development/preliminary-rainfall/latest?limit=748",
  vegetation: "/map/api/drought/development/ndvi/latest?limit=748",
  soil_water: "/map/api/drought/development/swi/latest?limit=748",
  thermal: "/map/api/drought/development/lst/latest?limit=748",
  water_use: "/map/api/drought/development/wapor/latest?limit=748",
};
const RASTERS = [
  ["native-raster-chirps", "chirps-current-rainfall.tif", "TSIRD display-ready CHIRPS final rainfall native grid", "observed"],
  ["native-raster-rapid", "chirps-rapid-rainfall.tif", "TSIRD display-ready CHIRPS preliminary rainfall native grid", "rapid"],
  ["native-raster-ndvi", "ndvi-current.tif", "TSIRD display-ready Copernicus NDVI native grid", "vegetation"],
  ["native-raster-swi", "swi040-current.tif", "TSIRD display-ready Copernicus SWI-040 native grid", "soil_water"],
  ["native-raster-lst", "lst-current.tif", "TSIRD display-ready Copernicus LST native grid", "thermal"],
  ["native-raster-wapor", "wapor-transpiration-current.tif", "TSIRD display-ready FAO WaPOR transpiration native grid", "water_use"],
];
const SUMMARY_FIELDS = {
  observed: ["tsird_tabia_id", "tabia_name_en", "woreda_name_en", "rainfall_mm", "baseline_median_mm", "percentile", "condition_class", "coverage_pct", "quality_status"],
  rapid: ["tsird_tabia_id", "tabia_name_en", "woreda_name_en", "rainfall_mm", "baseline_median_mm", "provisional_percentile", "comparison_status", "coverage_pct", "quality_status"],
  vegetation: ["tsird_tabia_id", "tabia_name_en", "woreda_name_en", "ndvi_mean", "ndvi_median", "coverage_pct", "quality_status"],
  soil_water: ["tsird_tabia_id", "tabia_name_en", "woreda_name_en", "swi010_mean", "swi040_mean", "swi100_mean", "coverage_pct", "quality_status"],
  thermal: ["tsird_tabia_id", "tabia_name_en", "woreda_name_en", "lst_c_mean", "errorbar_c_mean", "coverage_pct", "quality_status"],
  water_use: ["tsird_tabia_id", "tabia_name_en", "woreda_name_en", "transpiration_mm", "aeti_mm", "coverage_pct", "quality_status"],
};
const HISTORY_SOURCES = ["rapid", "ndvi", "swi", "lst", "wapor"];
const HISTORY_FIELDS = ["tsird_tabia_id", "value", "baseline_median_mm", "percentile", "comparison_status", "coverage_pct", "quality_status", "reference_median", "reference_deviation_pct", "reference_year_count", "reference_status"];

const now = () => new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
// Match the VPS forced-command contract: ISO date separators remain while
// time colons are removed for a filesystem-safe identifier.
const compactId = () => now().replace(/:/g, "").replace("Z", "Z-indicators");
const sha256 = (filename) => crypto.createHash("sha256").update(fs.readFileSync(filename)).digest("hex");
const jsonBytes = (data) => Buffer.from(`${JSON.stringify(data)}\n`, "utf8");
const writeJson = (filename, data) => { const bytes = jsonBytes(data); fs.writeFileSync(filename, bytes); return [bytes.length, sha256(filename)]; };
const fail = (message) => { throw new Error(message); };
function windowFor(run) {
  const start = run.observation_start || run.source_period_start || run.period_start || run.source_latest_month;
  const end = run.observation_end || run.source_period_end || run.period_end || run.source_latest_month;
  if (typeof start !== "string" || typeof end !== "string") fail("indicator run lacks a source-observation window");
  return [start.slice(0, 10), end.slice(0, 10)];
}
function asset(id, kind, relativePath, size, checksum, source, start, end, version, boundary) {
  return { asset_id:id, kind, relative_path:relativePath, byte_size:size, sha256:checksum, source,
    source_observation_start:start, source_observation_end:end, retrieved_at:now(), processing_version:version,
    quality_state:"validated", interpretation_boundary:boundary };
}
async function getJson(endpoint) {
  const response = await fetch(`${API_BASE}${endpoint}`, { signal: AbortSignal.timeout(30000) });
  if (!response.ok) fail(`development API ${endpoint} returned HTTP ${response.status}`);
  const payload = await response.json();
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) fail(`development API ${endpoint} is not an object`);
  return payload;
}
function usable(payload, name) {
  const run = payload.run;
  const rows = name === "observed" ? payload.conditions : payload.summaries;
  if (!run || typeof run !== "object" || !Array.isArray(rows) || !rows.length) fail(`${name} has no complete retained Tabia evidence`);
  if (["failed", "unavailable"].includes(String(run.status || "").toLowerCase())) fail(`${name} source state is not publishable`);
  if (!rows.some((row) => row && ["ok", "validated"].includes(String(row.quality_status || "").toLowerCase()) &&
    (row.coverage_pct == null || Number(row.coverage_pct) >= 90))) fail(`${name} contains no quality-approved Tabia summaries`);
}
function publicWorkspace(payloads) {
  const indicators = {};
  for (const [name, payload] of Object.entries(payloads)) {
    const run = payload.run;
    const rows = name === "observed" ? payload.conditions : payload.summaries;
    const publicRun = {};
    for (const key of ["run_id", "source_product", "source_version", "status", "analysis_year", "season_months", "period_start", "period_end", "observation_start", "observation_end", "source_period_start", "source_period_end", "native_resolution"]) if (run[key] != null) publicRun[key] = run[key];
    indicators[name] = { run: publicRun, summaries: rows.filter((row) => row && typeof row === "object").map((row) => {
      const safe = {}; for (const field of SUMMARY_FIELDS[name]) if (Object.hasOwn(row, field)) safe[field] = row[field]; return safe;
    })};
  }
  return { schema_version:"tsird-public-drought-workspace/v1",
    interpretation_boundary:"Approved retained indicator summaries only. They are separate evidence views, not a combined drought class, food-security classification, forecast, allocation recommendation, or operational decision.", indicators };
}
const safeSuffix = (value) => String(value).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
function observedIndex(payload) {
  if (!Array.isArray(payload.runs)) fail("observed rainfall snapshot index is invalid");
  const fields = ["run_id", "source_product", "source_version", "analysis_year", "season_months", "baseline_year_start", "baseline_year_end", "source_latest_month", "record_count", "usable_count"];
  return {schema_version:"tsird-public-observed-rainfall-runs/v1", selection_note:"Historical selections are retained observations, not forecasts or model backtests.", runs:payload.runs.filter((run) => run && typeof run === "object").map((run) => { const safe={}; for (const field of fields) if (run[field] != null) safe[field]=run[field]; return safe; })};
}
function observedSnapshot(payload) {
  if (!payload.run || !Array.isArray(payload.conditions)) fail("observed rainfall snapshot is invalid");
  const run = {}; for (const field of ["run_id", "source_product", "source_version", "status", "analysis_year", "season_months", "baseline_year_start", "baseline_year_end", "source_latest_month", "observation_start", "observation_end", "native_resolution"]) if (payload.run[field] != null) run[field]=payload.run[field];
  return {schema_version:"tsird-public-observed-rainfall/v1", snapshot_kind:"archived_observation", run, artifact:{native_resolution:run.native_resolution || "Tabia summary"}, conditions:payload.conditions.filter((row) => row && typeof row === "object").map((row) => { const safe={}; for (const field of SUMMARY_FIELDS.observed) if (Object.hasOwn(row,field)) safe[field]=row[field]; return safe; })};
}
function historyIndex(source, payload) {
  if (!Array.isArray(payload.runs)) fail(`${source} evidence index is invalid`);
  const fields = ["run_id", "evidence_kind", "observation_start", "observation_end", "native_resolution", "status", "quality_summary"];
  return {schema_version:"tsird-public-evidence-runs/v1", indicator:source, selection_note:"Retained source observations only; a selected date does not create a forecast, class, or priority result.", runs:payload.runs.filter((run) => run && typeof run === "object").map((run) => { const safe={}; for (const field of fields) if (run[field] != null) safe[field]=run[field]; return safe; })};
}
function historySnapshot(source, run, payload) {
  if (!Array.isArray(payload.rows)) fail(`${source} summary is invalid`);
  const publicRun={}; for (const field of ["run_id", "observation_start", "observation_end", "native_resolution", "status"]) if (run[field] != null) publicRun[field]=run[field];
  return {schema_version:"tsird-public-evidence-snapshot/v1", indicator:source, run:publicRun, rows:payload.rows.filter((row) => row && typeof row === "object").map((row) => { const safe={}; for (const field of HISTORY_FIELDS) if (Object.hasOwn(row,field)) safe[field]=row[field]; return safe; })};
}
function tabiaGeometry(payload) {
  if (!payload || payload.type !== "FeatureCollection" || !Array.isArray(payload.features)) fail("Tabia geometry is invalid");
  return {type:"FeatureCollection", schema_version:"tsird-public-tabia-geometry/v1", features:payload.features.map((feature) => {
    if (!feature || !feature.geometry || !feature.properties || typeof feature.properties.tsird_tabia_id !== "string") fail("Tabia geometry feature is invalid");
    const properties={}; for (const field of ["tsird_tabia_id", "tabia_name_en", "woreda_name_en"]) if (Object.hasOwn(feature.properties,field)) properties[field]=feature.properties[field];
    return {type:"Feature",geometry:feature.geometry,properties};
  })};
}
async function main() {
  const host = process.argv[2] || "";
  if (!/^[A-Za-z0-9.-]+$/.test(host)) fail("production host is invalid");
  for (const required of ["node", "sftp", "ssh", "mktemp"]) {
    try { childProcess.execFileSync("sh", ["-c", `command -v ${required}`], { stdio:"ignore" }); } catch { fail(`required command unavailable: ${required}`); }
  }
  for (const required of [path.join(KEY_ROOT, "tsird-drought-release-upload"), path.join(KEY_ROOT, "tsird-drought-release-activate"), path.join(KEY_ROOT, "known_hosts")]) if (!fs.existsSync(required)) fail(`missing controlled publisher input: ${required}`);
  const payloads = {};
  for (const [name, endpoint] of Object.entries(INDICATORS)) { payloads[name] = await getJson(endpoint); usable(payloads[name], name); }
  const rainfall = await getJson("/map/api/drought/development/evidence/rainfall/runs");
  if (!Array.isArray(rainfall.runs) || !rainfall.runs.length || !rainfall.runs[0] || typeof rainfall.runs[0] !== "object") fail("final rainfall evidence index is incomplete");
  const boundary = "Automatically published retained indicator evidence only. Each source is shown separately; it is not a combined drought class, food-security classification, forecast, allocation recommendation, or operational decision.";
  const workspace = publicWorkspace(payloads);
  const observedRunsRaw = await getJson("/map/api/drought/development/observed-rainfall/runs?limit=60");
  const observedRuns = observedIndex(observedRunsRaw);
  if (!observedRuns.runs.length) fail("observed rainfall snapshot index is empty");
  const observedSnapshots = {};
  let geometry = null;
  for (const run of observedRuns.runs) {
    const runId = run.run_id; if (typeof runId !== "string" || !safeSuffix(runId)) fail("observed rainfall run ID is invalid");
    observedSnapshots[runId] = observedSnapshot(await getJson(`/map/api/drought/development/observed-rainfall/runs/${encodeURIComponent(runId)}?limit=748`));
    if (!geometry) geometry = tabiaGeometry(await getJson(`/map/api/drought/development/observed-rainfall/runs/${encodeURIComponent(runId)}/features`));
  }
  const histories = {};
  for (const source of HISTORY_SOURCES) {
    const index = historyIndex(source, await getJson(`/map/api/drought/development/evidence/${source}/runs`));
    if (!index.runs.length) fail(`${source} evidence index is empty`);
    const snapshots = {};
    for (const run of index.runs) {
      const runId = run.run_id; if (typeof runId !== "string" || !safeSuffix(runId)) fail(`${source} run ID is invalid`);
      snapshots[runId] = historySnapshot(source, run, await getJson(`/map/api/drought/development/evidence/${source}/runs/${encodeURIComponent(runId)}/summary`));
    }
    histories[source] = {index, snapshots};
  }
  const publicRainfall = { schema_version:"tsird-public-rainfall-evidence-index/v1", runs: rainfall.runs.map((run) => ({
    run_id:run.run_id, evidence_kind:run.evidence_kind, native_resolution:run.native_resolution,
    observation_start:run.observation_start, observation_end:run.observation_end, quality_summary:run.quality_summary,
    source_product:run.provenance && run.provenance.source_product, method:run.provenance && run.provenance.method,
    interpretation_boundary:"Retained rainfall evidence only; it does not create a drought class or combined score." })) };
  const fingerprint = crypto.createHash("sha256").update(JSON.stringify({workspace, publicRainfall, observedRuns, observedSnapshots, histories, rasters:RASTERS.map((entry) => [entry[1], sha256(path.join(NATIVE_ROOT, entry[1]))])})).digest("hex");
  fs.mkdirSync(STAGING_ROOT, {recursive:true, mode:0o700});
  const receiptFile = path.join(STAGING_ROOT, "last-successful-fingerprint.json");
  if (fs.existsSync(receiptFile)) { try { if (JSON.parse(fs.readFileSync(receiptFile, "utf8")).fingerprint === fingerprint) { console.log(JSON.stringify({status:"current", note:"No retained indicator or native raster change; public pointer was not moved."})); return; } } catch {} }
  const releaseId = compactId(); const releaseDir = path.join(STAGING_ROOT, releaseId); fs.mkdirSync(releaseDir, {mode:0o700});
  try {
    const written = {};
    written["drought-evidence-summary.json"] = writeJson(path.join(releaseDir, "drought-evidence-summary.json"), publicRainfall);
    written["drought-workspace-latest.json"] = writeJson(path.join(releaseDir, "drought-workspace-latest.json"), workspace);
    written["tabia-geometry.json"] = writeJson(path.join(releaseDir, "tabia-geometry.json"), geometry);
    written["observed-rainfall-runs.json"] = writeJson(path.join(releaseDir, "observed-rainfall-runs.json"), observedRuns);
    for (const [runId, snapshot] of Object.entries(observedSnapshots)) written[`observed-rainfall-run-${safeSuffix(runId)}.json`] = writeJson(path.join(releaseDir, `observed-rainfall-run-${safeSuffix(runId)}.json`), snapshot);
    for (const [source, history] of Object.entries(histories)) {
      written[`evidence-${source}-runs.json`] = writeJson(path.join(releaseDir, `evidence-${source}-runs.json`), history.index);
      for (const [runId, snapshot] of Object.entries(history.snapshots)) written[`evidence-${source}-run-${safeSuffix(runId)}.json`] = writeJson(path.join(releaseDir, `evidence-${source}-run-${safeSuffix(runId)}.json`), snapshot);
    }
    const status = {schema_version:"tsird-drought-automatic-indicator-release-status/v1", environment:"development-to-production", release_id:releaseId, release_state:"auto-validated", release_channel:"indicator-evidence", generated_at:now(), note:"Published automatically only after complete source-specific Tabia quality and coverage checks. The existing public indicator release remains current when checks fail."};
    written["status.json"] = writeJson(path.join(releaseDir, "status.json"), status);
    const [start, end] = windowFor(payloads.observed.run);
    const assets = [
      asset("drought-evidence-summary", "drought_evidence_summary", "drought-evidence-summary.json", ...written["drought-evidence-summary.json"], "TSIRD retained CHIRPS rainfall evidence index", start, end, publicRainfall.schema_version, boundary),
      asset("drought-workspace-latest", "vector_display_summary", "drought-workspace-latest.json", ...written["drought-workspace-latest.json"], "TSIRD retained Tabia indicator summaries", start, end, workspace.schema_version, boundary),
      asset("tabia-geometry", "vector_display_summary", "tabia-geometry.json", ...written["tabia-geometry.json"], "TSIRD Tabia boundary geometry for retained evidence display", start, end, geometry.schema_version, `${boundary} Boundary geometry joins only to released Tabia evidence summaries.`),
      asset("observed-rainfall-runs", "drought_evidence_summary", "observed-rainfall-runs.json", ...written["observed-rainfall-runs.json"], "TSIRD retained observed rainfall snapshot index", start, end, observedRuns.schema_version, `${boundary} Historical selections remain archived observations.`),
      asset("release-status", "public_status", "status.json", ...written["status.json"], "TSIRD automated indicator validator", start, end, status.schema_version, "Publication provenance only; it is not a scientific certification or operational decision."),
    ];
    for (const run of observedRuns.runs) {
      const filename=`observed-rainfall-run-${safeSuffix(run.run_id)}.json`; const [runStart,runEnd]=windowFor(run);
      assets.push(asset(`observed-rainfall-run-${safeSuffix(run.run_id)}`, "vector_display_summary", filename, ...written[filename], "TSIRD retained observed rainfall Tabia snapshot", runStart, runEnd, observedSnapshots[run.run_id].schema_version, `${boundary} Historical snapshot is an archived observation, not a forecast or a past decision product.`));
    }
    for (const [source, history] of Object.entries(histories)) {
      const indexFilename=`evidence-${source}-runs.json`; const [historyStart,historyEnd]=windowFor(history.index.runs[0]);
      assets.push(asset(`evidence-${source}-runs`, "drought_evidence_summary", indexFilename, ...written[indexFilename], `TSIRD retained ${source} evidence index`, historyStart, historyEnd, history.index.schema_version, `${boundary} Retained source observations remain separate.`));
      for (const run of history.index.runs) { const filename=`evidence-${source}-run-${safeSuffix(run.run_id)}.json`; const [runStart,runEnd]=windowFor(run); assets.push(asset(`evidence-${source}-run-${safeSuffix(run.run_id)}`, "vector_display_summary", filename, ...written[filename], `TSIRD retained ${source} Tabia snapshot`, runStart, runEnd, history.snapshots[run.run_id].schema_version, `${boundary} Retained source observation only; it does not create a class, forecast, or priority result.`)); }
    }
    for (const [id, filename, source, indicator] of RASTERS) {
      const sourcePath = path.join(NATIVE_ROOT, filename); const st = fs.lstatSync(sourcePath);
      if (!st.isFile() || st.isSymbolicLink()) fail(`native display raster is missing or unsafe: ${filename}`);
      // The production ingress is setgid to the activation-only group. Keep
      // staged files group-readable so that account can verify and atomically
      // activate them, while neither account receives general shell access.
      const target = path.join(releaseDir, filename); fs.copyFileSync(sourcePath, target); fs.chmodSync(target, 0o640);
      const [rasterStart, rasterEnd] = windowFor(payloads[indicator].run);
      assets.push(asset(id, "native_evidence_raster", filename, fs.statSync(target).size, sha256(target), source, rasterStart, rasterEnd, String(payloads[indicator].run.schema_version || payloads[indicator].run.run_id || "unknown"), boundary));
    }
    const manifest = {schema_version:"tsird-drought-production-release/v1", release_id:releaseId, release_state:"auto-validated", release_channel:"indicator-evidence", prepared_by:"TSIRD automated indicator validation", prepared_at:now(), previous_release_id:null, public_scope:boundary, assets};
    writeJson(path.join(releaseDir, "manifest.json"), manifest);
    const runtime = fs.mkdtempSync(path.join(os.tmpdir(), "tsird-indicator-publisher-"));
    try {
      const uploadKey = path.join(runtime,"upload_key"), activateKey = path.join(runtime,"activate_key"), knownHosts = path.join(runtime,"known_hosts");
      fs.copyFileSync(path.join(KEY_ROOT,"tsird-drought-release-upload"), uploadKey); fs.copyFileSync(path.join(KEY_ROOT,"tsird-drought-release-activate"), activateKey); fs.copyFileSync(path.join(KEY_ROOT,"known_hosts"), knownHosts);
      for (const item of [uploadKey, activateKey, knownHosts]) fs.chmodSync(item,0o600);
      const filenames = ["manifest.json", ...assets.map((item) => item.relative_path)].sort();
      const batch = [`mkdir /incoming/${releaseId}`, ...filenames.map((filename) => `put ${path.join(releaseDir, filename)} /incoming/${releaseId}/${filename}`)].join("\n") + "\n";
      const batchFile = path.join(runtime,"upload.batch"); fs.writeFileSync(batchFile,batch,{mode:0o600});
      const options = ["-o","BatchMode=yes","-o","IdentitiesOnly=yes","-o","StrictHostKeyChecking=yes","-o",`UserKnownHostsFile=${knownHosts}`,"-o","GlobalKnownHostsFile=/dev/null"];
      childProcess.execFileSync("sftp", [...options,"-i",uploadKey,"-b",batchFile,`${UPLOAD_USER}@${host}`], {stdio:"inherit"});
      childProcess.execFileSync("ssh", [...options,"-i",activateKey,`${ACTIVATE_USER}@${host}`,`activate-indicators ${releaseId}`], {stdio:"inherit"});
      fs.writeFileSync(receiptFile, JSON.stringify({fingerprint,release_id:releaseId,published_at:now()})+"\n", {mode:0o600});
      console.log(JSON.stringify({status:"published",release_id:releaseId,assets:assets.length}));
    } finally { fs.rmSync(runtime,{recursive:true,force:true}); }
  } catch (error) { fs.rmSync(releaseDir,{recursive:true,force:true}); throw error; }
}
main().catch((error) => { console.error(`ERROR: ${error.message}`); process.exit(2); });
