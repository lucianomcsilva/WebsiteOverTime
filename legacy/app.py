
import os
from flask import Flask, flash, jsonify, redirect, render_template, request, session, send_from_directory
#from flask_session import Session
from tempfile import mkdtemp

import re
import os
from urllib.parse import urlparse
import time
import datetime
import uuid
import shutil

import boto3

prefix = 'local-' if os.environ.get('IS_LOCAL') == 'true' else ''
sqs = boto3.resource("sqs")
s3  = boto3.resource("s3")
Session = session
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

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
#Session(app)

#diable cache for a better experience
@app.after_request
def add_header(r):
    r.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    r.headers["Pragma"] = "no-cache"
    r.headers["Expires"] = "0"
    r.headers['Cache-Control'] = 'public, max-age=0'
    return r

#main route...just a search box and a list of hashtags of previous crawllings
@app.route("/", methods=["GET", "POST"])
def index():
    screenshots_dir = os.path.join(base_dir, 'screenshots')
    os.makedirs(screenshots_dir, exist_ok=True)
    cache = [ f.name for f in os.scandir(screenshots_dir) if (f.is_dir()) and (f.name[-1:] != ')')] 
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
    sqs_client = boto3.client("sqs")
    
    queues_info = []
    queue_names = [
        f"{prefix}websiteovertime-geturl.fifo",
        f"{prefix}websiteovertime-getscreenshot.fifo"
    ]
    
    for q_name in queue_names:
        try:
            url = sqs_client.get_queue_url(QueueName=q_name)['QueueUrl']
            attrs = sqs_client.get_queue_attributes(
                QueueUrl=url,
                AttributeNames=['ApproximateNumberOfMessages', 'ApproximateNumberOfMessagesNotVisible']
            )['Attributes']
            
            # Peek at some messages without deleting them
            peek_response = sqs_client.receive_message(
                QueueUrl=url,
                MaxNumberOfMessages=5,
                VisibilityTimeout=5, # Hide from other consumers for just 5 seconds
                WaitTimeSeconds=0,
                MessageAttributeNames=['All']
            )
            
            peeked_messages = []
            if 'Messages' in peek_response:
                for msg in peek_response['Messages']:
                    title = 'No Title'
                    year = ''
                    if 'MessageAttributes' in msg:
                        if 'Title' in msg['MessageAttributes']:
                            title = msg['MessageAttributes']['Title']['StringValue']
                        if 'Year' in msg['MessageAttributes']:
                            year = msg['MessageAttributes']['Year']['StringValue']
                        
                    peeked_messages.append({
                        'id': msg.get('MessageId', 'Unknown'),
                        'body': msg.get('Body', ''),
                        'title': title,
                        'year': year
                    })

            queues_info.append({
                'name': q_name,
                'visible': attrs.get('ApproximateNumberOfMessages', '0'),
                'in_flight': attrs.get('ApproximateNumberOfMessagesNotVisible', '0'),
                'messages': peeked_messages
            })
        except Exception as e:
            queues_info.append({
                'name': q_name,
                'error': str(e)
            })

    # Fetch cache for the sidebar
    screenshots_dir = os.path.join(base_dir, 'screenshots')
    os.makedirs(screenshots_dir, exist_ok=True)
    cache = [ f.name for f in os.scandir(screenshots_dir) if (f.is_dir()) and (f.name[-1:] != ')')] 
            
    return render_template("monitor.html", queues=queues_info, cache=cache)

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
        shutil.copyfile(os.path.join(base_dir, "websiteovertime-working.png"), f"{original_path}/{domain}_{year}.png")
        time.sleep(1)
    if('favicon' in domain):
        return "nothing for you here"    
    import random
    screenshots_dir = os.path.join(base_dir, 'screenshots')
    print(f"looking for domain at {screenshots_dir}/{domain}/")        
    try:
        screenshots = [(index, int(tup[0]), tup[1], random.randint(1,100000)) for (index, tup) in enumerate(sorted([(f.name[-8:-4], f.name) for f in os.scandir(os.path.join(screenshots_dir, domain))]))]
    except FileNotFoundError:
        screenshots = []
    cache = [ f.name for f in os.scandir(screenshots_dir) if (f.is_dir()) and (f.name[-1:] != ')')]    
    return render_template("screenshots.html", screenshots=screenshots, cache=cache, domain=domain)    

@app.route("/screenshots/<domain>/<filename>")
def serve_screenshot(domain, filename):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    screenshots_dir = os.path.join(base_dir, 'screenshots', domain)
    return send_from_directory(screenshots_dir, filename)

# call the program in a safe way
if __name__ == '__main__':
      app.run(host='0.0.0.0', port=5001)