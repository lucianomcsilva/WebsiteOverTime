# `sqs_geturl.py`

## Role
This script acts as the primary "URL Coordinator" worker for the local/VPS environment. It constantly polls the `websiteovertime-geturl.fifo` queue.

## Workflow

1. **Receive Message**: 
   Reads an incoming SQS message containing a target URL.
   
2. **Directory Management**:
   The `create_dir(domain)` method checks if a directory for the domain exists in `./screenshots/`. 
   If it exists (meaning it was crawled previously), the script moves the old folder to a backup (i.e., `domain (2)`). 
   It then copies a placeholder image (`websiteovertime-working.png`) to act as a loading state for the year 2000 while the crawler runs.

3. **Scatter Events**:
   Iterates through every year from 2000 to 2022. For every year, it dispatches a *new* message to the secondary queue: `websiteovertime-getscreenshot.fifo`.
   The message attributes include: Domain, Path, and the specific Year to crawl.
   
By doing this, the script breaks down a single user request ("Crawl www.example.com") into 23 separate, smaller tasks ("Crawl www.example.com for year 2000", "Crawl www.example.com for year 2001", etc.) allowing them to be potentially distributed or throttled.
