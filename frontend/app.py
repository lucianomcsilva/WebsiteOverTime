
import os
import re
import uuid
import time
import datetime
import random
import shutil
from urllib.parse import urlparse
import tldextract as _tldex


def normalize_domain(raw: str) -> str | None:
    """
    Normalize user input to a clean hostname, prepending www. only when
    the input has no subdomain at all.

    Examples:
      google.com              → www.google.com
      www.google.com          → www.google.com
      developer.meugastos.com.br → developer.meugastos.com.br
      meugastos.com.br        → www.meugastos.com.br
    """
    # strip protocol + trailing slashes
    host = re.sub(r'https?://', '', raw.strip().lower()).rstrip('/')
    # strip path/query if any
    host = host.split('/')[0].split('?')[0]

    ext = _tldex.extract(host)
    if not ext.domain or not ext.suffix:
        return None                         # not a valid domain

    if ext.subdomain:
        return f"{ext.subdomain}.{ext.domain}.{ext.suffix}"
    else:
        return f"www.{ext.domain}.{ext.suffix}"

from flask import Flask, jsonify, redirect, render_template, request, send_from_directory
from asgiref.wsgi import WsgiToAsgi
from mangum import Mangum
from s3path import S3Path
import boto3

prefix = 'local-' if os.environ.get('IS_LOCAL') == 'true' else ''
sqs = boto3.resource("sqs")
s3  = boto3.resource("s3")
base_dir = os.path.dirname(os.path.abspath(__file__))

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    BLINK = '\033[5m'

# Configure application
app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True
handler = Mangum(WsgiToAsgi(app), lifespan="off")

@app.after_request
def add_header(r):
    r.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    r.headers["Pragma"] = "no-cache"
    r.headers["Expires"] = "0"
    return r

def get_cache():
    if os.environ.get('IS_LOCAL') == 'true':
        screenshots_dir = os.path.join(base_dir, 'screenshots')
        os.makedirs(screenshots_dir, exist_ok=True)
        return [ f.name for f in os.scandir(screenshots_dir) if (f.is_dir()) and (f.name[-1:] != ')')]
    else:
        try:
            return [item.name for item in S3Path('/websiteovertime/screenshots/').iterdir() if item.is_dir()]
        except Exception:
            return []

#main route...just a search box and a list of hashtags of previous crawllings
@app.route("/", methods=["GET", "POST"])
def index():
    cache = get_cache()
    if request.method == "POST":
        raw_input = request.form.get('url', '').strip()
        domain = normalize_domain(raw_input)
        if not domain:
            return render_template("home.html", cache=cache, error="URL inválida.")
        url = f"http://{domain}"
        print(f"Received '{raw_input}' → normalized to '{domain}'")

        if domain in cache:
            return redirect(f"/{url[7:]}")
        
        

        ct = datetime.datetime.now()
        
        # Send message to SQS queue   
        sqs_queue = sqs.get_queue_by_name(QueueName=f"{prefix}websiteovertime-geturl.fifo")     

        response = sqs_queue.send_message(
            # Per-domain group so multiple domain submissions fan out in parallel.
            MessageGroupId=domain,
            MessageDeduplicationId=f'{uuid.uuid4()}',
            MessageAttributes={
                'Title': {
                    'DataType': 'String',
                    'StringValue': 'Request new URL'
                },
                'IPValue': {
                    'DataType': 'String',
                    'StringValue': request.remote_addr
                },
                'RequestDate': {
                    'DataType': 'String',
                    'StringValue': f'{ct}'
                }
            },
            MessageBody=(url)
        )
        print(f"message {response['MessageId']} sent")
        #get_url(url)
        #TODO sanatize the string
        time.sleep(1)
        return redirect(f"/{url[7:]}")
    else: 
        return render_template("home.html", cache=cache)    

@app.route("/monitor", methods=["GET"])
def monitor():
    cache = get_cache()
    return render_template("monitor.html", cache=cache)


