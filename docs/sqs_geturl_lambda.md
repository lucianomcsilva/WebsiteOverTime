# `sqs_geturl_lambda.py`

## Role
This is the AWS Serverless/Lambda equivalent of the `sqs_geturl.py` script. It serves as the URL coordinator for the cloud-native architecture. 

## Workflow

1. **Lambda Integration**:
   Instead of constantly polling with an infinite loop like the local script (`while True:`), it implements an AWS Lambda Handler function (`lambda_handler(event, context)`).

2. **Event Parsing**:
   AWS Lambda triggers the function natively via an SQS event. The handler parses the multiple `Records` in the event payload.

3. **Scatter Events with Added Delay**:
   Like its local equivalent, this script divides a domain into 24 distinct screenshot tasks (years 2000-2023). However, to prevent AWS or Internet Archive from throttling/blocking concurrent requests, it utilizes the `DelaySeconds` attribute in the generated SQS messages:
   `DelaySeconds=60*(year-1999)`
   This means the queue releases screenshots one by one spaced evenly by ~60 seconds per year, ensuring rate limits are respected without needing an actively sleeping blocking script.

4. **S3 Placeholder Override**:
   Replaces the local `shutil.copy` call for generating a placeholder with the `s3.Object(...).copy_from(...)` API equivalent.
