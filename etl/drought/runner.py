"""Restricted local runner for TSIRD Drought Intelligence refresh jobs.

n8n may request only known, validated workflows through this service.  It has
no Docker socket and does not accept arbitrary commands, file paths, URLs, or
database statements.  It is development-only and must never be exposed at a
host port.
"""
import json
import os
import subprocess
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field, field_validator
from model_readiness import build_readiness_report
from storage_inventory import build_inventory

WORK_DIR = Path("/work/drought")
DATA_ROOT = Path("/data/drought")
TOKEN = os.environ.get("DROUGHT_RUNNER_TOKEN")
CHIRPS_BASELINE_START, CHIRPS_BASELINE_END = 1991, 2020
app = FastAPI(title="TSIRD Drought Runner", docs_url=None, redoc_url=None)
jobs: dict[str, dict] = {}
jobs_lock = threading.Lock()

CONTROL_WORKFLOWS = (
    {"key": "chirps-final", "label": "CHIRPS final monthly rainfall refresh", "cadence": "Daily 08:00 Addis discovery; refresh only when a completed final month is new", "policy_state": "active"},
    {"key": "chirps-rapid", "label": "CHIRPS rapid source probe", "cadence": "Daily 06:30 Addis", "policy_state": "active"},
    {"key": "wapor", "label": "WaPOR crop water-use", "cadence": "Daily 07:00 Addis; refresh only when the provider declares a new dekad", "policy_state": "active"},
    {"key": "ndvi", "label": "Copernicus NDVI source probe", "cadence": "Daily 06:45 Addis; metadata only", "policy_state": "active"},
    {"key": "ndvi-summary", "label": "Copernicus NDVI Tabia evidence", "cadence": "Manual development verification; no schedule activated", "policy_state": "inactive"},
    {"key": "swi", "label": "Copernicus SWI source probe", "cadence": "Daily 06:50 Addis; metadata only", "policy_state": "active"},
    {"key": "lst-history", "label": "Thermal historical evidence (CLMS LST v2)", "cadence": "Manual history only; upstream product superseded", "policy_state": "inactive"},
    {"key": "seasonal-outlook", "label": "ICPAC seasonal-outlook catalogue probe", "cadence": "Weekly 07:10 Addis; no schedule activated", "policy_state": "inactive"},
    {"key": "c3s-seasonal", "label": "C3S seasonal forecast access probe", "cadence": "Monthly candidate; no schedule activated", "policy_state": "inactive"},
    {"key": "c3s-hindcast", "label": "C3S matched hindcast availability probe", "cadence": "Manual development gate; no schedule activated", "policy_state": "inactive"},
    {"key": "c3s-skill-pilot", "label": "C3S–CHIRPS seasonal skill pilot", "cadence": "Manual development study; no schedule activated", "policy_state": "inactive"},
    {"key": "fews-net-food-security", "label": "FEWS NET public classification discovery", "cadence": "Weekly Monday 07:20 Addis availability check; no automatic provider-geometry retention", "policy_state": "active_local_only"},
    {"key": "storage-inventory", "label": "Drought storage inventory", "cadence": "Monthly, day 1 at 07:15 Addis; read-only", "policy_state": "active"},
    {"key": "seasonal-baseline-pilot", "label": "Seasonal-baseline technical pilot", "cadence": "Manual fixed 2018/2021/2025 × February/August/November; no schedule", "policy_state": "inactive"},
    {"key": "seasonal-reference-history", "label": "Seasonal-reference candidate history", "cadence": "Manual fixed 2018–2025 × all calendar months; no schedule", "policy_state": "inactive"},
)


def now():
    return datetime.now(timezone.utc).isoformat()


def synchronize_current_evidence(kind: str) -> str:
    """Rebuild one stable native raster from the same current run as its Tabia layer."""
    completed = subprocess.run(
        ["python3", str(WORK_DIR / "sync_current_evidence.py"), "--kind", kind, "--apply"],
        cwd=WORK_DIR, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        check=True, timeout=900,
    )
    return completed.stdout[-1500:]


def control_receipt(filename: str, fields: tuple[str, ...]) -> dict | None:
    """Return selected, non-sensitive receipt fields for the control view."""
    path = DATA_ROOT / "outputs" / filename
    if not path.is_file():
        return None
    try:
        source = json.loads(path.read_text(encoding="utf-8"))
        return {key: source.get(key) for key in fields}
    except (OSError, json.JSONDecodeError):
        return {"status": "unreadable_receipt"}


def current_wapor_manifest() -> dict | None:
    manifests = sorted((DATA_ROOT / "outputs").glob("fao-wapor-v3-l2-*.manifest.json"),
                       key=lambda path: path.stat().st_mtime, reverse=True)
    for path in manifests:
        try:
            source = json.loads(path.read_text(encoding="utf-8"))
            # Historical baseline-pilot artifacts are retained for review but
            # must never displace the declared current WaPOR context in the
            # control dashboard.
            if source.get("baseline_pilot_only") or source.get("seasonal_reference_candidate_only"):
                continue
            return {key: source.get(key) for key in ("run_id", "status", "source_period_start",
                                                       "source_period_end", "source_retrieved_at",
                                                       "native_resolution")}
        except (OSError, json.JSONDecodeError):
            continue
    return None


def require_token(value: str | None):
    if not TOKEN or value != TOKEN:
        # Deliberately redacted: enough evidence to diagnose container routing
        # and header forwarding without placing credential material in logs.
        print(f"drought runner authorization rejected: header_present={value is not None} "
              f"header_length={len(value) if value is not None else 0}", flush=True)
        raise HTTPException(status_code=401, detail="Unauthorized drought runner request")


class ObservedRainfallRequest(BaseModel):
    analysis_year: int = Field(ge=1981, le=2100)
    months: list[int] = Field(min_length=1, max_length=6)
    baseline_start: int = Field(default=1991, ge=1981, le=2099)
    baseline_end: int = Field(default=2020, ge=1982, le=2100)

    @field_validator("months")
    @classmethod
    def unique_calendar_months(cls, values):
        if any(month < 1 or month > 12 for month in values):
            raise ValueError("months must be between 1 and 12")
        if len(set(values)) != len(values):
            raise ValueError("months must not contain duplicates")
        return sorted(values)

    @field_validator("baseline_end")
    @classmethod
    def valid_baseline(cls, value, info):
        start = info.data.get("baseline_start")
        if start and value <= start:
            raise ValueError("baseline_end must be after baseline_start")
        return value


def run_job(job_id: str, request: ObservedRainfallRequest):
    month_string = ",".join(str(month) for month in request.months)
    run_id = (
        f"chirps-v3-{request.analysis_year}-{'-'.join(map(str, request.months))}"
        f"-baseline-{request.baseline_start}-{request.baseline_end}"
    )
    artifact_base = DATA_ROOT / "outputs" / run_id
    commands = [
        ["python3", str(WORK_DIR / "chirps_tabia_summary.py"),
         "--analysis-year", str(request.analysis_year), "--months", month_string,
         "--baseline-start", str(request.baseline_start), "--baseline-end", str(request.baseline_end),
         "--data-root", str(DATA_ROOT), "--refresh-current-source", "--defer-current-publish"],
        ["python3", str(WORK_DIR / "validate_artifact.py"), str(artifact_base)],
        ["python3", str(WORK_DIR / "load_chirps_summary.py"), str(artifact_base)],
    ]
    with jobs_lock:
        jobs[job_id].update(status="running", started_at=now(), run_id=run_id)
    output = []
    try:
        for command in commands:
            completed = subprocess.run(command, cwd=WORK_DIR, text=True,
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       check=True, timeout=7200)
            output.append(completed.stdout[-2000:])
        output.append(synchronize_current_evidence("rainfall"))
        status = "succeeded"
        error = None
    except subprocess.CalledProcessError as exc:
        status = "failed"
        error = f"ETL command failed with exit code {exc.returncode}"
        output.append((exc.stdout or "")[-2000:])
    except subprocess.TimeoutExpired:
        status = "failed"
        error = "ETL job exceeded the 2-hour development timeout"
    except Exception as exc:  # Preserve operator visibility without a traceback leak.
        status = "failed"
        error = f"Unexpected runner error: {type(exc).__name__}"
    with jobs_lock:
        jobs[job_id].update(status=status, finished_at=now(), error=error,
                            output_tail="\n".join(output)[-4000:])