@app.route("/api/stats")
def api_stats():
    from datetime import datetime, timezone

    PLACEHOLDER_SIZE = 492924
    EXPECTED_YEARS   = list(range(2000, 2027))
    s3_client        = boto3.client("s3")
    sqs_client       = boto3.client("sqs")

    # ── S3 domain stats ──────────────────────────────────────────────────────
    domains_data    = []
    total_completed = 0
    total_size      = 0

    try:
        domain_names = sorted([
            item.name for item in S3Path("/websiteovertime/screenshots/").iterdir()
            if item.is_dir()
        ])
    except Exception:
        domain_names = []

    from collections import defaultdict
    from datetime import timedelta
    daily_screenshots = defaultdict(int)   # "YYYY-MM-DD" → count

    now = datetime.now(timezone.utc)   # defined once, before the loop

    for domain in domain_names:
        try:
            files = []
            paginator = s3_client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket="websiteovertime", Prefix=f"screenshots/{domain}/"):
                for obj in page.get("Contents", []):
                    filename  = obj["Key"].split("/")[-1]
                    year_str  = filename[-8:-4]
                    if not year_str.isdigit() or year_str == "0000":
                        continue
                    year = int(year_str)
                    if not (2000 <= year <= 2026):
                        continue
                    files.append({
                        "year":          year,
                        "size_bytes":    obj["Size"],
                        "last_modified": obj["LastModified"].isoformat(),
                        "is_done":       obj["Size"] != PLACEHOLDER_SIZE,
                    })

            done_files    = [f for f in files if f["is_done"]]
            pending_files = [f for f in files if not f["is_done"]]
            done_years    = sorted(f["year"] for f in done_files)
            pending_years = [y for y in EXPECTED_YEARS if y not in set(done_years)]

            # Years whose placeholder was touched recently = probably in SQS queue
            queued_years = sorted(
                f["year"] for f in pending_files
                if (now - datetime.fromisoformat(f["last_modified"])).total_seconds() < 1800  # 30 min
            )

            all_dates  = [f["last_modified"] for f in files]
            done_dates = [f["last_modified"] for f in done_files]

            first_seen    = min(all_dates)  if all_dates  else None
            last_activity = max(done_dates) if done_dates else None

            elapsed_seconds = 0
            if first_seen:
                elapsed_seconds = int((now - datetime.fromisoformat(first_seen)).total_seconds())

            rate_per_min = round(len(done_files) / (elapsed_seconds / 60), 2) if elapsed_seconds > 60 and done_files else 0
            eta_seconds  = int(len(pending_years) / rate_per_min * 60) if rate_per_min > 0 and pending_years else None

            domain_size = sum(f["size_bytes"] for f in done_files)
            avg_size    = domain_size // len(done_files) if done_files else 0

            total_completed += len(done_files)
            total_size      += domain_size

            for f in done_files:
                daily_screenshots[f["last_modified"][:10]] += 1

            if not pending_years:
                status = "done"
            elif last_activity and (now - datetime.fromisoformat(last_activity)).total_seconds() < 600:
                status = "active"
            else:
                status = "stalled"

            domains_data.append({
                "name":           domain,
                "completed":      len(done_files),
                "total":          len(EXPECTED_YEARS),
                "pct":            round(len(done_files) / len(EXPECTED_YEARS) * 100),
                "pending_years":  pending_years,
                "queued_years":   queued_years,
                "done_years":     done_years,
                "size_bytes":     domain_size,
                "avg_size_bytes": avg_size,
                "first_seen":     first_seen,
                "last_activity":  last_activity,
                "elapsed_seconds":elapsed_seconds,
                "rate_per_min":   rate_per_min,
                "eta_seconds":    eta_seconds,
                "status":         status,
            })
        except Exception:
            pass

    # ── CloudWatch logs — parallel instances ─────────────────────────────────
    # With reservedConcurrency=5, up to 5 Lambda execution environments can run
    # concurrently. Each environment writes to its own log stream. We fetch the
    # N most recently active streams and merge them so the monitor shows all
    # parallel instances at once.
    LAMBDA_LOG_GROUPS = {
        "getscreenshot": "/aws/lambda/wsot-sqs-get-screenshot-dev-wsotGetScreenshotFunction",
        "geturl":        "/aws/lambda/websiteovertime-geturl-dev-geturl",
    }
    ACTIVE_WINDOW_MS   = 5 * 60 * 1000   # streams with events in the last 5 min
    MAX_STREAMS        = 5                # match reservedConcurrency
    EVENTS_PER_STREAM  = 25
    now_ms             = int(time.time() * 1000)

    logs_client = boto3.client("logs")
    lambda_logs = {}

    for fn_key, log_group in LAMBDA_LOG_GROUPS.items():
        try:
            streams_resp = logs_client.describe_log_streams(
                logGroupName=log_group,
                orderBy="LastEventTime",
                descending=True,
                limit=10,
            )
            all_streams = streams_resp.get("logStreams", [])

            # Prefer streams active in the last 5 min; fall back to the most recent
            active = [
                s for s in all_streams
                if now_ms - s.get("lastEventTimestamp", 0) < ACTIVE_WINDOW_MS
            ][:MAX_STREAMS]
            if not active:
                active = all_streams[:1]

            merged = []
            for idx, stream in enumerate(active):
                # Derive a short, stable instance ID from the stream name hash
                # e.g. "2026/06/04/[$LATEST]728df387..." → "728df387"
                raw_id   = stream["logStreamName"].split("]")[-1].lstrip("/")
                inst_key = raw_id[:8] if raw_id else f"{idx+1}"
                inst_lbl = f"λ{idx+1}"   # λ1 … λ5 (display label)

                events_resp = logs_client.get_log_events(
                    logGroupName=log_group,
                    logStreamName=stream["logStreamName"],
                    limit=EVENTS_PER_STREAM,
                    startFromHead=False,
                )
                for e in events_resp["events"]:
                    msg = e["message"].rstrip("\n")
                    if (not msg.strip()
                            or msg.startswith("START ")
                            or msg.startswith("END ")
                            or msg.startswith("REPORT ")):
                        continue
                    merged.append({
                        "ts":       e["timestamp"],
                        "msg":      msg,
                        "instance": inst_lbl,
                        "inst_key": inst_key,
                    })

            # Sort chronologically; keep the tail
            merged.sort(key=lambda x: x["ts"])
            merged = merged[-50:]

            lambda_logs[fn_key] = {
                "events":           merged,
                "active_instances": len(active),
            }
        except Exception:
            lambda_logs[fn_key] = {"events": [], "active_instances": 0}

    # ── SQS queue stats ───────────────────────────────────────────────────────
    queues_data = []
    for q_name in [f"{prefix}websiteovertime-geturl.fifo", f"{prefix}websiteovertime-getscreenshot.fifo"]:
        try:
            q_url  = sqs_client.get_queue_url(QueueName=q_name)["QueueUrl"]
            attrs  = sqs_client.get_queue_attributes(
                QueueUrl=q_url,
                AttributeNames=["ApproximateNumberOfMessages", "ApproximateNumberOfMessagesNotVisible"]
            )["Attributes"]

            peek = sqs_client.receive_message(
                QueueUrl=q_url, MaxNumberOfMessages=5,
                VisibilityTimeout=5, WaitTimeSeconds=0,
                MessageAttributeNames=["All"], AttributeNames=["SentTimestamp"]
            )

            messages = []
            for msg in peek.get("Messages", []):
                ts  = int(msg.get("Attributes", {}).get("SentTimestamp", 0)) / 1000
                ma  = msg.get("MessageAttributes", {})
                messages.append({
                    "body":     msg.get("Body", ""),
                    "domain":   ma.get("Domain", {}).get("StringValue", ""),
                    "year":     ma.get("Year",   {}).get("StringValue", ""),
                    "retries":  ma.get("Retries",{}).get("StringValue", "0"),
                    "sent_at":  datetime.fromtimestamp(ts, tz=timezone.utc).isoformat() if ts else None,
                })

            queues_data.append({
                "name":      q_name,
                "visible":   int(attrs.get("ApproximateNumberOfMessages", 0)),
                "in_flight": int(attrs.get("ApproximateNumberOfMessagesNotVisible", 0)),
                "messages":  messages,
            })
        except Exception as e:
            queues_data.append({"name": q_name, "error": str(e)})

    total_expected = len(domain_names) * len(EXPECTED_YEARS)

    # ── Activity timeline (last 30 days, derived from S3 LastModified) ────────
    today = datetime.now(timezone.utc).date()
    daily_activity = [
        {"date": str(today - timedelta(days=i)), "count": daily_screenshots.get(str(today - timedelta(days=i)), 0)}
        for i in range(29, -1, -1)
    ]

    return jsonify({
        "domains": domains_data,
        "totals": {
            "domains":     len(domain_names),
            "expected":    total_expected,
            "completed":   total_completed,
            "pending":     total_expected - total_completed,
            "size_bytes":  total_size,
            "pct":         round(total_completed / total_expected * 100) if total_expected else 0,
        },
        "queues":         queues_data,
        "lambda_logs":    lambda_logs,
        "daily_activity": daily_activity,
        # Memory config so frontend can calculate cost estimates
        "lambda_config": {
            "getscreenshot_mb": 1024,   # Chrome+Selenium needs ~1GB
            "geturl_mb":        128,
            "frontend_mb":      256,
            "getscreenshot_avg_duration_s": 60,
            "geturl_avg_duration_s":        3,
        },
        "refreshed_at": datetime.now(timezone.utc).isoformat(),
    })


