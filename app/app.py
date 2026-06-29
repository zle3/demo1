import os
import time
from datetime import datetime, timezone
from flask import Flask, jsonify, request, send_from_directory
import requests
from google.cloud.devtools import cloudbuild_v1
from google.cloud import monitoring_v3
from google.cloud.sql.connector import Connector, IPTypes
import sqlalchemy

app = Flask(__name__)

METADATA_HEADERS = {"Metadata-Flavor": "Google"}
METADATA_BASE = "http://metadata.google.internal/computeMetadata/v1"
PROJECT_ID = "demo1-500618"
REGION = "us-central1"
MAX_BUILDS = 20

DB_INSTANCE_CONNECTION_NAME = "demo1-500618:us-central1:demo1-postgres"
DB_NAME = "demo1"
DB_USER = "app_user"
DB_PASS = os.environ.get("DB_PASSWORD")

_connector = Connector()
_engine = None


def get_db_engine():
    def getconn():
        return _connector.connect(
            DB_INSTANCE_CONNECTION_NAME,
            "pg8000",
            user=DB_USER,
            password=DB_PASS,
            db=DB_NAME,
            ip_type=IPTypes.PRIVATE,
        )
    return sqlalchemy.create_engine("postgresql+pg8000://", creator=getconn)


def get_engine():
    global _engine
    if _engine is None:
        _engine = get_db_engine()
        with _engine.connect() as conn:
            conn.execute(sqlalchemy.text(
                "CREATE TABLE IF NOT EXISTS visits (id SERIAL PRIMARY KEY, visited_at TIMESTAMPTZ DEFAULT now())"
            ))
            conn.commit()
    return _engine


@app.route("/api/verify")
def verify():
    info = {}

    try:
        project = requests.get(f"{METADATA_BASE}/project/project-id",
                                headers=METADATA_HEADERS, timeout=2).text
        zone_path = requests.get(f"{METADATA_BASE}/instance/zone",
                                  headers=METADATA_HEADERS, timeout=2).text
        instance_id = requests.get(f"{METADATA_BASE}/instance/id",
                                    headers=METADATA_HEADERS, timeout=2).text
        info["gcp_verified"] = True
        info["gcp_project"] = project
        info["gcp_zone"] = zone_path.split("/")[-1]
        info["gcp_instance_id"] = instance_id
    except Exception as e:
        info["gcp_verified"] = False
        info["gcp_error"] = str(e)

    k_service = os.environ.get("K_SERVICE")
    info["platform"] = "Cloud Run" if k_service else "Compute Engine"
    info["k_service"] = k_service
    info["k_revision"] = os.environ.get("K_REVISION")

    cf_ray = request.headers.get("CF-Ray")
    info["cloudflare_verified"] = cf_ray is not None
    info["cf_ray"] = cf_ray
    info["cf_connecting_ip"] = request.headers.get("CF-Connecting-IP")
    info["cf_country"] = request.headers.get("CF-IPCountry")

    return jsonify(info)


@app.route("/api/docker")
def docker_info():
    info = {}

    try:
        info["hostname"] = os.uname().nodename
    except Exception as e:
        info["hostname"] = None
        info["hostname_error"] = str(e)

    info["dockerenv_present"] = os.path.exists("/.dockerenv")

    try:
        with open("/proc/1/cgroup", "r") as f:
            cgroup_content = f.read().strip()
        info["cgroup_excerpt"] = cgroup_content.splitlines()[:5]
        info["containerized"] = any(
            kw in cgroup_content for kw in ("docker", "containerd", "kubepods", "container")
        )
    except Exception as e:
        info["cgroup_excerpt"] = []
        info["containerized"] = None
        info["cgroup_error"] = str(e)

    info["pid"] = os.getpid()
    info["k_service"] = os.environ.get("K_SERVICE")
    info["k_revision"] = os.environ.get("K_REVISION")

    return jsonify(info)


@app.route("/api/db")
def db_info():
    info = {
        "instance_connection_name": DB_INSTANCE_CONNECTION_NAME,
        "ip_type": "PRIVATE",
    }
    try:
        engine = get_engine()
        start = time.time()
        with engine.connect() as conn:
            count = conn.execute(sqlalchemy.text("SELECT COUNT(*) FROM visits")).scalar()
        info["connected"] = True
        info["latency_ms"] = round((time.time() - start) * 1000, 1)
        info["total_visits"] = count
    except Exception as e:
        info["connected"] = False
        info["error"] = str(e)
    return jsonify(info)


