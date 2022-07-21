
import os
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp

import re
import os
from urllib.parse import urlparse
import time
import datetime
import uuid
import shutil

import boto3

sqs = boto3.resource("sqs")

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
Session(app)

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
    cache = [ f.name for f in os.scandir('./screenshots/') if (f.is_dir()) and (f.name[-1:] != ')')] 
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
        sqs_queue = sqs.get_queue_by_name(QueueName="websiteovertime-geturl.fifo")     

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

#domain route...just the same search box, a list of hashtags of previous crawllings and....the screenshots of this century
@app.route("/<domain>", methods=["GET", "POST"])
def get_domain(domain):
    if request.method == "POST":
        sqs = boto3.resource("sqs")        
        sqs_queue = sqs.get_queue_by_name(QueueName="websiteovertime-getscreenshot.fifo")     
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
                    'StringValue': str(request.form.get('path').strip())
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
        shutil.copyfile("websiteovertime-working.png", f"{original_path}/{domain}_{year}.png")
        time.sleep(1)
    if('favicon' in domain):
        return "nothing for you here"    
    print(f"looking dor domain at ./screenshots/{domain}/")        
    screenshots = [(index, int(tup[0]), tup[1]) for (index, tup) in enumerate(sorted([(f.name[-8:-4], f.name) for f in os.scandir(f'./screenshots/{domain}/')]))]
    cache = [ f.name for f in os.scandir('./screenshots/') if (f.is_dir()) and (f.name[-1:] != ')')]    
    return render_template("screenshots.html", screenshots=screenshots, cache=cache, domain=domain)    

# call the program in a safe way
if __name__ == '__main__':
      app.run(host='0.0.0.0', port=5000)