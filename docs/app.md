# `app.py`

## Role
This is the primary frontend Flask application intended for the local or VPS (like Amazon Lightsail) environment. It handles routing and user interaction, while offloading long-running scraping tasks to the backend queue.

## Features

1. **Routes**:
    - `GET /` : Renders the home page (`home.html`) and lists previously cached domains from the `./screenshots/` directory.
    - `POST /` : Accepts a new URL submitted from the search bar, parses the domain, checks if it is in the cache, and if not, triggers an SQS event to `websiteovertime-geturl.fifo`.
    - `GET /<domain>` : Renders the screenshots page (`screenshots.html`) displaying all captured images for that specific domain over the years.
    - `POST /<domain>` : Allows users to request re-crawling of a specific year and domain if a screenshot failed or needs refreshing. This sends a direct message to the `websiteovertime-getscreenshot.fifo` queue.

2. **Session and Cache**:
    - Disables browser caching explicitly through the `@app.after_request` decorator to ensure users see the latest screenshots when navigating.
    - Configures Flask sessions using the tempfile filesystem (`flask_session.Session`).

3. **Event Driven**:
    - Emits SQS parameters such as `MessageGroupId`, `MessageDeduplicationId` (using UUID), and Custom Attributes containing IP info and request dates for message tracking.