@app.route("/api/builds")
def builds():
    try:
        client = cloudbuild_v1.CloudBuildClient()
        request_obj = cloudbuild_v1.ListBuildsRequest(
            project_id=PROJECT_ID,
            parent=f"projects/{PROJECT_ID}/locations/{REGION}",
            page_size=MAX_BUILDS,
        )
        results = []
        for build in client.list_builds(request=request_obj):
            results.append({
                "id": build.id[:8],
                "status": build.status.name,
                "sha": build.substitutions.get("SHORT_SHA", "manual"),
                "create_time": build.create_time.isoformat() if build.create_time else None,
            })
            if len(results) >= MAX_BUILDS:
                break
        return jsonify({"ok": True, "builds": results})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route("/api/uptime/history")
def uptime_history():
    days = int(request.args.get("days", 30))
    try:
        client = monitoring_v3.MetricServiceClient()
        project_name = f"projects/{PROJECT_ID}"
        now = time.time()
        interval = monitoring_v3.TimeInterval({
            "end_time": {"seconds": int(now)},
            "start_time": {"seconds": int(now - days * 86400)},
        })
        aggregation = monitoring_v3.Aggregation({
            "alignment_period": {"seconds": 86400},
            "per_series_aligner": monitoring_v3.Aggregation.Aligner.ALIGN_FRACTION_TRUE,
        })
        results = client.list_time_series(
            request={
                "name": project_name,
                "filter": 'metric.type="monitoring.googleapis.com/uptime_check/check_passed"',
                "interval": interval,
                "aggregation": aggregation,
                "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
            }
        )

        day_buckets = {}
        for series in results:
            for point in series.points:
                day = datetime.fromtimestamp(
                    point.interval.end_time.timestamp(), tz=timezone.utc
                ).strftime("%Y-%m-%d")
                day_buckets[day] = round(point.value.double_value * 100, 2)

        history = [{"date": d, "uptime_pct": day_buckets[d]} for d in sorted(day_buckets)]
        return jsonify({"ok": True, "history": history})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route("/api/visit", methods=["POST"])
def record_visit():
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(sqlalchemy.text("INSERT INTO visits DEFAULT VALUES"))
            conn.commit()
            count = conn.execute(sqlalchemy.text("SELECT COUNT(*) FROM visits")).scalar()
        return jsonify({"ok": True, "total_visits": count})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route("/api/visits")
def get_visits():
    try:
        engine = get_engine()
        with engine.connect() as conn:
            count = conn.execute(sqlalchemy.text("SELECT COUNT(*) FROM visits")).scalar()
        return jsonify({"ok": True, "total_visits": count})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>demo1 — GCP Infrastructure Project</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="icon" href="/favicon.ico">