def run_final_monthly_probe(job_id: str):
    """Run bounded final-month discovery; it never downloads a CHIRPS raster."""
    with jobs_lock:
        jobs[job_id].update(status="running", started_at=now())
    try:
        completed = subprocess.run(["python3", str(WORK_DIR / "chirps_final_monthly_probe.py")], cwd=WORK_DIR,
                                   text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   check=True, timeout=180)
        result = json.loads(completed.stdout)
        status, error, output = result.get("status", "unavailable"), None, completed.stdout[-3000:]
    except subprocess.CalledProcessError as exc:
        status, error, output = "unavailable", "CHIRPS final-month probe failed", (exc.stdout or "")[-3000:]
    except Exception as exc:
        status, error, output = "unavailable", f"Unexpected final-month probe error: {type(exc).__name__}", ""
    with jobs_lock:
        jobs[job_id].update(status=status, finished_at=now(), error=error, output_tail=output)


def run_calendar_final_refresh(job_id: str):
    """Refresh only the fixed latest month selected by the local discovery gate."""
    with jobs_lock:
        jobs[job_id].update(status="running", started_at=now())
    try:
        completed = subprocess.run(["python3", str(WORK_DIR / "chirps_final_monthly_probe.py")], cwd=WORK_DIR,
                                   text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   check=True, timeout=180)
        result = json.loads(completed.stdout)
        if result.get("status") != "ready":
            with jobs_lock:
                jobs[job_id].update(status=result.get("status", "unavailable"), finished_at=now(),
                                    error=None, output_tail=completed.stdout[-3000:])
            return
        request = ObservedRainfallRequest(analysis_year=int(result["analysis_year"]), months=[int(result["month"])],
                                          baseline_start=CHIRPS_BASELINE_START, baseline_end=CHIRPS_BASELINE_END)
        with jobs_lock:
            jobs[job_id]["request"] = request.model_dump()
        run_job(job_id, request)
    except subprocess.CalledProcessError as exc:
        with jobs_lock:
            jobs[job_id].update(status="failed", finished_at=now(), error="CHIRPS final-month discovery failed",
                                output_tail=(exc.stdout or "")[-3000:])
    except Exception as exc:
        with jobs_lock:
            jobs[job_id].update(status="failed", finished_at=now(), error=f"Unexpected final refresh error: {type(exc).__name__}", output_tail="")


def run_preliminary_probe(job_id: str):
    with jobs_lock:
        jobs[job_id].update(status="running", started_at=now())
    try:
        completed = subprocess.run(
            ["python3", str(WORK_DIR / "chirps_prelim_probe.py")], cwd=WORK_DIR,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            check=True, timeout=600,
        )
        result = json.loads(completed.stdout)
        # A stale feed is an expected operational condition, not a failed
        # request. n8n can route it to an operator warning without publishing.
        status, error = result["status"], None
        output = completed.stdout[-4000:]
    except subprocess.CalledProcessError as exc:
        status, error, output = "failed", "CHIRPS preliminary probe failed", (exc.stdout or "")[-4000:]
    except Exception as exc:
        status, error, output = "failed", f"Unexpected probe error: {type(exc).__name__}", ""
    with jobs_lock:
        jobs[job_id].update(status=status, finished_at=now(), error=error, output_tail=output)


def run_preliminary_summary(job_id: str):
    with jobs_lock:
        jobs[job_id].update(status="running", started_at=now())
    output = []
    try:
        summary = subprocess.run(["python3", str(WORK_DIR / "chirps_prelim_tabia_summary.py")], cwd=WORK_DIR,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True, timeout=3600)
        run_id = json.loads(summary.stdout)["run_id"]
        loaded = subprocess.run(["python3", str(WORK_DIR / "load_chirps_prelim_summary.py"), str(DATA_ROOT / "outputs" / run_id)],
            cwd=WORK_DIR, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True, timeout=600)
        output = [summary.stdout[-2000:], loaded.stdout[-2000:], synchronize_current_evidence("rapid")]
        status, error = "succeeded", None
    except subprocess.CalledProcessError as exc:
        status, error, output = "failed", "CHIRPS preliminary Tabia summary failed", [(exc.stdout or "")[-4000:]]
    except Exception as exc:
        status, error = "failed", f"Unexpected preliminary summary error: {type(exc).__name__}"
    with jobs_lock:
        jobs[job_id].update(status=status, finished_at=now(), error=error, output_tail="\n".join(output)[-4000:])


def run_preliminary_baseline(job_id: str):
    with jobs_lock:
        jobs[job_id].update(status="running", started_at=now())
    try:
        completed = subprocess.run(["python3", str(WORK_DIR / "build_chirps_prelim_baseline.py")], cwd=WORK_DIR,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True, timeout=7200)
        status, error, output = "succeeded", None, completed.stdout[-4000:]
    except subprocess.CalledProcessError as exc:
        status, error, output = "failed", "CHIRPS preliminary baseline build failed", (exc.stdout or "")[-4000:]
    except subprocess.TimeoutExpired:
        status, error, output = "failed", "CHIRPS preliminary baseline exceeded the 2-hour development timeout", ""
    except Exception as exc:
        status, error, output = "failed", f"Unexpected preliminary baseline error: {type(exc).__name__}", ""
    with jobs_lock:
        jobs[job_id].update(status=status, finished_at=now(), error=error, output_tail=output)


def run_ndvi_access_check(job_id: str):
    """Verify CDSE OAuth plus one metadata-only NDVI collection request."""
    with jobs_lock:
        jobs[job_id].update(status="running", started_at=now())
    try:
        completed = subprocess.run(
            ["python3", str(WORK_DIR / "ndvi_access_check.py")], cwd=WORK_DIR,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            check=True, timeout=90,
        )
        status, error, output = "succeeded", None, completed.stdout[-1000:]
    except subprocess.CalledProcessError as exc:
        # The child script emits only status-level, deliberately redacted JSON.
        status, error, output = "failed", "CDSE NDVI access check failed", (exc.stdout or "")[-1000:]
    except subprocess.TimeoutExpired:
        status, error, output = "failed", "CDSE NDVI access check timed out", ""
    except Exception as exc:
        status, error, output = "failed", f"Unexpected NDVI access-check error: {type(exc).__name__}", ""
    with jobs_lock:
        jobs[job_id].update(status=status, finished_at=now(), error=error, output_tail=output)


def run_cdse_source_probe(job_id: str, kind: str):
    """Probe CDSE catalogue metadata and preserve ready/current/degraded state."""
    with jobs_lock:
        jobs[job_id].update(status="running", started_at=now())
    try:
        completed = subprocess.run(["python3", str(WORK_DIR / "cdse_source_probe.py"), kind], cwd=WORK_DIR,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True, timeout=120)
        result = json.JSONDecoder().raw_decode(completed.stdout[completed.stdout.find("{"):])[0]
        status, error, output = result.get("status", "succeeded"), None, completed.stdout[-2000:]
    except subprocess.CalledProcessError as exc:
        status, error, output = "unavailable", f"CDSE {kind.upper()} source probe failed", (exc.stdout or "")[-2000:]
    except subprocess.TimeoutExpired:
        status, error, output = "unavailable", f"CDSE {kind.upper()} source probe timed out", ""
    except Exception as exc:
        status, error, output = "unavailable", f"Unexpected CDSE {kind.upper()} probe error: {type(exc).__name__}", ""
    with jobs_lock:
        jobs[job_id].update(status=status, finished_at=now(), error=error, output_tail=output)


