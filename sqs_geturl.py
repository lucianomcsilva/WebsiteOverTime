import asyncio
import os
from urllib.parse import urlparse
import boto3
import shutil
import uuid

# Colors to be used in print/log functions
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


sqs = boto3.resource("sqs")
sqs_queue = sqs.get_queue_by_name(QueueName="websiteovertime-geturl.fifo")

def background(f):
    def wrapped(*args, **kwargs):
        return asyncio.get_event_loop().run_in_executor(None, f, *args, **kwargs)

    return wrapped

# This methdod create a new directory in case 
# the requested domain was already crawled, avoiding
# override the previous screenshot taken
def create_dir(domain):
    base = 'screenshots'
    if not os.path.exists(base):
        os.mkdir(base)
    original_path = f'{base}/{domain}'
    if not os.path.exists(original_path):
        os.mkdir(original_path)        
    else:
        # in case it is a override, create a new dir, move the files, and then 
        # let the original_path empty for a new crawler
        i = 2
        path = original_path
        while os.path.exists(path):
            path = original_path + f" ({i})"
            if not os.path.exists(path):
                os.mkdir(path)
                filenames = os.listdir(original_path)
                    
                for filename in filenames:
                    shutil.move(os.path.join(original_path, filename), path)
                break
            i += 1
            
    shutil.copyfile("websiteovertime-working.png", f"{original_path}/{domain}_0000.png")
    return original_path

# Invoke selenium and chrome and save the screenshot for each file
def get_url(url):
    print(f"Requested screenshot for {bcolors.OKCYAN}{url}{bcolors.ENDC}")    
    
    domain = urlparse(url).netloc
    print(f"Domain for this request is {bcolors.OKCYAN}{domain}{bcolors.ENDC}")
    path = create_dir(domain)

    for year in range(2000, 2023):
        #get_url_at_year(path, domain, year)      
        shutil.copyfile("websiteovertime-working.png", f"{path}/{domain}_{year}.png")  
        sqs_send_queue = sqs.get_queue_by_name(QueueName="websiteovertime-getscreenshot.fifo")     

        response = sqs_send_queue.send_message(            
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
                    'StringValue': domain
                },
                'Path': {
                    'DataType': 'String',
                    'StringValue': path
                },
                'Year': {
                    'DataType': 'String',
                    'StringValue': f"{year}"
                }
            },
            MessageBody=(url)
        )
        print(f"message {response['MessageId']} sent")                
 
if __name__ == "__main__":
    while True:
        messages = sqs_queue.receive_messages(WaitTimeSeconds=10)
        for message in messages:            
            print(f"processing message {bcolors.OKCYAN}{message.message_id} {bcolors.OKGREEN}{message.body}{bcolors.ENDC}")            
            get_url(message.body)
            message.delete()