<style>
  :root {
    --color-neutral-200: 249,249,251;
    --color-neutral-300: 205,205,219;
    --color-neutral-400: 160,160,187;
    --color-neutral-700: 79,79,110;
    --color-neutral-800: 62,62,86;
    --color-neutral-900: 45,45,63;
    --color-primary-300: 217,198,208;
    --color-primary-400: 186,153,170;
    --color-primary-500: 155,107,132;
    --color-secondary-300: 196,26,64;
    --color-success: 90,168,110;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    background: rgb(var(--color-neutral-900));
    color: rgb(var(--color-neutral-300));
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    padding: 56px 24px 80px;
  }
  .wrap { max-width: 760px; margin: 0 auto; text-align: center; }
  .badge {
    display: inline-flex; align-items: center; gap: 8px; font-size: 13px;
    color: rgb(var(--color-primary-300));
    border: 1px solid rgb(var(--color-neutral-700));
    border-radius: 20px; padding: 5px 14px; margin-bottom: 28px;
  }
  .dot {
    width: 7px; height: 7px; border-radius: 50%;
    background: rgb(var(--color-success));
    box-shadow: 0 0 8px rgb(var(--color-success));
  }
  h1 { font-size: 32px; font-weight: 700; color: rgb(var(--color-neutral-200)); margin: 0 0 6px; }
  .role { color: rgb(var(--color-neutral-400)); font-size: 16px; margin-bottom: 24px; }
  .sub { color: rgb(var(--color-neutral-400)); font-size: 15px; line-height: 1.7; max-width: 600px; margin: 0 auto 32px; }
  .sub a { color: rgb(var(--color-primary-400)); text-decoration: none; }
  .sub a:hover { color: rgb(var(--color-primary-300)); }

  button.verify {
    background: rgb(var(--color-primary-500));
    color: rgb(var(--color-neutral-200));
    border: none; font-weight: 600; font-size: 14px;
    padding: 12px 24px; border-radius: 8px; cursor: pointer;
    margin-bottom: 36px;
  }
  button.verify:hover { background: rgb(var(--color-primary-400)); }
  button.verify:disabled { opacity: 0.6; cursor: default; }

  h2.section { text-align: left; font-size: 20px; font-weight: 700; color: rgb(var(--color-neutral-200)); margin: 0 0 16px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px; margin-bottom: 36px; text-align: left; }
  .card { background: rgb(var(--color-neutral-800)); border: 1px solid rgb(var(--color-neutral-700)); border-radius: 10px; padding: 18px 20px; }
  .card .title { color: rgb(var(--color-neutral-200)); font-weight: 700; font-size: 15px; margin-bottom: 6px; display: flex; justify-content: space-between; align-items: center; }
  .card .desc { color: rgb(var(--color-neutral-400)); font-size: 13px; line-height: 1.6; }
  .card .desc code { color: rgb(var(--color-primary-300)); font-size: 12px; word-break: break-all; }
  .card .desc code.ip { word-break: normal; white-space: nowrap; display: inline-block; margin-left: 4px; }
  .ip-row { margin-top: 2px; }
  .pill { font-size: 10px; padding: 2px 8px; border-radius: 20px; font-weight: 700; }
  .pill.unverified { background: rgb(var(--color-neutral-700)); color: rgb(var(--color-neutral-400)); }
  .pill.verified { background: rgb(var(--color-success)); color: white; }

  .reveal {
    cursor: pointer;
    color: rgb(var(--color-primary-300));
    border-bottom: 1px dashed rgb(var(--color-primary-400));
    margin-left: 4px;
  }

  .buildrow { margin-bottom: 10px; }

  .pagination {
    display: flex; align-items: center; justify-content: space-between;
    margin-bottom: 36px;
  }
  .pagination button {
    background: rgb(var(--color-neutral-800));
    border: 1px solid rgb(var(--color-neutral-700));
    color: rgb(var(--color-neutral-200));
    font-weight: 600; font-size: 13px;
    padding: 8px 16px; border-radius: 8px; cursor: pointer;
  }
  .pagination button:hover:not(:disabled) { border-color: rgb(var(--color-primary-400)); }
  .pagination button:disabled { opacity: 0.4; cursor: default; }
  .pagination .page-label { font-size: 13px; color: rgb(var(--color-neutral-400)); }

  .visits-banner {
    background: rgb(var(--color-neutral-800));
    border: 1px solid rgb(var(--color-neutral-700));
    border-radius: 10px;
    padding: 16px 20px;
    margin-bottom: 14px;
    text-align: left;
  }
  .visits-banner .count { color: rgb(var(--color-primary-300)); font-weight: 700; font-size: 20px; }

  .statusbar-wrap {
    text-align: left;
    margin-bottom: 36px;
    background: rgb(var(--color-neutral-800));
    border: 1px solid rgb(var(--color-neutral-700));
    border-radius: 10px;
    padding: 12px 20px;
  }
  .statusbar-row { display: flex; gap: 2px; height: 14px; align-items: flex-end; }
  .statusbar-bar {
    flex: 1; min-width: 3px; border-radius: 2px; height: 100%;
    background: rgb(var(--color-neutral-700));
    cursor: pointer; position: relative;
  }
  .statusbar-bar.up { background: rgb(var(--color-success)); }
  .statusbar-bar.degraded { background: #d29922; }
  .statusbar-bar.down { background: rgb(var(--color-secondary-300)); }
  .statusbar-labels { display: flex; justify-content: space-between; font-size: 11px; color: rgb(var(--color-neutral-400)); margin-top: 6px; }
  .statusbar-summary { font-size: 13px; color: rgb(var(--color-neutral-400)); margin-top: 6px; }

  a.repo {
    display: inline-flex; align-items: center; gap: 8px;
    background: rgb(var(--color-neutral-800));
    border: 1px solid rgb(var(--color-neutral-700));
    color: rgb(var(--color-neutral-200));
    text-decoration: none; font-weight: 600; font-size: 14px;
    padding: 11px 22px; border-radius: 8px;
  }
  a.repo:hover { border-color: rgb(var(--color-primary-400)); }
  footer { margin-top: 48px; color: rgb(var(--color-neutral-700)); font-size: 12px; }
  footer a { color: rgb(var(--color-neutral-400)); text-decoration: none; }
  footer a:hover { color: rgb(var(--color-primary-300)); }
</style>
</head>
<body>
  <div class="wrap">
    <div class="badge"><span class="dot"></span> live on Cloud Run</div>
    <h1>demo1</h1>
    <div class="role">GCP Infrastructure Project</div>
    <p class="sub">
      A self-built GCP infrastructure project, provisioned entirely through Terraform,
      containerized with Docker, and fronted by Cloudflare.
      <a href="https://github.com/zle3/demo1" target="_blank" rel="noopener">Full source and Terraform code on GitHub</a>.
    </p>

    <div class="visits-banner" id="visitsBanner">Recording visit...</div>

    <div class="statusbar-wrap" id="statusbarWrap">
      <div class="statusbar-row" id="statusbarRow"></div>
      <div class="statusbar-labels">
        <span id="statusbarOldest">30 days ago</span>
        <span id="statusbarNewest">Today</span>
      </div>
      <div class="statusbar-summary" id="statusbarSummary">Loading uptime history...</div>
    </div>

    <button class="verify" id="verifyBtn" onclick="runVerify()">Re-verify GCP + Cloudflare</button>

    <h2 class="section">Stack</h2>
    <div class="grid" id="grid">
      <div class="card" id="card-gcp">
        <div class="title">GCP <span class="pill unverified" id="pill-gcp">checking...</span></div>
        <div class="desc" id="desc-gcp">Querying GCP's internal metadata server, only reachable from inside a real GCP resource.</div>
      </div>
      <div class="card" id="card-compute">
        <div class="title">Compute Platform <span class="pill unverified" id="pill-compute">checking...</span></div>
        <div class="desc" id="desc-compute">Reading the platform-specific environment this process is actually running in.</div>
      </div>
      <div class="card" id="card-cf">
        <div class="title">Cloudflare <span class="pill unverified" id="pill-cf">checking...</span></div>
        <div class="desc" id="desc-cf">Inspecting the request headers Cloudflare injects at the edge.</div>
      </div>
      <div class="card" id="card-docker">
        <div class="title">Docker <span class="pill unverified" id="pill-docker">checking...</span></div>
        <div class="desc" id="desc-docker">Checking for container-runtime markers (hostname, cgroup namespace, /.dockerenv).</div>
      </div>
      <div class="card" id="card-db">
        <div class="title">Cloud SQL <span class="pill unverified" id="pill-db">checking...</span></div>
        <div class="desc" id="desc-db">Connecting over the instance's private IP and timing a live query.</div>
      </div>
    </div>

    <h2 class="section">Infrastructure as Code</h2>
    <div class="grid">
      <div class="card">
        <div class="title">Provisioning</div>
        <div class="desc">Every resource above defined as code in Terraform, planned before applied.</div>
      </div>
    </div>

    <h2 class="section">CI/CD Pipeline</h2>
    <button class="verify" id="buildsBtn" onclick="loadBuilds()">Load recent Cloud Build runs</button>
    <div id="buildsList" style="text-align:left;"></div>
    <div class="pagination" id="buildsPagination" style="display:none;">
      <button id="buildsPrevBtn" onclick="changeBuildsPage(-1)">&larr; Prev</button>
      <span class="page-label" id="buildsPageLabel"></span>
      <button id="buildsNextBtn" onclick="changeBuildsPage(1)">Next &rarr;</button>
    </div>

    <a class="repo" href="https://github.com/zle3/demo1" target="_blank" rel="noopener">View source on GitHub &rarr;</a>
    <footer>built by <a href="https://zachle.info" target="_blank" rel="noopener">Zach Le</a> &middot; terraform &middot; docker &middot; gcp &middot; cloudflare</footer>
  </div>

<script>
let lastIp = null;
let allBuilds = [];
let buildsPage = 0;
const BUILDS_PER_PAGE = 5;

async function runVerify() {
  const btn = document.getElementById('verifyBtn');
  btn.disabled = true;
  btn.textContent = 'Checking...';
  try {
    const res = await fetch('/api/verify');
    const data = await res.json();

    if (data.gcp_verified) {
      setPill('gcp', true);
      document.getElementById('desc-gcp').innerHTML =
        `Project: <code>${data.gcp_project}</code><br>Zone: <code>${data.gcp_zone}</code><br>Instance ID: <code>${data.gcp_instance_id}</code>`;
    } else {
      setPill('gcp', false);
      document.getElementById('desc-gcp').textContent = 'Metadata server unreachable: ' + data.gcp_error;
    }

    setPill('compute', true);
    document.getElementById('desc-compute').innerHTML =
      `Running on: <code>${data.platform}</code>` +
      (data.k_service ? `<br>Service: <code>${data.k_service}</code><br>Revision: <code>${data.k_revision}</code>` : '');

    if (data.cloudflare_verified) {
      setPill('cf', true);
      lastIp = data.cf_connecting_ip;
      document.getElementById('desc-cf').innerHTML =
        `CF-Ray: <code>${data.cf_ray}</code><br>Detected country: <code>${data.cf_country}</code>` +
        `<div class="ip-row">Your IP per Cloudflare: <span class="reveal" onclick="revealIp(this)">click to reveal</span></div>`;
    } else {
      setPill('cf', false);
      document.getElementById('desc-cf').textContent = 'No CF-Ray header present, this request did not pass through Cloudflare.';
    }
  } catch (e) {
    btn.textContent = 'Check failed, see console';
    console.error(e);
    return;
  }
  btn.disabled = false;
  btn.textContent = 'Re-verify GCP + Cloudflare';
}

async function runDockerCheck() {
  try {
    const res = await fetch('/api/docker');
    const data = await res.json();
    const ok = data.dockerenv_present || data.containerized || !!data.k_service;
    setPill('docker', !!ok);
    const cgroupLines = (data.cgroup_excerpt || []).join('<br>');
    document.getElementById('desc-docker').innerHTML =
      `Hostname (container ID-style): <code>${data.hostname}</code><br>` +
      `/.dockerenv present: <code>${data.dockerenv_present}</code><br>` +
      `cgroup namespace isolated: <code>${data.containerized}</code><br>` +
      (cgroupLines ? `cgroup excerpt:<br><code>${cgroupLines}</code><br>` : '') +
      `PID inside container: <code>${data.pid}</code>` +
      (data.k_revision ? `<br>Cloud Run revision (built from this image): <code>${data.k_revision}</code>` : '');
  } catch (e) {
    setPill('docker', false);
    document.getElementById('desc-docker').textContent = 'Could not reach /api/docker.';
    console.error(e);
  }
}

async function runDbCheck() {
  try {
    const res = await fetch('/api/db');
    const data = await res.json();
    setPill('db', !!data.connected);
    if (data.connected) {
      document.getElementById('desc-db').innerHTML =
        `Instance: <code>${data.instance_connection_name}</code><br>` +
        `IP type: <code>${data.ip_type}</code><br>` +
        `Query latency: <code>${data.latency_ms}ms</code><br>` +
        `Rows in visits table: <code>${data.total_visits}</code>`;
    } else {
      document.getElementById('desc-db').innerHTML =
        `Instance: <code>${data.instance_connection_name}</code><br>` +
        `IP type: <code>${data.ip_type}</code><br>` +
        `Connection failed: ${data.error}`;
    }
  } catch (e) {
    setPill('db', false);
    document.getElementById('desc-db').textContent = 'Could not reach /api/db.';
    console.error(e);
  }
}

async function loadBuilds() {
  const btn = document.getElementById('buildsBtn');
  btn.disabled = true;
  btn.textContent = 'Loading...';
  try {
    const res = await fetch('/api/builds');
    const data = await res.json();
    if (!data.ok) {
      document.getElementById('buildsList').innerHTML = `<div class="card">Could not load builds: ${data.error}</div>`;
      document.getElementById('buildsPagination').style.display = 'none';
    } else {
      allBuilds = data.builds;
      buildsPage = 0;
      renderBuildsPage();
    }
  } catch (e) {
    document.getElementById('buildsList').innerHTML = '<div class="card">Failed to load build history.</div>';
    console.error(e);
  }
  btn.disabled = false;
  btn.textContent = 'Refresh';
}

function renderBuildsPage() {
  const list = document.getElementById('buildsList');
  const pagination = document.getElementById('buildsPagination');

  if (allBuilds.length === 0) {
    list.innerHTML = '<div class="card">No builds found.</div>';
    pagination.style.display = 'none';
    return;
  }

  const totalPages = Math.ceil(allBuilds.length / BUILDS_PER_PAGE);
  const start = buildsPage * BUILDS_PER_PAGE;
  const pageItems = allBuilds.slice(start, start + BUILDS_PER_PAGE);

  list.innerHTML = pageItems.map(b => `
    <div class="card buildrow">
      <div class="title">
        build ${b.id}
        <span class="pill ${b.status === 'SUCCESS' ? 'verified' : 'unverified'}">${b.status}</span>
      </div>
      <div class="desc">commit: <code>${b.sha}</code><br>started: <code>${b.create_time || 'n/a'}</code></div>
    </div>
  `).join('');

  pagination.style.display = totalPages > 1 ? 'flex' : 'none';
  document.getElementById('buildsPageLabel').textContent = `Page ${buildsPage + 1} of ${totalPages}`;
  document.getElementById('buildsPrevBtn').disabled = buildsPage === 0;
  document.getElementById('buildsNextBtn').disabled = buildsPage >= totalPages - 1;
}

function changeBuildsPage(delta) {
  const totalPages = Math.ceil(allBuilds.length / BUILDS_PER_PAGE);
  buildsPage = Math.min(Math.max(0, buildsPage + delta), totalPages - 1);
  renderBuildsPage();
}

async function loadUptimeHistory() {
  const row = document.getElementById('statusbarRow');
  const summary = document.getElementById('statusbarSummary');
  try {
    const res = await fetch('/api/uptime/history?days=30');
    const data = await res.json();
    if (!data.ok || data.history.length === 0) {
      summary.textContent = 'No uptime data yet, check was just created.';
      return;
    }
    row.innerHTML = data.history.map(d => {
      let cls = 'up';
      if (d.uptime_pct < 100 && d.uptime_pct >= 95) cls = 'degraded';
      if (d.uptime_pct < 95) cls = 'down';
      return `<div class="statusbar-bar ${cls}" title="${d.date}: ${d.uptime_pct}%"></div>`;
    }).join('');
    const avg = (data.history.reduce((a, d) => a + d.uptime_pct, 0) / data.history.length).toFixed(2);
    summary.textContent = `${avg}% average uptime over ${data.history.length} day(s) tracked`;
  } catch (e) {
    summary.textContent = 'Failed to load uptime history.';
    console.error(e);
  }
}

async function recordVisit() {
  const banner = document.getElementById('visitsBanner');
  try {
    const res = await fetch('/api/visit', { method: 'POST' });
    const data = await res.json();
    if (data.ok) {
      banner.innerHTML = `<span class="count">${data.total_visits}</span> total visits recorded in Cloud SQL`;
    } else {
      banner.textContent = 'Could not reach Cloud SQL: ' + data.error;
    }
  } catch (e) {
    banner.textContent = 'Failed to record visit.';
    console.error(e);
  }
}

window.addEventListener('DOMContentLoaded', () => {
  loadUptimeHistory();
  recordVisit();
  runVerify();
  runDockerCheck();
  runDbCheck();
});

function revealIp(el) {
  el.outerHTML = `<code class="ip">${lastIp}</code>`;
}

function setPill(key, ok) {
  const pill = document.getElementById('pill-' + key);
  pill.textContent = ok ? 'verified' : 'failed';
  pill.classList.toggle('verified', ok);
  pill.classList.toggle('unverified', !ok);
}
</script>
</body>
</html>
"""

@app.route("/")
def home():
    return PAGE

@app.route("/favicon.ico")
def favicon():
    return send_from_directory(os.path.join(app.root_path, "static"), "favicon.ico")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)