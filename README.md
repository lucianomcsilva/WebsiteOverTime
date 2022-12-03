# Website Over Time

#### Video Demo:  https://www.youtube.com/watch?v=FYucijjcUzA&ab_channel=LucianoCamilo

#### Description:
  
**WebSiteOverTime** is a simple, however, a long time wish and interesting project I had ever had. As someone that have lived the dawn and the gold ages of websites and being a historical curious and pretending to have an eidetic memory, I usually am mesmerized by the transition and evolution of some websites over time.
The idea is really simples. Starting with some URL (e.g.: www.harvard.edu) and using the must needed digital library of the internet, a.k.a. internet archive (https://archive.org/), and some simple math that spreads requests over a one-year period, my project crawl the page on the site.
Using a $5 computer at Amazon LightSail – I am scrooge as Carl Bark’s Scrooge McDuck – I built three python apps: 
-	A front-end flaks site, reversed proxied using nginx, serving the screenshots previously crawled as also a search box to POST new requests via a message in AWS SQS.
-	Two simple back-end scripts orchestrated over a queue in AWS SQS. The first one, named sqs_geturl.py, read the queue and create 22 new messages in a new topic that my other script, sqs_getscreenshots.py, read and using selenium and chromedriver open the website and save the screenshot in a convenient directory I have chosen (./screenshots/domain)
  
The figure shows how the site is rendered. And I hope you have as much fun as I have playing with this project.
  
![image](44.193.54.16_www.harvard.edu.png)

## Description of each progrman 
### Flask Front-end 
The frontend application was written in flask as the websites we developed at nineth week. There are two routes, with similar templates (more on that, [later on](#templates)).

The application runs on a single thread and listen to port 5000. A nginx server is used for a reverse proxy.

### Index route

The index route may receive a GET or POST request. Whichever it gets a list of cached folders is built. The cache list considers all non-duplicated folders identified by a number between parentheses. That’s needed to avoid some backup the backend generates when crawling the same domain twice.

For the GET route, the template with the cache list is rendered.

The POST route receives a URL to be crawled in a form request. There is a simple sanitizing of the received text to extract the domain (e.g. www.website.com). In case of the domain is in cache, the app redirects the user to the domain route. Otherwise it emits a SQS queue in the ```websiteovertime-geturl.fifo``` topic with the URL in the body message. The post route ends redirecting the user to the domain route.

### Domain route

The domain route may receive a GET or POST request.

The GET route built to lists. The cache list of previous crawled domains and the list of all pictures inside de screenshot folder for that domain. Both list are rendered on the [screenshots.html](templates/screenshots.html) template.

The POST route receives a set of information regarding a specific screenshot (domain, year, and relative path of the file on the server) to crawl it again. This can be used in case of an error on previous crawls.  With these information an SQS event is emitted and after 1 second the user is redirected to the domain route again.

### Templates
There are 2 templates, very similar. [Home.html](templates/home.html) and [screenshots.html](templates/screenshots.html). Both have a colorful logo on top with a search bar and a list of previous crawled pages. 

The search bar does a POST request to the index route. Clicking on the link of the previous crawled page does a GET request to the domain route, for that specific domain.

Screenshots.html has also a responsive grid system up to 3 images per row. If you hover the mouse over the picture a button appears. Clicking on it a POST request is made for the domain route, with YEAR, PATH and DOMAIN (see [domain route](#domain-route)).

### Backend programs
The standard Flask app is single threaded. So, if one tries to crawl new websites at the same time a flask method is running will be locked out.  

To avoid that behavior this projected use an event driven architecture. As explained in the previous section, whenever requested to crawl a new URL or new screenshots the flask frontend application just fire a new SQS event. These events are listened by two backend scripts.

#### sqs_getscreenshot.py

This script continuously listened to the ```websiteovertime-geturl.fifo``` topic.  After a simple sanitizing (avoids blank requests) it calls a ```get_url``` method for the URL in the message body.

The ```get_url``` functions extract the domain from the message body and a folder is created. In case the folder already exists, everything Is backed up in a new sequential numbered folder. 

A loop is created to emit 22 new events at ```websiteovertime-getscreenshot.fifo``` topic, one from each year from 2000 to 2022. Beside the year, the message also has the domain and the relative path on the server which the file must be saved.

It is also created 22 placeholder pictures so if the user requests the domain route it shows an image explaining the screenshots is in the process of being crawled. 

#### sqs_geturl.py
This script continuously listened to the ```websiteovertime-getscreenshot.fifo``` topic.  For each message received it calls a ```get_url_at_year```.

Firstly, we defined which final URL we should crawl. That's because it is not likely to found and exactly Jan 1st page for every domain. That’s made by calling ```getFinalUrl```, that uses the request library for that.

With the URL we invoke an invisible google chrome through selenium for python, with no scrollbar or any others visual elements at 800x600 pixels resolution. This resolution was chosen because websites on the beginning of this century was design to this resolution and those got in a higher resolution would not transmit the sensation of that time.

Selenium saves the screenshot at the received path, respecting the struct show on this line.

```driver.get_screenshot_as_file(f"{path}/{domain}_{year}.png")```
