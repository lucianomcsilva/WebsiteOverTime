import asyncio
import sys
import re
import os
from urllib.parse import urlparse
from selenium import webdriver
import time 
import boto3
import shutil

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
    return original_path

# this is a simple method to find the closest URL in internet Archive
# for a given initialURL. That's because it is not likely to found and exactly jan 1st
def getFinalUrl(initialURL):
    import requests
    #url = "https://web.archive.org/web/20080101/http://www.microsoft.com/"
    res = requests.get(initialURL)
    return res.request.url

# Invoke selenium and chrome and save the screenshot for each file. Atempt to
# make if more performatic and run in paralel with asyncio
# Note: IT did not work in a cheap machine. LEt it run assincronous
# @background
def get_url_at_year(path, domain, year):
    url = f"http://{domain}"

    DRIVER = 'chromedriver'
    options = webdriver.ChromeOptions()
    options.headless = True
    options.add_argument("--hide-scrollbars")
    
    driver = webdriver.Chrome(options=options)
    driver.set_window_size(1920, 1080)
    driver.set_window_size(800, 600)    

    
    aURL = f'https://web.archive.org/web/{year}0101/{url}'
    print(f"{bcolors.BOLD}{bcolors.OKGREEN}------------------  {bcolors.BLINK}{year}  ------------------{bcolors.ENDC}")
    print(f"Trying {bcolors.OKCYAN}{aURL}{bcolors.ENDC}")

    finalUrl = getFinalUrl(aURL)    
    print(f"{bcolors.BOLD}{bcolors.OKGREEN}------------------  {bcolors.BLINK}{year}  ------------------{bcolors.ENDC}")
    print(f"best webarchive url found at  {bcolors.OKCYAN}{finalUrl}{bcolors.ENDC}")

    driver.get(aURL)
    driver.get_screenshot_as_file(f"{path}/{domain}_{year}.png")
    print(f"{bcolors.BOLD}{bcolors.OKGREEN}------------------  {bcolors.BLINK}{year}  ------------------{bcolors.ENDC}")
    print(f"File saved at {bcolors.OKCYAN}{path}/{domain}_{year}.png{bcolors.ENDC}")

    #driver.quit()
    return 

# Invoke selenium and chrome and save the screenshot for each file
def get_url(url):
    print(f"Requested screenshot for {bcolors.OKCYAN}{url}{bcolors.ENDC}")    
    
    domain = urlparse(url).netloc
    print(f"Domain for this request is {bcolors.OKCYAN}{domain}{bcolors.ENDC}")
    path = create_dir(domain)

    for year in range(2000, 2022):
        get_url_at_year(path, domain, year)
    
    # DRIVER = 'chromedriver'
    # options = webdriver.ChromeOptions()
    # options.headless = True
    # options.add_argument("--hide-scrollbars")
    
    # driver = webdriver.Chrome(options=options)
    # driver.set_window_size(1920, 1080)
    # driver.set_window_size(800, 600)
    
    
    # for year in range(2000, 2022):        
    #     print(f"{bcolors.BOLD}{bcolors.OKGREEN}------------------  {bcolors.BLINK}{year}  ------------------{bcolors.ENDC}")
    #     aURL = f'https://web.archive.org/web/{year}0101/{url}'        
    #     print(f"Trying {bcolors.OKCYAN}{aURL}{bcolors.ENDC}")

    #     finalUrl = getFinalUrl(aURL)    
    #     print(f"best webarchive url found at  {bcolors.OKCYAN}{finalUrl}{bcolors.ENDC}")

    #     driver.get(aURL)
    #     driver.get_screenshot_as_file(f"{path}/{domain}_{year}.png")
    #     print(f"File saved at {bcolors.OKCYAN}{path}/{domain}_{year}.png{bcolors.ENDC}")

    # driver.quit()
    pass

def process_message(message_body):
    print(f"processing message: {message_body}")
    # do what you want with the message here
    pass

if __name__ == "__main__":
    while True:
        messages = sqs_queue.receive_messages(WaitTimeSeconds=10)
        # if messages:
        #     print("-----------------------------")
        for message in messages:
            message_ts = message.attributes     
            process_message(f"{message_ts} {message.message_id} {message.body}")
            message.delete()
            get_url(message.body)            