def run_swi_access_check(job_id: str):
    """Verify the configured SWI collection without downloading pixels."""
    with jobs_lock:
        jobs[job_id].update(status="running", started_at=now())
    try:
        environment = os.environ.copy()
        environment["CDSE_NDVI_COLLECTION"] = environment["CDSE_SWI_COLLECTION"]
        completed = subprocess.run(["python3", str(WORK_DIR / "ndvi_access_check.py")], cwd=WORK_DIR,
            env=environment, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            check=True, timeout=90)
        status, error, output = "succeeded", None, completed.stdout[-1000:]
    except subprocess.CalledProcessError as exc:
        status, error, output = "failed", "CDSE SWI access check failed", (exc.stdout or "")[-1000:]
    except KeyError:
        status, error, output = "failed", "CDSE SWI collection setting is missing", ""
    except Exception as exc:
        status, error, output = "failed", f"Unexpected SWI access-check error: {type(exc).__name__}", ""
    with jobs_lock:
        jobs[job_id].update(status=status, finished_at=now(), error=error, output_tail=output)


def run_lst_access_check(job_id: str):
    with jobs_lock: jobs[job_id].update(status="running", started_at=now())
    try:
        environment = os.environ.copy(); environment["CDSE_NDVI_COLLECTION"] = environment["CDSE_LST_COLLECTION"]
        completed = subprocess.run(["python3", str(WORK_DIR / "ndvi_access_check.py")], cwd=WORK_DIR, env=environment,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True, timeout=90)
        status, error, output = "succeeded", None, completed.stdout[-1000:]
    except subprocess.CalledProcessError as exc:
        status, error, output = "failed", "CDSE LST access check failed", (exc.stdout or "")[-1000:]
    except KeyError:
        status, error, output = "failed", "CDSE LST collection setting is missing", ""
    except Exception as exc:
        status, error, output = "failed", f"Unexpected LST access-check error: {type(exc).__name__}", ""
    with jobs_lock: jobs[job_id].update(status=status, finished_at=now(), error=error, output_tail=output)


def run_ndvi_tabia_summary(job_id: str):
    """Retrieve one bounded current raster and derive local Tabia summaries."""
    with jobs_lock:
        jobs[job_id].update(status="running", started_at=now())
    output = []
    try:
        summary = subprocess.run(["python3", str(WORK_DIR / "cdse_ndvi_tabia_summary.py")], cwd=WORK_DIR,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True, timeout=1800)
        # GDAL/Python may emit non-JSON status notices before the script's
        # final JSON record.  Decode that record without treating a valid
        # completed artifact as a failed refresh.
        first_json = summary.stdout.find("{")
        if first_json < 0:
            raise ValueError("NDVI summary did not report a run ID")
        run_id = json.JSONDecoder().raw_decode(summary.stdout[first_json:])[0]["run_id"]
        loaded = subprocess.run(["python3", str(WORK_DIR / "load_cdse_ndvi_summary.py"), str(DATA_ROOT / "outputs" / run_id)],
            cwd=WORK_DIR, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True, timeout=600)
        loaded_json = json.JSONDecoder().raw_decode(loaded.stdout[loaded.stdout.find("{"):])[0]
        synced = synchronize_current_evidence("ndvi")
        status, error, output = loaded_json.get("artifact_status", "succeeded"), None, [summary.stdout[-2000:], loaded.stdout[-2000:], synced]
    except subprocess.CalledProcessError as exc:
        status, error, output = "failed", "CDSE NDVI Tabia summary failed", [(exc.stdout or "")[-2000:]]
    except subprocess.TimeoutExpired:
        status, error, output = "failed", "CDSE NDVI Tabia summary exceeded the 30-minute development timeout", []
    except Exception as exc:
        status, error, output = "failed", f"Unexpected NDVI summary error: {type(exc).__name__}", []
    with jobs_lock:
        jobs[job_id].update(status=status, finished_at=now(), error=error, output_tail="\n".join(output)[-4000:])


def run_swi_tabia_summary(job_id: str):
    with jobs_lock: jobs[job_id].update(status="running", started_at=now())
    try:
        summary = subprocess.run(["python3", str(WORK_DIR / "cdse_swi_tabia_summary.py")], cwd=WORK_DIR, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True, timeout=1800)
        run_id = json.JSONDecoder().raw_decode(summary.stdout[summary.stdout.find("{"):])[0]["run_id"]
        loaded = subprocess.run(["python3", str(WORK_DIR / "load_cdse_swi_summary.py"), str(DATA_ROOT / "outputs" / run_id)], cwd=WORK_DIR, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True, timeout=600)
        result=json.JSONDecoder().raw_decode(loaded.stdout[loaded.stdout.find("{"):])[0]; synced=synchronize_current_evidence("swi"); status,error,output=result.get("artifact_status","succeeded"),None,summary.stdout[-2000:]+loaded.stdout[-2000:]+synced
    except subprocess.CalledProcessError as exc: status,error,output="failed","CDSE SWI Tabia summary failed",(exc.stdout or "")[-4000:]
    except Exception as exc: status,error,output="failed",f"Unexpected SWI summary error: {type(exc).__name__}",""
    with jobs_lock: jobs[job_id].update(status=status, finished_at=now(), error=error, output_tail=output)


def run_lst_tabia_summary(job_id: str):
    with jobs_lock: jobs[job_id].update(status="running", started_at=now())
    try:
        summary = subprocess.run(["python3", str(WORK_DIR / "cdse_lst_tabia_summary.py")], cwd=WORK_DIR,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True, timeout=1800)
        run_id = json.JSONDecoder().raw_decode(summary.stdout[summary.stdout.find("{"):])[0]["run_id"]
        loaded = subprocess.run(["python3", str(WORK_DIR / "load_cdse_lst_summary.py"), str(DATA_ROOT / "outputs" / run_id)], cwd=WORK_DIR,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True, timeout=600)
        result = json.JSONDecoder().raw_decode(loaded.stdout[loaded.stdout.find("{"):])[0]
        synced = synchronize_current_evidence("lst")
        status, error, output = result.get("artifact_status", "succeeded"), None, summary.stdout[-2000:] + loaded.stdout[-2000:] + synced
    except subprocess.CalledProcessError as exc:
        status, error, output = "failed", "CDSE LST Tabia summary failed", (exc.stdout or "")[-4000:]
    except Exception as exc:
        status, error, output = "failed", f"Unexpected LST summary error: {type(exc).__name__}", ""
    with jobs_lock: jobs[job_id].update(status=status, finished_at=now(), error=error, output_tail=output)


def run_wapor_probe(job_id: str):
    """Inspect WaPOR catalogue metadata only; it never requests raster pixels."""
    with jobs_lock: jobs[job_id].update(status="running", started_at=now())
    try:
        completed = subprocess.run(["python3", str(WORK_DIR / "wapor_probe.py")], cwd=WORK_DIR,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True, timeout=300)
        result = json.JSONDecoder().raw_decode(completed.stdout[completed.stdout.find("{"):])[0]
        status, error, output = result.get("status", "succeeded"), None, completed.stdout[-2000:]
    except subprocess.CalledProcessError as exc:
        status, error, output = "failed", "FAO WaPOR source probe failed", (exc.stdout or "")[-2000:]
    except Exception as exc:
        status, error, output = "failed", f"Unexpected WaPOR source-probe error: {type(exc).__name__}", ""
    with jobs_lock: jobs[job_id].update(status=status, finished_at=now(), error=error, output_tail=output)


def run_seasonal_baseline_availability_preflight(job_id: str):
    """Inspect fixed provider catalogues for history; never acquire rasters."""
    with jobs_lock: jobs[job_id].update(status="running", started_at=now())
    try:
        completed = subprocess.run(
            ["python3", str(WORK_DIR / "seasonal_baseline_availability_preflight.py")], cwd=WORK_DIR,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True, timeout=900,
        )
        result = json.JSONDecoder().raw_decode(completed.stdout[completed.stdout.find("{"):])[0]
        status, error, output = result.get("status", "succeeded"), None, completed.stdout[-4000:]
    except subprocess.CalledProcessError as exc:
        status, error, output = "unavailable", "Seasonal-baseline availability preflight failed", (exc.stdout or "")[-4000:]
    except subprocess.TimeoutExpired:
        status, error, output = "unavailable", "Seasonal-baseline availability preflight exceeded 15 minutes", ""
    except Exception as exc:
        status, error, output = "unavailable", f"Unexpected baseline-preflight error: {type(exc).__name__}", ""
    with jobs_lock: jobs[job_id].update(status=status, finished_at=now(), error=error, output_tail=output)


