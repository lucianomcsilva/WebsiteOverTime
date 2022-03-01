
import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp


import sys
import re
import os
from urllib.parse import urlparse
from selenium import webdriver
from time import sleep

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

#url = 'https://www.apple.com/'

def create_dir(domain):
    base = 'screenshots'
    if not os.path.exists(base):
        os.mkdir(base)
    path = f'{base}/{domain}'
    if not os.path.exists(path):
        os.mkdir(path)
    else:
        i = 2
        while os.path.exists(path):
            path = domain + f" ({i})"
            if not os.path.exists(path):
                os.mkdir(path)
                break
            i += 1
    return path

def getFinalUrl(initialURL):
    import requests
    #url = "https://web.archive.org/web/20080101/http://www.microsoft.com/"
    res = requests.get(initialURL)
    return res.request.url


# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        url = "http://"+request.form.get('url').strip()
        get_url(url)
        #TODO sanatize the string
        return redirect(f"/{url}")
    else:
        #cache = ['www.uol.com.br', 'www.terra.com.br', 'www.ig.com.br', 'www.globo.com']
        cache = [ f.name for f in os.scandir('./screenshots/') if f.is_dir() ]
        return render_template("home.html", cache=cache)
    #return "nada ainda...aguarde"
    
@app.route("/<domain>", methods=["GET", "POST"])
def get_domain(domain):
    print(domain)
    if('favicon' in domain):
        return "nothing for you here"
    url = f"http://{domain}"
    print(f"looking dor domain at ./screenshots/{domain}/")
    screenshots = [(index, f.name[-8:-4], f.name) for (index, f) in enumerate(os.scandir(f'./screenshots/{domain}/'))]
    cache = [ f.name for f in os.scandir('./screenshots/') if f.is_dir() ]
    #screenshots = [ (f.name[-8:-4], f.name) for f in os.scandir(f'./screenshots/{domain}/') ]
    
    return render_template("screenshots.html", screenshots=screenshots, cache=cache)
    return url


def get_url(url):
    print(f"Requested screenshot for {bcolors.OKCYAN}{url}{bcolors.ENDC}")
    
    domain = urlparse(url).netloc
    print(f"Domain for this request is {bcolors.OKCYAN}{domain}{bcolors.ENDC}")
    
    DRIVER = 'chromedriver'
    options = webdriver.ChromeOptions()
    options.headless = True
    options.add_argument("--hide-scrollbars")

    driver = webdriver.Chrome(options=options)
    driver.set_window_size(1920, 1080)
    driver.set_window_size(800, 600)
    path = create_dir(domain)
    for year in range(2000, 2021):
        print(f"{bcolors.BOLD}{bcolors.OKGREEN}------------------  {bcolors.BLINK}{year}  ------------------{bcolors.ENDC}")
        aURL = f'https://web.archive.org/web/{year}0101/{url}'        
        print(f"Trying {bcolors.OKCYAN}{aURL}{bcolors.ENDC}")

        finalUrl = getFinalUrl(aURL)    
        print(f"best webarchive url found at  {bcolors.OKCYAN}{finalUrl}{bcolors.ENDC}")

        driver.get(aURL)
        driver.get_screenshot_as_file(f"{path}/{domain}_{year}.png")
        print(f"File saved at {bcolors.OKCYAN}{path}/{domain}_{year}.png{bcolors.ENDC}")

    driver.quit()

# orquestrate de program
def main():
    # Ensure correct usage
    if len(sys.argv) != 2:
        sys.exit("Usage: python3 screenshots.py http://www.example.com")
    url = sys.argv[1]
    get_url(url)    

# call the program in a safe way
if __name__ == '__main__':
      app.run(host='0.0.0.0', port=5001)