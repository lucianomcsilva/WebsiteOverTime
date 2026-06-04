
import os
import re
import uuid
import time
import datetime
import random
import shutil
from urllib.parse import urlparse

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

#diable cache for a better experience
@app.after_request
def add_header(r):
    r.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    r.headers["Pragma"] = "no-cache"
    r.headers["Expires"] = "0"
    r.headers['Cache-Control'] = 'public, max-age=0'
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
        #Sanitize HTTPs
        url = request.form.get('url').strip().lower()
        print(f" 1 - {url}")
        if url.startswith('http'):
            print("it starts")
            url = re.sub(r'https?://', '', url) 
            print(f" 2 - {url}")
        url = "http://"+url
        print(f" 3 - {url}")
        domain = urlparse(url).netloc

        print(f"Received {request.form.get('url')}, converted to {url} and domain extracted was {domain}")

        if domain in cache:
            return redirect(f"/{url[7:]}")
        
        

        ct = datetime.datetime.now()
        
        # Send message to SQS queue   
        sqs_queue = sqs.get_queue_by_name(QueueName=f"{prefix}websiteovertime-geturl.fifo")     

        response = sqs_queue.send_message(            
            MessageGroupId="WebSiteOverTime",
            #for test purpose. In the future change for URL
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
            done_years    = sorted(f["year"] for f in done_files)
            pending_years = [y for y in EXPECTED_YEARS if y not in set(done_years)]

            all_dates  = [f["last_modified"] for f in files]
            done_dates = [f["last_modified"] for f in done_files]

            first_seen    = min(all_dates)  if all_dates  else None
            last_activity = max(done_dates) if done_dates else None

            now = datetime.now(timezone.utc)
            elapsed_seconds = 0
            if first_seen:
                elapsed_seconds = int((now - datetime.fromisoformat(first_seen)).total_seconds())

            rate_per_min = round(len(done_files) / (elapsed_seconds / 60), 2) if elapsed_seconds > 60 and done_files else 0
            eta_seconds  = int(len(pending_years) / rate_per_min * 60) if rate_per_min > 0 and pending_years else None

            domain_size = sum(f["size_bytes"] for f in done_files)
            avg_size    = domain_size // len(done_files) if done_files else 0

            total_completed += len(done_files)
            total_size      += domain_size

            if not pending_years:
                status = "done"
            elif last_activity and (now - datetime.fromisoformat(last_activity)).total_seconds() < 600:
                status = "active"
            elif done_files:
                status = "stalled"
            else:
                status = "queued"

            domains_data.append({
                "name":           domain,
                "completed":      len(done_files),
                "total":          len(EXPECTED_YEARS),
                "pct":            round(len(done_files) / len(EXPECTED_YEARS) * 100),
                "pending_years":  pending_years,
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
        "queues":       queues_data,
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
            MessageGroupId="WebSiteOverTime",
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
            MessageGroupId="WebSiteOverTime",
            #for test purpose. In the future change for URL
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
            screenshots_data = [(f.name[-8:-4], f.name) for f in os.scandir(os.path.join(screenshots_dir, domain))]
        else:
            print(f"looking for domain in S3 websiteovertime/screenshots/{domain}/")
            s3_screenshots_obj = [item.name for item in S3Path(f'/websiteovertime/screenshots/{domain}').iterdir() if not item.is_dir()]        
            screenshots_data = [(f[-8:-4], f) for f in s3_screenshots_obj]
            
        screenshots = [(index, int(tup[0]), tup[1], random.randint(1,100000)) for (index, tup) in enumerate(sorted(screenshots_data))]
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
        return redirect(f"https://websiteovertime.s3.amazonaws.com/screenshots/{domain}/{filename}")

# call the program in a safe way
if __name__ == '__main__':
      app.run(host='0.0.0.0', port=5001)