def run_seasonal_baseline_pilot(job_id: str):
    """Run the fixed 27-file technical pilot; never calculate a baseline."""
    with jobs_lock: jobs[job_id].update(status="running", started_at=now())
    try:
        completed = subprocess.run(
            ["python3", str(WORK_DIR / "seasonal_baseline_pilot.py")], cwd=WORK_DIR,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True, timeout=28800,
        )
        status, error, output = "completed_review_required", None, completed.stdout[-4000:]
    except subprocess.CalledProcessError as exc:
        status, error, output = "failed", "Fixed seasonal-baseline pilot stopped", (exc.stdout or "")[-4000:]
    except subprocess.TimeoutExpired:
        status, error, output = "failed", "Fixed seasonal-baseline pilot exceeded the 8-hour local-development limit", ""
    except Exception as exc:
        status, error, output = "failed", f"Unexpected seasonal-baseline pilot error: {type(exc).__name__}", ""
    with jobs_lock: jobs[job_id].update(status=status, finished_at=now(), error=error, output_tail=output)


def run_seasonal_reference_history(job_id: str):
    """Run only the fixed 2018--2025 candidate matrix, then build its separate reference."""
    with jobs_lock: jobs[job_id].update(status="running", started_at=now())
    try:
        acquired = subprocess.run(["python3", str(WORK_DIR / "seasonal_reference_history.py")], cwd=WORK_DIR,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True, timeout=172800)
        built = subprocess.run(["python3", str(WORK_DIR / "build_seasonal_reference.py")], cwd=WORK_DIR,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True, timeout=900)
        status, error, output = "candidate_review_required", None, acquired.stdout[-2000:] + built.stdout[-2000:]
    except subprocess.CalledProcessError as exc:
        status, error, output = "failed", "Fixed seasonal-reference history stopped", (exc.stdout or "")[-4000:]
    except subprocess.TimeoutExpired:
        status, error, output = "failed", "Fixed seasonal-reference history exceeded the 48-hour local-development limit", ""
    except Exception as exc:
        status, error, output = "failed", f"Unexpected seasonal-reference history error: {type(exc).__name__}", ""
    with jobs_lock: jobs[job_id].update(status=status, finished_at=now(), error=error, output_tail=output)


def run_wapor_tabia_summary(job_id: str):
    """Acquire one bounded Tigray T/AETI dekad and load its local artifact."""
    with jobs_lock: jobs[job_id].update(status="running", started_at=now())
    try:
        summary = subprocess.run(["python3", str(WORK_DIR / "wapor_tabia_summary.py")], cwd=WORK_DIR,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True, timeout=3600)
        run_id = json.JSONDecoder().raw_decode(summary.stdout[summary.stdout.find("{"):])[0]["run_id"]
        loaded = subprocess.run(["python3", str(WORK_DIR / "load_wapor_summary.py"), str(DATA_ROOT / "outputs" / run_id)], cwd=WORK_DIR,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True, timeout=600)
        result = json.JSONDecoder().raw_decode(loaded.stdout[loaded.stdout.find("{"):])[0]
        synced = synchronize_current_evidence("wapor")
        status, error, output = result.get("artifact_status", "succeeded"), None, summary.stdout[-2000:] + loaded.stdout[-2000:] + synced
    except subprocess.CalledProcessError as exc:
        status, error, output = "failed", "FAO WaPOR Tabia summary failed", (exc.stdout or "")[-4000:]
    except subprocess.TimeoutExpired:
        status, error, output = "failed", "FAO WaPOR summary exceeded the 60-minute development timeout", ""
    except Exception as exc:
        status, error, output = "failed", f"Unexpected WaPOR summary error: {type(exc).__name__}", ""
    with jobs_lock: jobs[job_id].update(status=status, finished_at=now(), error=error, output_tail=output)


def run_storage_inventory(job_id: str):
    """Measure known drought directories; never archive or delete data."""
    with jobs_lock: jobs[job_id].update(status="running", started_at=now())
    try:
        completed = subprocess.run(
            ["python3", str(WORK_DIR / "storage_inventory.py"), "--data-root", str(DATA_ROOT)],
            cwd=WORK_DIR, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            check=True, timeout=120,
        )
        status, error, output = "succeeded", None, completed.stdout[-4000:]
    except subprocess.CalledProcessError as exc:
        status, error, output = "failed", "Storage inventory failed", (exc.stdout or "")[-4000:]
    except subprocess.TimeoutExpired:
        status, error, output = "failed", "Storage inventory exceeded 2 minutes", ""
    except Exception as exc:
        status, error, output = "failed", f"Unexpected runner error: {type(exc).__name__}", ""
    with jobs_lock: jobs[job_id].update(status=status, finished_at=now(), error=error, output_tail=output)


def run_seasonal_outlook_probe(job_id: str):
    """Check the fixed ICPAC catalogue; never infer or ingest forecast data."""
    with jobs_lock: jobs[job_id].update(status="running", started_at=now())
    try:
        completed = subprocess.run(
            ["python3", str(WORK_DIR / "icpac_seasonal_outlook_probe.py")], cwd=WORK_DIR,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True, timeout=90,
        )
        result = json.JSONDecoder().raw_decode(completed.stdout[completed.stdout.find("{"):])[0]
        status, error, output = result.get("status", "manual_asset_review_required"), None, completed.stdout[-2000:]
    except subprocess.CalledProcessError as exc:
        status, error, output = "unavailable", "ICPAC seasonal-outlook catalogue probe failed", (exc.stdout or "")[-2000:]
    except subprocess.TimeoutExpired:
        status, error, output = "unavailable", "ICPAC seasonal-outlook catalogue probe timed out", ""
    except Exception as exc:
        status, error, output = "unavailable", f"Unexpected outlook probe error: {type(exc).__name__}", ""
    with jobs_lock: jobs[job_id].update(status=status, finished_at=now(), error=error, output_tail=output)


def run_fews_net_food_security_probe(job_id: str):
    """Discover public FEWS NET Ethiopia assets; never download, load, or classify."""
    with jobs_lock: jobs[job_id].update(status="running", started_at=now())
    try:
        completed = subprocess.run(
            ["python3", str(WORK_DIR / "fews_net_public_classification_discovery.py")], cwd=WORK_DIR,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True, timeout=90,
        )
        result = json.JSONDecoder().raw_decode(completed.stdout[completed.stdout.find("{"):])[0]
        status, error, output = result.get("status", "manual_data_contract_review_required"), None, completed.stdout[-2000:]
    except subprocess.CalledProcessError as exc:
        status, error, output = "unavailable", "FEWS NET public classification discovery failed", (exc.stdout or "")[-2000:]
    except subprocess.TimeoutExpired:
        status, error, output = "unavailable", "FEWS NET public classification discovery timed out", ""
    except Exception as exc:
        status, error, output = "unavailable", f"Unexpected FEWS NET probe error: {type(exc).__name__}", ""
    with jobs_lock: jobs[job_id].update(status=status, finished_at=now(), error=error, output_tail=output)


def run_priority_historical_replay(job_id: str):
    """Build retained-evidence Jan--Aug draft planning replays only."""
    with jobs_lock: jobs[job_id].update(status="running", started_at=now())
    try:
        completed = subprocess.run(
            ["python3", str(WORK_DIR / "build_priority_historical_replay.py")], cwd=WORK_DIR,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True, timeout=600,
        )
        status, error, output = "succeeded", None, completed.stdout[-4000:]
    except subprocess.CalledProcessError as exc:
        status, error, output = "failed", "Historical priority replay failed", (exc.stdout or "")[-4000:]
    except subprocess.TimeoutExpired:
        status, error, output = "failed", "Historical priority replay exceeded 10 minutes", ""
    except Exception as exc:
        status, error, output = "failed", f"Unexpected priority replay error: {type(exc).__name__}", ""
    with jobs_lock: jobs[job_id].update(status=status, finished_at=now(), error=error, output_tail=output)


