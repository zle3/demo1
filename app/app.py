import os
from flask import Flask, jsonify, request
import requests

app = Flask(__name__)

METADATA_HEADERS = {"Metadata-Flavor": "Google"}
METADATA_BASE = "http://metadata.google.internal/computeMetadata/v1"

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
    background: rgb(var(--color-secondary-300));
    box-shadow: 0 0 8px rgb(var(--color-secondary-300));
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
  .pill { font-size: 10px; padding: 2px 8px; border-radius: 20px; font-weight: 700; }
  .pill.unverified { background: rgb(var(--color-neutral-700)); color: rgb(var(--color-neutral-400)); }
  .pill.verified { background: rgb(var(--color-secondary-300)); color: white; }

  .reveal {
    cursor: pointer;
    color: rgb(var(--color-primary-300));
    border-bottom: 1px dashed rgb(var(--color-primary-400));
  }

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

    <button class="verify" id="verifyBtn" onclick="runVerify()">Verify this is really running on GCP + Cloudflare</button>

    <h2 class="section">Stack</h2>
    <div class="grid" id="grid">
      <div class="card" id="card-gcp">
        <div class="title">GCP <span class="pill unverified" id="pill-gcp">unverified</span></div>
        <div class="desc" id="desc-gcp">Click verify to query GCP's internal metadata server, only reachable from inside a real GCP resource.</div>
      </div>
      <div class="card" id="card-compute">
        <div class="title">Compute Platform <span class="pill unverified" id="pill-compute">unverified</span></div>
        <div class="desc" id="desc-compute">Click verify to read the platform-specific environment this process is actually running in.</div>
      </div>
      <div class="card" id="card-cf">
        <div class="title">Cloudflare <span class="pill unverified" id="pill-cf">unverified</span></div>
        <div class="desc" id="desc-cf">Click verify to inspect the request headers Cloudflare injects at the edge.</div>
      </div>
      <div class="card">
        <div class="title">Provisioning</div>
        <div class="desc">Every resource above defined as code in Terraform, planned before applied.</div>
      </div>
    </div>

    <a class="repo" href="https://github.com/zle3/demo1" target="_blank" rel="noopener">View source on GitHub &rarr;</a>
    <footer>built by <a href="https://zachle.info" target="_blank" rel="noopener">Zach Le</a> &middot; terraform &middot; docker &middot; gcp &middot; cloudflare</footer>
  </div>

<script>
let lastIp = null;

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
        `CF-Ray: <code>${data.cf_ray}</code><br>Your IP per Cloudflare: <span class="reveal" onclick="revealIp(this)">click to reveal</span><br>Detected country: <code>${data.cf_country}</code>`;
    } else {
      setPill('cf', false);
      document.getElementById('desc-cf').textContent = 'No CF-Ray header present, this request did not pass through Cloudflare.';
    }
  } catch (e) {
    btn.textContent = 'Check failed, see console';
    console.error(e);
    return;
  }
  btn.textContent = 'Verified';
}

function revealIp(el) {
  el.outerHTML = `<code>${lastIp}</code>`;
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
    from flask import send_from_directory
    return send_from_directory(os.path.join(app.root_path, "static"), "favicon.ico")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)