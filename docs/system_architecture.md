# System Architecture: Website Over Time

## Overview

**Website Over Time** is a web archiving and visualization system designed to chronologically capture and display the evolution of websites. It leverages the Internet Archive (Wayback Machine) to retrieve historical versions of websites spanning from 2000 to the present day.

The system is built on an event-driven architecture to ensure scalability and avoid blocking the frontend application during long-running web scraping tasks.

## Components

The architecture consists of three main components:

1. **Frontend Application (Flask)**: Serves the user interface, allows users to request new domains to crawl, and displays the galleries of captured screenshots.
2. **URL Processing Worker**: Listens for new domain requests via an AWS SQS queue. When a domain is requested, it generates a series of tasks (one for each year) and places them into a secondary queue.
3. **Screenshot Processing Worker**: Listens to the secondary SQS queue. For each task, it fires up a headless Chrome browser (via Selenium), navigates to the Internet Archive's snapshot of the domain for the requested year, captures a screenshot, and saves it.

## Execution Flow

```mermaid
sequenceDiagram
    participant User
    participant Flask App
    participant SQS (geturl.fifo)
    participant Worker (geturl)
    participant SQS (getscreenshot.fifo)
    participant Worker (getscreenshot)
    participant Internet Archive

    User->>Flask App: POST / (Submit Domain)
    Flask App->>SQS (geturl.fifo): Send message (URL)
    Flask App->>User: Redirect to /<domain>
    SQS (geturl.fifo)->>Worker (geturl): Consume message
    loop Every year (2000-2023)
        Worker (geturl)->>SQS (getscreenshot.fifo): Send message (URL, Year)
    end
    SQS (getscreenshot.fifo)->>Worker (getscreenshot): Consume message
    Worker (getscreenshot)->>Internet Archive: Navigate to web.archive.org/web/<Year>0101/<URL>
    Internet Archive-->>Worker (getscreenshot): Return website
    Worker (getscreenshot)->>Worker (getscreenshot): Take Screenshot via Selenium
    Worker (getscreenshot)->>Storage: Save to disk/S3
```

## Cloud vs Local Implementations
The codebase includes two implementations:
- **Local/Lightsail**: Uses local file system (`./screenshots`) to store images and runs as standard python scripts (`app.py`, `sqs_geturl.py`, `sqs_getscreenshot.py`).
- **AWS Serverless/Lambda**: Uses AWS S3 for storage and AWS Lambda for execution, adjusting to a purely cloud-native architecture (`app_lambda.py`, `sqs_geturl_lambda.py`).

## Dependencies
- **Flask**: Web framework for the frontend.
- **Boto3**: AWS SDK for Python to interact with SQS and S3.
- **Selenium**: Browser automation to capture screenshots natively in Chrome.
- **Requests**: Fetch URLs dynamically to locate closest Internet Archive records.