def run_c3s_seasonal_access_probe(job_id: str):
    """Run one bounded temporary CDS access check; never publish an outlook."""
    with jobs_lock: jobs[job_id].update(status="running", started_at=now())
    try:
        completed = subprocess.run(
            ["python3", str(WORK_DIR / "c3s_seasonal_access_probe.py")], cwd=WORK_DIR,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True, timeout=180,
        )
        result = json.JSONDecoder().raw_decode(completed.stdout[completed.stdout.find("{"):])[0]
        status, error, output = result.get("status", "unavailable"), None, completed.stdout[-2000:]
    except subprocess.CalledProcessError as exc:
        status, error, output = "unavailable", "C3S seasonal access probe failed", (exc.stdout or "")[-2000:]
    except subprocess.TimeoutExpired:
        status, error, output = "unavailable", "C3S seasonal access probe exceeded 3 minutes", ""
    except Exception as exc:
        status, error, output = "unavailable", f"Unexpected C3S probe error: {type(exc).__name__}", ""
    with jobs_lock: jobs[job_id].update(status=status, finished_at=now(), error=error, output_tail=output)


def run_c3s_seasonal_hindcast_probe(job_id: str):
    """Verify one temporary matched C3S hindcast; never calculate skill."""
    with jobs_lock: jobs[job_id].update(status="running", started_at=now())
    try:
        completed = subprocess.run(
            ["python3", str(WORK_DIR / "c3s_seasonal_hindcast_probe.py")], cwd=WORK_DIR,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True, timeout=360,
        )
        result = json.JSONDecoder().raw_decode(completed.stdout[completed.stdout.find("{"):])[0]
        status, error, output = result.get("status", "unavailable"), None, completed.stdout[-2000:]
    except subprocess.CalledProcessError as exc:
        status, error, output = "unavailable", "C3S matched hindcast probe failed", (exc.stdout or "")[-2000:]
    except subprocess.TimeoutExpired:
        status, error, output = "unavailable", "C3S matched hindcast probe exceeded 6 minutes", ""
    except Exception as exc:
        status, error, output = "unavailable", f"Unexpected C3S hindcast probe error: {type(exc).__name__}", ""
    with jobs_lock: jobs[job_id].update(status=status, finished_at=now(), error=error, output_tail=output)


def run_c3s_seasonal_skill_pilot(job_id: str):
    """Run the fixed, non-publishing C3S-versus-CHIRPS skill pilot."""
    with jobs_lock: jobs[job_id].update(status="running", started_at=now())
    try:
        completed = subprocess.run(
            ["python3", str(WORK_DIR / "c3s_seasonal_skill_pilot.py")], cwd=WORK_DIR,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True, timeout=5400,
        )
        result = json.JSONDecoder().raw_decode(completed.stdout[completed.stdout.find("{"):])[0]
        status, error, output = result.get("status", "failed"), None, completed.stdout[-4000:]
    except subprocess.CalledProcessError as exc:
        status, error, output = "failed", "C3S–CHIRPS skill pilot failed", (exc.stdout or "")[-4000:]
    except subprocess.TimeoutExpired:
        status, error, output = "failed", "C3S–CHIRPS skill pilot exceeded 90 minutes", ""
    except Exception as exc:
        status, error, output = "failed", f"Unexpected C3S skill-pilot error: {type(exc).__name__}", ""
    with jobs_lock: jobs[job_id].update(status=status, finished_at=now(), error=error, output_tail=output)