@app.route("/api/requeue", methods=["POST"])
def api_requeue():
    data   = request.get_json()
    domain = (data.get("domain") or "").strip()
    years  = data.get("years") or []

    if not domain or not years:
        return jsonify({"error": "domain and years required"}), 400

    sqs_queue = sqs.get_queue_by_name(QueueName=f"{prefix}websiteovertime-getscreenshot.fifo")
    queued = []
    for year in years:
        key = f"screenshots/{domain}/{domain}_{year}.png"
        s3.Object("websiteovertime", key).copy_from(
            CopySource="websiteovertime/screenshots/websiteovertime-working.png"
        )
        sqs_queue.send_message(
            # One FIFO group per (domain, year): a broken year only blocks itself,
            # never the rest. Shared groups cause head-of-line blocking where one
            # un-renderable page stalls the whole queue.
            MessageGroupId=f"{domain}-{year}",
            MessageDeduplicationId=str(uuid.uuid4()),
            MessageAttributes={
                "Title":  {"DataType": "String", "StringValue": "Request new screenshot"},
                "Domain": {"DataType": "String", "StringValue": domain},
                "Path":   {"DataType": "String", "StringValue": key},
                "Year":   {"DataType": "String", "StringValue": str(year)},
            },
            MessageBody=f"http://{domain}"
        )
        queued.append(year)

    return jsonify({"queued": queued, "count": len(queued)})

