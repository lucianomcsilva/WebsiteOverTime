# `app_lambda.py`

## Role
This is the AWS Serverless/Lambda equivalent of the `app.py` Flask frontend application. It is functionally identical to `app.py` but is modified to rely on AWS S3 for storage rather than the local filesystem.

## Key Differences from `app.py`

1. **Storage Mechanism**:
    - Replaces local file system operations (`os.scandir`) with S3 queries using `s3path.S3Path`.
    - Iterates over the bucket `/websiteovertime/screenshots/` to fetch cached domains.
    
2. **File References**:
    - Instead of serving local paths, image URLs are constructed pointing directly to the public S3 bucket: `https://websiteovertime.s3.amazonaws.com/screenshots/...`.

3. **Image Placeholder Copying (POST /domain)**:
    - Instead of using `shutil.copyfile` to copy the `websiteovertime-working.png` placeholder to a local directory upon requesting a reload for a domain/year, it executes `s3.Object(...).copy_from(...)` to copy the placeholder directly inside the S3 bucket.

4. **Message Triggers**:
    - SQS messaging syntax stays mostly the same, continuing to pass requests to the `.fifo` queues for AWS Lambda workers.