def run_c3s_august_lead_comparison(job_id: str):
    """Compare fixed two- and three-month leads for the August technical pilot."""
    with jobs_lock: jobs[job_id].update(status="running", started_at=now())
    outputs, cases = [], []
    try:
        for case in ("august-lead-2", "august-lead-3"):
            completed = subprocess.run(
                ["python3", str(WORK_DIR / "c3s_seasonal_skill_pilot.py"), "--case", case], cwd=WORK_DIR,
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True, timeout=5400,
            )
            cases.append(json.JSONDecoder().raw_decode(completed.stdout[completed.stdout.find("{"):])[0])
            outputs.append(completed.stdout[-2000:])
        receipt = {"status": "development_skill_pilot", "purpose": "August rainfall target lead comparison",
                   "cases": [{key: case.get(key) for key in ("case", "target_month", "initialization_month", "lead_month", "metrics", "record_count", "raw_rasters_retained", "created_at")} for case in cases],
                   "publication_gate": "blocked_pending_review", "raw_rasters_retained": False,
                   "created_at": now()}
        (DATA_ROOT / "outputs" / "c3s-skill-pilot-ecmwf51-august-lead-comparison.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
        status, error, output = receipt["status"], None, "\n".join(outputs)[-4000:]
    except subprocess.CalledProcessError as exc:
        status, error, output = "failed", "C3S August lead-comparison pilot failed", (exc.stdout or "")[-4000:]
    except subprocess.TimeoutExpired:
        status, error, output = "failed", "C3S August lead-comparison pilot exceeded its per-case cap", ""
    except Exception as exc:
        status, error, output = "failed", f"Unexpected C3S lead-comparison error: {type(exc).__name__}", ""
    with jobs_lock: jobs[job_id].update(status=status, finished_at=now(), error=error, output_tail=output)


@app.get("/healthz")
def healthz():
    return {"status": "ok", "service": "tsird-drought-runner", "environment": "development"}


@app.get("/control")
def control():
    """Read-only, redacted snapshot for the local TSIRD control dashboard."""
    with jobs_lock:
        recent_jobs = [{key: job.get(key) for key in ("job_id", "workflow", "status",
                                                        "requested_at", "started_at", "finished_at", "error")}
                       for job in list(jobs.values())[-12:]]
        active_jobs = sum(job["status"] in {"queued", "running"} for job in jobs.values())
    try:
        readiness = build_readiness_report()
    except Exception:
        # The dashboard should make a failed readiness inspection visible, but
        # never expose connection details or an implementation traceback.
        readiness = {"status": "unavailable", "read_only": True,
                     "reason": "Local model-readiness inspection is unavailable."}
    return {
        "environment": "development",
        "generated_at": now(),
        "runner": {"status": "ok", "active_jobs": active_jobs},
        "storage": build_inventory(DATA_ROOT),
        "workflow_policy": list(CONTROL_WORKFLOWS),
        "provider_receipts": {
            "chirps_final": control_receipt("chirps-v3-final-monthly-probe.json",
                                               ("status", "reason", "analysis_year", "month", "run_id", "checked_at")),
            "chirps_rapid": control_receipt("chirps-v3-preliminary-pentad-probe.json",
                                               ("status", "reason", "period", "already_summarized", "age_days", "freshness_threshold_days")),
            "wapor": control_receipt("fao-wapor-v3-probe.json",
                                      ("status", "reason", "run_id", "period_start", "period_end", "already_published", "age_days")),
            "seasonal_baseline_preflight": control_receipt("seasonal-baseline-availability-preflight.json",
                                      ("status", "candidate_period", "retrieved_at", "next_step", "not_an_acquisition", "ndvi", "wapor")),
            "seasonal_baseline_pilot": control_receipt("seasonal-baseline-pilot-receipt.json",
                                      ("status", "baseline_pilot_only", "candidate_period", "fixed_years", "fixed_months", "slots", "started_or_retrieved_at", "next_step")),
            "seasonal_reference_history": control_receipt("seasonal-reference-history-receipt.json",
                                      ("status", "seasonal_reference_candidate_only", "candidate_period", "slot_count", "started_or_retrieved_at", "next_step")),
            "seasonal_reference_build": control_receipt("seasonal-reference-build-receipt.json",
                                      ("status", "reference_id", "candidate_period", "minimum_valid_years", "ndvi_reference_rows", "wapor_reference_rows", "built_at", "next_step")),
            "ndvi": control_receipt("cdse-ndvi-probe.json",
                                    ("status", "reason", "observation_timestamp", "already_summarized", "age_days", "freshness_threshold_days", "authentication", "collection_access")),
            "swi": control_receipt("cdse-swi-probe.json",
                                   ("status", "reason", "observation_timestamp", "already_summarized", "age_days", "freshness_threshold_days", "authentication", "collection_access")),
            "seasonal_outlook": control_receipt("igad-icpac-seasonal-probe.json",
                                                 ("status", "reason", "catalogue_url", "http_status", "season_labels_seen", "retrieved_at")),
            "c3s_seasonal": control_receipt("c3s-seasonal-access-probe.json",
                                             ("status", "reason", "dataset", "http_status", "request_scope", "temporary_byte_count", "retained_output", "retrieved_at")),
            "c3s_hindcast": control_receipt("c3s-seasonal-hindcast-probe.json",
                                              ("status", "reason", "dataset", "http_status", "request_scope", "temporary_byte_count", "raster_contract", "retained_output", "retrieved_at")),
            "c3s_skill_pilot": control_receipt("c3s-skill-pilot-ecmwf51-august-lead1.json",
                                                ("status", "provider", "dataset", "system", "observed_reference", "years", "case", "geography", "metric", "metrics", "raw_rasters_retained", "created_at")),
            "c3s_august_lead_comparison": control_receipt("c3s-skill-pilot-ecmwf51-august-lead-comparison.json",
                                                           ("status", "purpose", "cases", "publication_gate", "raw_rasters_retained", "created_at")),
            "fews_net_food_security": control_receipt("fews-net-public-classification-discovery.json",
                                                        ("status", "reason", "product", "catalogue_url", "publication_url", "geojson_candidates", "retrieved_at")),
        },
        "artifacts": {"wapor": current_wapor_manifest()},
        "model_readiness": readiness,
        "recent_jobs": recent_jobs,
        "limitations": [
            "This view does not connect to n8n's database or expose n8n credentials.",
            "Workflow policy is declarative; confirm actual activation and execution history in local n8n.",
            "No action, retry, schedule toggle, archive, or deletion control is available here.",
        ],
    }


@app.get("/readiness")
def readiness():
    """Return the read-only seasonal-stress evidence gate for local development."""
    try:
        return build_readiness_report()
    except Exception:
        raise HTTPException(status_code=503, detail="Local model-readiness inspection unavailable")


@app.post("/runs/observed-rainfall", status_code=202)
def start_observed_rainfall(request: ObservedRainfallRequest,
                            x_tsird_drought_token: str | None = Header(default=None)):
    require_token(x_tsird_drought_token)
    return enqueue_observed_rainfall(request)


def enqueue_observed_rainfall(request: ObservedRainfallRequest):
    with jobs_lock:
        if any(job["status"] in {"queued", "running"} for job in jobs.values()):
            raise HTTPException(status_code=409, detail="A drought refresh job is already active")
        job_id = str(uuid.uuid4())
        jobs[job_id] = {"job_id": job_id, "workflow": "observed-climate-refresh",
                        "status": "queued", "requested_at": now(),
                        "request": request.model_dump(), "run_id": None,
                        "started_at": None, "finished_at": None, "error": None,
                        "output_tail": None}
    threading.Thread(target=run_job, args=(job_id, request), daemon=True).start()
    return jobs[job_id]


@app.post("/runs/observed-rainfall/development-test", status_code=202)
def start_established_development_test(
        ):
    """Run the reviewable, fixed first-workflow verification window.

    This endpoint intentionally takes no user-supplied parameters.  Seasonal
    definitions and scheduling become configurable only after scientific and
    operational review, rather than through an unattended n8n request.
    """
    return enqueue_observed_rainfall(
        ObservedRainfallRequest(analysis_year=2026, months=[6, 7],
                                baseline_start=1991, baseline_end=2020),
    )


@app.post("/runs/chirps-final-monthly-probe/development-test", status_code=202)
def start_final_monthly_probe():
    """Discover the latest completed CHIRPS final month; never download a raster."""
    with jobs_lock:
        if any(job["status"] in {"queued", "running"} for job in jobs.values()):
            raise HTTPException(status_code=409, detail="A drought refresh job is already active")
        job_id = str(uuid.uuid4())
        jobs[job_id] = {"job_id": job_id, "workflow": "chirps-final-monthly-probe", "status": "queued",
                        "requested_at": now(), "request": {}, "run_id": None, "started_at": None,
                        "finished_at": None, "error": None, "output_tail": None}
    threading.Thread(target=run_final_monthly_probe, args=(job_id,), daemon=True).start()
    return jobs[job_id]


@app.post("/runs/chirps-final-monthly-refresh/development-test", status_code=202)
def start_calendar_final_refresh():
    """Refresh only a provider-discovered final month, then atomically promote it after validation."""
    with jobs_lock:
        if any(job["status"] in {"queued", "running"} for job in jobs.values()):
            raise HTTPException(status_code=409, detail="A drought refresh job is already active")
        job_id = str(uuid.uuid4())
        jobs[job_id] = {"job_id": job_id, "workflow": "chirps-final-monthly-refresh", "status": "queued",
                        "requested_at": now(), "request": {}, "run_id": None, "started_at": None,
                        "finished_at": None, "error": None, "output_tail": None}
    threading.Thread(target=run_calendar_final_refresh, args=(job_id,), daemon=True).start()
    return jobs[job_id]


@app.post("/runs/chirps-preliminary-pentad/development-test", status_code=202)
def start_preliminary_pentad_probe():
    """Probe and validate the official preliminary feed; never publishes data."""
    with jobs_lock:
        if any(job["status"] in {"queued", "running"} for job in jobs.values()):
            raise HTTPException(status_code=409, detail="A drought refresh job is already active")
        job_id = str(uuid.uuid4())
        jobs[job_id] = {"job_id": job_id, "workflow": "chirps-preliminary-pentad-probe",
                        "status": "queued", "requested_at": now(), "request": {}, "run_id": None,
                        "started_at": None, "finished_at": None, "error": None, "output_tail": None}
    threading.Thread(target=run_preliminary_probe, args=(job_id,), daemon=True).start()
    return jobs[job_id]


@app.post("/runs/chirps-preliminary-pentad-summary/development-test", status_code=202)
def start_preliminary_pentad_summary():
    """Create a non-classified six-pentad Tabia summary; never publishes data."""
    with jobs_lock:
        if any(job["status"] in {"queued", "running"} for job in jobs.values()):
            raise HTTPException(status_code=409, detail="A drought refresh job is already active")
        job_id = str(uuid.uuid4())
        jobs[job_id] = {"job_id": job_id, "workflow": "chirps-preliminary-pentad-summary",
                        "status": "queued", "requested_at": now(), "request": {}, "run_id": None,
                        "started_at": None, "finished_at": None, "error": None, "output_tail": None}
    threading.Thread(target=run_preliminary_summary, args=(job_id,), daemon=True).start()
    return jobs[job_id]


@app.post("/runs/chirps-preliminary-pentad-baseline/development-test", status_code=202)
def start_preliminary_pentad_baseline():
    """Build local final-history comparison data; never assigns drought classes."""
    with jobs_lock:
        if any(job["status"] in {"queued", "running"} for job in jobs.values()):
            raise HTTPException(status_code=409, detail="A drought refresh job is already active")
        job_id = str(uuid.uuid4())
        jobs[job_id] = {"job_id": job_id, "workflow": "chirps-preliminary-pentad-baseline",
                        "status": "queued", "requested_at": now(), "request": {}, "run_id": None,
                        "started_at": None, "finished_at": None, "error": None, "output_tail": None}
    threading.Thread(target=run_preliminary_baseline, args=(job_id,), daemon=True).start()
    return jobs[job_id]


@app.post("/runs/ndvi-access/development-test", status_code=202)
def start_ndvi_access_check():
    """Run one metadata-only CDSE NDVI access check; no imagery is downloaded."""
    with jobs_lock:
        if any(job["status"] in {"queued", "running"} for job in jobs.values()):
            raise HTTPException(status_code=409, detail="A drought refresh job is already active")
        job_id = str(uuid.uuid4())
        jobs[job_id] = {"job_id": job_id, "workflow": "ndvi-access-check",
                        "status": "queued", "requested_at": now(), "request": {}, "run_id": None,
                        "started_at": None, "finished_at": None, "error": None, "output_tail": None}
    threading.Thread(target=run_ndvi_access_check, args=(job_id,), daemon=True).start()
    return jobs[job_id]


@app.post("/runs/ndvi-source-probe/development-test", status_code=202)
def start_ndvi_source_probe():
    """Inspect the latest NDVI catalogue timestamp; never download imagery."""
    with jobs_lock:
        if any(job["status"] in {"queued", "running"} for job in jobs.values()):
            raise HTTPException(status_code=409, detail="A drought refresh job is already active")
        job_id = str(uuid.uuid4())
        jobs[job_id] = {"job_id": job_id, "workflow": "ndvi-source-probe", "status": "queued",
                        "requested_at": now(), "request": {}, "run_id": None, "started_at": None,
                        "finished_at": None, "error": None, "output_tail": None}
    threading.Thread(target=run_cdse_source_probe, args=(job_id, "ndvi"), daemon=True).start()
    return jobs[job_id]


@app.post("/runs/swi-source-probe/development-test", status_code=202)
def start_swi_source_probe():
    """Inspect the latest SWI catalogue timestamp; never download imagery."""
    with jobs_lock:
        if any(job["status"] in {"queued", "running"} for job in jobs.values()):
            raise HTTPException(status_code=409, detail="A drought refresh job is already active")
        job_id = str(uuid.uuid4())
        jobs[job_id] = {"job_id": job_id, "workflow": "swi-source-probe", "status": "queued",
                        "requested_at": now(), "request": {}, "run_id": None, "started_at": None,
                        "finished_at": None, "error": None, "output_tail": None}
    threading.Thread(target=run_cdse_source_probe, args=(job_id, "swi"), daemon=True).start()
    return jobs[job_id]


@app.post("/runs/ndvi-tabia-summary/development-test", status_code=202)
def start_ndvi_tabia_summary():
    """Run one bounded Tigray NDVI raster/Tabia development artifact."""
    with jobs_lock:
        if any(job["status"] in {"queued", "running"} for job in jobs.values()):
            raise HTTPException(status_code=409, detail="A drought refresh job is already active")
        job_id = str(uuid.uuid4())
        jobs[job_id] = {"job_id": job_id, "workflow": "ndvi-tabia-summary",
                        "status": "queued", "requested_at": now(), "request": {}, "run_id": None,
                        "started_at": None, "finished_at": None, "error": None, "output_tail": None}
    threading.Thread(target=run_ndvi_tabia_summary, args=(job_id,), daemon=True).start()
    return jobs[job_id]

@app.post("/runs/swi-tabia-summary/development-test", status_code=202)
def start_swi_tabia_summary():
    with jobs_lock:
        if any(job["status"] in {"queued", "running"} for job in jobs.values()): raise HTTPException(status_code=409, detail="A drought refresh job is already active")
        job_id=str(uuid.uuid4()); jobs[job_id]={"job_id":job_id,"workflow":"swi-tabia-summary","status":"queued","requested_at":now(),"request":{},"run_id":None,"started_at":None,"finished_at":None,"error":None,"output_tail":None}
    threading.Thread(target=run_swi_tabia_summary,args=(job_id,),daemon=True).start(); return jobs[job_id]


@app.post("/runs/lst-tabia-summary/development-test", status_code=202)
def start_lst_tabia_summary():
    """Run one bounded Tigray LST evidence artifact; never publishes it."""
    with jobs_lock:
        if any(job["status"] in {"queued", "running"} for job in jobs.values()): raise HTTPException(status_code=409, detail="A drought refresh job is already active")
        job_id = str(uuid.uuid4()); jobs[job_id] = {"job_id": job_id, "workflow": "lst-tabia-summary", "status": "queued", "requested_at": now(), "request": {}, "run_id": None, "started_at": None, "finished_at": None, "error": None, "output_tail": None}
    threading.Thread(target=run_lst_tabia_summary, args=(job_id,), daemon=True).start(); return jobs[job_id]


@app.post("/runs/wapor-probe/development-test", status_code=202)
def start_wapor_probe():
    """Run the credential-free FAO catalogue probe; no raster is downloaded."""
    with jobs_lock:
        if any(job["status"] in {"queued", "running"} for job in jobs.values()): raise HTTPException(status_code=409, detail="A drought refresh job is already active")
        job_id=str(uuid.uuid4()); jobs[job_id] = {"job_id": job_id, "workflow": "wapor-source-probe", "status": "queued", "requested_at": now(), "request": {}, "run_id": None, "started_at": None, "finished_at": None, "error": None, "output_tail": None}
    threading.Thread(target=run_wapor_probe, args=(job_id,), daemon=True).start(); return jobs[job_id]


@app.post("/runs/seasonal-baseline-availability/development-test", status_code=202)
def start_seasonal_baseline_availability_preflight():
    """Run a fixed, metadata-only historical source availability check."""
    with jobs_lock:
        if any(job["status"] in {"queued", "running"} for job in jobs.values()):
            raise HTTPException(status_code=409, detail="A drought refresh job is already active")
        job_id = str(uuid.uuid4())
        jobs[job_id] = {"job_id": job_id, "workflow": "seasonal-baseline-availability",
                        "status": "queued", "requested_at": now(), "request": {}, "run_id": None,
                        "started_at": None, "finished_at": None, "error": None, "output_tail": None}
    threading.Thread(target=run_seasonal_baseline_availability_preflight, args=(job_id,), daemon=True).start()
    return jobs[job_id]


@app.post("/runs/seasonal-baseline-pilot/development-test", status_code=202)
def start_seasonal_baseline_pilot():
    """Run only the hard-coded pilot; no dates, model rules, or publish action are accepted."""
    with jobs_lock:
        if any(job["status"] in {"queued", "running"} for job in jobs.values()):
            raise HTTPException(status_code=409, detail="A drought refresh job is already active")
        job_id = str(uuid.uuid4())
        jobs[job_id] = {"job_id": job_id, "workflow": "seasonal-baseline-pilot",
                        "status": "queued", "requested_at": now(), "request": {}, "run_id": None,
                        "started_at": None, "finished_at": None, "error": None, "output_tail": None}
    threading.Thread(target=run_seasonal_baseline_pilot, args=(job_id,), daemon=True).start()
    return jobs[job_id]


@app.post("/runs/seasonal-reference-history/development-test", status_code=202)
def start_seasonal_reference_history():
    """Run the fixed candidate history and its separate review-required reference; accepts no inputs."""
    with jobs_lock:
        if any(job["status"] in {"queued", "running"} for job in jobs.values()):
            raise HTTPException(status_code=409, detail="A drought refresh job is already active")
        job_id = str(uuid.uuid4())
        jobs[job_id] = {"job_id": job_id, "workflow": "seasonal-reference-history", "status": "queued",
                        "requested_at": now(), "request": {}, "run_id": None, "started_at": None,
                        "finished_at": None, "error": None, "output_tail": None}
    threading.Thread(target=run_seasonal_reference_history, args=(job_id,), daemon=True).start()
    return jobs[job_id]


@app.post("/runs/wapor-tabia-summary/development-test", status_code=202)
def start_wapor_tabia_summary():
    """Run one bounded WaPOR T/AETI Tigray development artifact."""
    with jobs_lock:
        if any(job["status"] in {"queued", "running"} for job in jobs.values()): raise HTTPException(status_code=409, detail="A drought refresh job is already active")
        job_id=str(uuid.uuid4()); jobs[job_id] = {"job_id": job_id, "workflow": "wapor-tabia-summary", "status": "queued", "requested_at": now(), "request": {}, "run_id": None, "started_at": None, "finished_at": None, "error": None, "output_tail": None}
    threading.Thread(target=run_wapor_tabia_summary, args=(job_id,), daemon=True).start(); return jobs[job_id]


@app.post("/runs/storage-inventory/development-test", status_code=202)
def start_storage_inventory():
    """Run a read-only capacity inventory for the local drought data mount."""
    with jobs_lock:
        if any(job["status"] in {"queued", "running"} for job in jobs.values()):
            raise HTTPException(status_code=409, detail="A drought refresh job is already active")
        job_id = str(uuid.uuid4())
        jobs[job_id] = {"job_id": job_id, "workflow": "storage-inventory",
                        "status": "queued", "requested_at": now(), "request": {}, "run_id": None,
                        "started_at": None, "finished_at": None, "error": None, "output_tail": None}
    threading.Thread(target=run_storage_inventory, args=(job_id,), daemon=True).start()
    return jobs[job_id]


@app.post("/runs/priority-historical-replay/development-test", status_code=202)
def start_priority_historical_replay():
    """Run Jan--Aug draft replays from the active local Model Studio definition.

    It accepts no dates, rules, source URLs or publish instruction.  It is not
    scheduled and cannot create an outlook or future priority product.
    """
    with jobs_lock:
        if any(job["status"] in {"queued", "running"} for job in jobs.values()):
            raise HTTPException(status_code=409, detail="A drought refresh job is already active")
        job_id = str(uuid.uuid4())
        jobs[job_id] = {"job_id": job_id, "workflow": "priority-historical-replay",
                        "status": "queued", "requested_at": now(), "request": {}, "run_id": None,
                        "started_at": None, "finished_at": None, "error": None, "output_tail": None}
    threading.Thread(target=run_priority_historical_replay, args=(job_id,), daemon=True).start()
    return jobs[job_id]


@app.post("/runs/seasonal-outlook-probe/development-test", status_code=202)
def start_seasonal_outlook_probe():
    """Probe the fixed ICPAC catalogue; it cannot ingest or publish an outlook."""
    with jobs_lock:
        if any(job["status"] in {"queued", "running"} for job in jobs.values()):
            raise HTTPException(status_code=409, detail="A drought refresh job is already active")
        job_id = str(uuid.uuid4())
        jobs[job_id] = {"job_id": job_id, "workflow": "seasonal-outlook-probe",
                        "status": "queued", "requested_at": now(), "request": {}, "run_id": None,
                        "started_at": None, "finished_at": None, "error": None, "output_tail": None}
    threading.Thread(target=run_seasonal_outlook_probe, args=(job_id,), daemon=True).start()
    return jobs[job_id]


@app.post("/runs/fews-net-food-security-probe/development-test", status_code=202)
def start_fews_net_food_security_probe():
    """Discover public FEWS NET assets only; no layer is downloaded, loaded, or published."""
    with jobs_lock:
        if any(job["status"] in {"queued", "running"} for job in jobs.values()):
            raise HTTPException(status_code=409, detail="A drought refresh job is already active")
        job_id = str(uuid.uuid4())
        jobs[job_id] = {"job_id": job_id, "workflow": "fews-net-food-security-probe",
                        "status": "queued", "requested_at": now(), "request": {}, "run_id": None,
                        "started_at": None, "finished_at": None, "error": None, "output_tail": None}
    threading.Thread(target=run_fews_net_food_security_probe, args=(job_id,), daemon=True).start()
    return jobs[job_id]


@app.post("/runs/c3s-seasonal-access-probe/development-test", status_code=202)
def start_c3s_seasonal_access_probe():
    """Test CDS seasonal access with one temporary bounded request only."""
    with jobs_lock:
        if any(job["status"] in {"queued", "running"} for job in jobs.values()):
            raise HTTPException(status_code=409, detail="A drought refresh job is already active")
        job_id = str(uuid.uuid4())
        jobs[job_id] = {"job_id": job_id, "workflow": "c3s-seasonal-access-probe",
                        "status": "queued", "requested_at": now(), "request": {}, "run_id": None,
                        "started_at": None, "finished_at": None, "error": None, "output_tail": None}
    threading.Thread(target=run_c3s_seasonal_access_probe, args=(job_id,), daemon=True).start()
    return jobs[job_id]


@app.post("/runs/c3s-seasonal-hindcast-probe/development-test", status_code=202)
def start_c3s_seasonal_hindcast_probe():
    """Test one matched hindcast request; no values are retained or published."""
    with jobs_lock:
        if any(job["status"] in {"queued", "running"} for job in jobs.values()):
            raise HTTPException(status_code=409, detail="A drought refresh job is already active")
        job_id = str(uuid.uuid4())
        jobs[job_id] = {"job_id": job_id, "workflow": "c3s-seasonal-hindcast-probe",
                        "status": "queued", "requested_at": now(), "request": {}, "run_id": None,
                        "started_at": None, "finished_at": None, "error": None, "output_tail": None}
    threading.Thread(target=run_c3s_seasonal_hindcast_probe, args=(job_id,), daemon=True).start()
    return jobs[job_id]


@app.post("/runs/c3s-seasonal-skill-pilot/development-test", status_code=202)
def start_c3s_seasonal_skill_pilot():
    """Start the fixed technical skill pilot; it cannot publish an Outlook."""
    with jobs_lock:
        if any(job["status"] in {"queued", "running"} for job in jobs.values()):
            raise HTTPException(status_code=409, detail="A drought refresh job is already active")
        job_id = str(uuid.uuid4())
        jobs[job_id] = {"job_id": job_id, "workflow": "c3s-seasonal-skill-pilot",
                        "status": "queued", "requested_at": now(), "request": {}, "run_id": None,
                        "started_at": None, "finished_at": None, "error": None, "output_tail": None}
    threading.Thread(target=run_c3s_seasonal_skill_pilot, args=(job_id,), daemon=True).start()
    return jobs[job_id]


@app.post("/runs/c3s-august-lead-comparison/development-test", status_code=202)
def start_c3s_august_lead_comparison():
    """Run fixed August two- and three-month lead diagnostics; never publish an Outlook."""
    with jobs_lock:
        if any(job["status"] in {"queued", "running"} for job in jobs.values()):
            raise HTTPException(status_code=409, detail="A drought refresh job is already active")
        job_id = str(uuid.uuid4())
        jobs[job_id] = {"job_id": job_id, "workflow": "c3s-august-lead-comparison",
                        "status": "queued", "requested_at": now(), "request": {}, "run_id": None,
                        "started_at": None, "finished_at": None, "error": None, "output_tail": None}
    threading.Thread(target=run_c3s_august_lead_comparison, args=(job_id,), daemon=True).start()
    return jobs[job_id]


@app.post("/runs/swi-access/development-test", status_code=202)
def start_swi_access_check():
    """Run one metadata-only CDSE SWI collection access check."""
    with jobs_lock:
        if any(job["status"] in {"queued", "running"} for job in jobs.values()):
            raise HTTPException(status_code=409, detail="A drought refresh job is already active")
        job_id = str(uuid.uuid4())
        jobs[job_id] = {"job_id": job_id, "workflow": "swi-access-check", "status": "queued",
                        "requested_at": now(), "request": {}, "run_id": None, "started_at": None,
                        "finished_at": None, "error": None, "output_tail": None}
    threading.Thread(target=run_swi_access_check, args=(job_id,), daemon=True).start()
    return jobs[job_id]


@app.post("/runs/lst-access/development-test", status_code=202)
def start_lst_access_check():
    with jobs_lock:
        if any(job["status"] in {"queued", "running"} for job in jobs.values()): raise HTTPException(status_code=409, detail="A drought refresh job is already active")
        job_id = str(uuid.uuid4()); jobs[job_id] = {"job_id": job_id, "workflow": "lst-access-check", "status": "queued", "requested_at": now(), "request": {}, "run_id": None, "started_at": None, "finished_at": None, "error": None, "output_tail": None}
    threading.Thread(target=run_lst_access_check, args=(job_id,), daemon=True).start(); return jobs[job_id]


@app.get("/runs/{job_id}")
def get_job(job_id: str):
    """Return redacted state for an in-memory local development job.

    The runner has no host port, job identifiers are random, and this route
    cannot start work or accept any user-supplied command/URL/SQL/path.  It is
    intentionally readable by local n8n so workflows can record outcomes
    without duplicating the runner token in n8n credentials.
    """
    with jobs_lock:
        job = jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Unknown drought runner job")
        return job


@app.get("/runs/development-test/{job_id}")
def get_development_test_job(job_id: str):
    """Read a fixed, internal development job without exposing runner tokens."""
    with jobs_lock:
        job = jobs.get(job_id)
        if not job or job["workflow"] not in {
            "observed-climate-refresh", "chirps-preliminary-pentad-probe", "chirps-preliminary-pentad-summary",
            "chirps-preliminary-pentad-baseline", "ndvi-access-check", "ndvi-tabia-summary", "swi-access-check", "swi-tabia-summary", "lst-access-check", "lst-tabia-summary"
        }:
            raise HTTPException(status_code=404, detail="Unknown development test job")
        return job
