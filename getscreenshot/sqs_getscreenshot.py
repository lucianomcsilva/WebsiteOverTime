import os
from selenium import webdriver
import boto3
import random

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
sqs_queue = sqs.get_queue_by_name(QueueName="websiteovertime-getscreenshot.fifo")     

# this is a simple method to find the closest URL in internet Archive
# for a given initialURL. That's because it is not likely to found and exactly jan 1st
def getFinalUrl(initialURL):
    import requests    
    res = requests.get(initialURL)
    return res.request.url

# Invoke selenium and chrome and save the screenshot for each file. Atempt to
# make if more performatic and run in paralel with asyncio
# Note: IT did not work in a cheap machine. LEt it run sincronous
# @background
def get_url_at_year(path, domain, year, random_date=False):
    url = f"http://{domain}"

    DRIVER = 'chromedriver'
    options = webdriver.ChromeOptions()
    options.headless = True
    options.add_argument("--hide-scrollbars")
    
    driver = webdriver.Chrome(options=options)
    driver.set_window_size(1920, 1080)
    driver.set_window_size(800, 600)    
    
    if random_date:
        month = random.randint(1,4)
        day   = random.randint(1,28)
        target = f"0{month}{day}"
    else:
        target = '0101'
    
    aURL = f'https://web.archive.org/web/{year}{target}/{url}'
    print(f"{bcolors.BOLD}{bcolors.OKGREEN}------------------  {bcolors.BLINK}{year}  ------------------{bcolors.ENDC}")
    print(f"Trying {bcolors.OKCYAN}{aURL}{bcolors.ENDC}")

    finalUrl = getFinalUrl(aURL)    
    print(f"{bcolors.BOLD}{bcolors.OKGREEN}------------------  {bcolors.BLINK}{year}  ------------------{bcolors.ENDC}")
    print(f"best webarchive url found at  {bcolors.OKCYAN}{finalUrl}{bcolors.ENDC}")

    driver.get(aURL)
    driver.get_screenshot_as_file(f"{path}/{domain}_{year}.png")
    print(f"{bcolors.BOLD}{bcolors.OKGREEN}------------------  {bcolors.BLINK}{year}  ------------------{bcolors.ENDC}")
    print(f"File saved at {bcolors.OKCYAN}{path}/{domain}_{year}.png{bcolors.ENDC}")
    filenames = [(f.name[-8:-4], f.name) for f in os.scandir(f'{path}')]
    if(len(filenames) > 23):
        os.remove(f"{path}/{domain}_0000.png")
    print(len(filenames))
    #driver.quit()
    return 

if __name__ == "__main__":
    while True:
        messages = sqs_queue.receive_messages(WaitTimeSeconds=10, MessageAttributeNames=['All'])
        for message in messages:
            message_ts = message.message_attributes.get("Path").get('StringValue')
            path    = message.message_attributes.get("Path").get('StringValue')
            domain  = message.message_attributes.get("Domain").get('StringValue')
            year    = message.message_attributes.get("Year").get('StringValue')
            # random_date = True if message.message_attributes.get("Random").get('StringValue') else False
            random_date = True if message.message_attributes.get("Random") else False            

            print("-----------------------------")       
            print(f"{message.message_id} {path} {domain} {year} {random_date}")
            message.delete()       
            get_url_at_year(path, domain, year, random_date)