#domain route...just the same search box, a list of hashtags of previous crawllings and....the screenshots of this century
@app.route("/<domain>", methods=["GET", "POST"])
def get_domain(domain):
    if request.method == "POST":
        sqs = boto3.resource("sqs")        
        sqs_queue = sqs.get_queue_by_name(QueueName=f"{prefix}websiteovertime-getscreenshot.fifo")     
        original_path = str(request.form.get('path').strip())
        domain        = str(request.form.get('domain').strip())
        year          = str(request.form.get('year').strip())
        response = sqs_queue.send_message(
            # Per-(domain, year) FIFO group → a broken year never blocks others.
            MessageGroupId=f"{domain}-{year}",
            MessageDeduplicationId=f'{uuid.uuid4()}',
            MessageAttributes={
                'Title': {
                    'DataType': 'String',
                    'StringValue': 'Request new screenshot'
                },
                'Domain': {
                    'DataType': 'String',
                    'StringValue': str(request.form.get('domain').strip())
                },
                'Path': {
                    'DataType': 'String',
                    'StringValue': os.path.join(os.path.dirname(os.path.abspath(__file__)), 'screenshots', domain)
                },
                'Year': {
                    'DataType': 'String',
                    'StringValue': f"{request.form.get('year').strip()}"
                },
                'Random': {
                    'DataType': 'String',
                    'StringValue': "True"
                }                
            },
            MessageBody=(f"New Screenshot screeenshot/{str(request.form.get('domain').strip())}/{str(request.form.get('domain').strip())}_{str(request.form.get('year').strip())}")
        )
        print(f"message {response['MessageId']} sent (New Screenshot screeenshot/{str(request.form.get('domain').strip())}/{str(request.form.get('domain').strip())}_{str(request.form.get('year').strip())})")
        if os.environ.get('IS_LOCAL') == 'true':
            shutil.copyfile(os.path.join(base_dir, "websiteovertime-working.png"), f"{original_path}/{domain}_{year}.png")
        else:
            s3.Object('websiteovertime', f"screenshots/{domain}/{domain}_{year}.png").copy_from(CopySource='websiteovertime/screenshots/websiteovertime-working.png')
        time.sleep(1)
    if('favicon' in domain):
        return "nothing for you here"

    try:
        if os.environ.get('IS_LOCAL') == 'true':
            screenshots_dir = os.path.join(base_dir, 'screenshots')
            print(f"looking for domain at {screenshots_dir}/{domain}/")
            screenshots_data = [
                (f.name[-8:-4], f.name, int(f.stat().st_mtime))
                for f in os.scandir(os.path.join(screenshots_dir, domain))
            ]
        else:
            print(f"looking for domain in S3 websiteovertime/screenshots/{domain}/")
            s3_client = boto3.client('s3')
            paginator = s3_client.get_paginator('list_objects_v2')
            screenshots_data = []
            for page in paginator.paginate(Bucket='websiteovertime', Prefix=f'screenshots/{domain}/'):
                for obj in page.get('Contents', []):
                    filename = obj['Key'].split('/')[-1]
                    year_str = filename[-8:-4]
                    if year_str.isdigit() and year_str != '0000':
                        # Use LastModified as cache-buster: same file = same ?r= = browser cache hit
                        bust = int(obj['LastModified'].timestamp())
                        screenshots_data.append((year_str, filename, bust))

        screenshots = [
            (index, int(tup[0]), tup[1], tup[2])
            for index, tup in enumerate(sorted(screenshots_data))
        ]
    except Exception:
        screenshots = []
        
    cache = get_cache()
    return render_template("screenshots.html", screenshots=screenshots, cache=cache, domain=domain)    

@app.route("/screenshots/<domain>/<filename>")
def serve_screenshot(domain, filename):
    if os.environ.get('IS_LOCAL') == 'true':
        base_dir = os.path.dirname(os.path.abspath(__file__))
        screenshots_dir = os.path.join(base_dir, 'screenshots', domain)
        return send_from_directory(screenshots_dir, filename)
    else:
        # Pass the cache-buster param through so the browser never serves
        # a stale placeholder from its cache when the real screenshot arrives.
        r = request.args.get('r', '')
        qs = f"?r={r}" if r else ""
        resp = redirect(f"https://websiteovertime.s3.amazonaws.com/screenshots/{domain}/{filename}{qs}")
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return resp

# call the program in a safe way
if __name__ == '__main__':
      app.run(host='0.0.0.0', port=5001)