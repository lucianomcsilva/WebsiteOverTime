# `sqs_getscreenshot.py`

## Role
This script is the heavy lifter. Its sole purpose is to capture visual snapshots using browser automation given a specific domain and year. It is a secondary worker polling the `websiteovertime-getscreenshot.fifo` queue.

## Workflow

1. **Parameter Passing**:
    Reads the Domain, Year, Target Path, and optionally a random date instruction from SQS headers.

2. **Fetching Closest Archive**:
    A simple crawler script (`getFinalUrl(initialURL)`) queries the Wayback Machine to find the closest available snapshot for January 1st (`0101`) or a randomized date of the requested year using `requests.get`. It resolves any redirects the Wayback Machine issues when it finds the best match.

3. **Headless Broswer Automation**:
    Uses Selenium (`webdriver.Chrome(...)`) with `headless=True` to hide the UI. It hides scrollbars as well to maintain a clean image.
    The resolution is set to `800x600` specifically because "websites on the beginning of this century was designed to this resolution and those got in a higher resolution would not transmit the sensation of that time."

4. **File Saving**:
    It saves the screenshot natively to the specified target path:
    `driver.get_screenshot_as_file(...)`
    It also implements a small cleanup logic removing the temporary 0000 placeholder image once enough images (more than 23) successfully land in the directory.
