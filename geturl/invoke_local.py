import os
import json
import uuid
import sys

# Emulate the Lambda environment
os.environ['IS_LOCAL'] = 'true'

try:
    from sqs_geturl_lambda import lambda_handler
except ImportError:
    print("Error: Could not import 'sqs_geturl_lambda'. Make sure you are in the geturl directory.")
    sys.exit(1)

def invoke(url):
    print(f"Emulating AWS SQS Event for URL: {url}...")
    
    # Construct a mock SQS event payload
    event = {
        "Records": [
            {
                "messageId": str(uuid.uuid4()),
                "body": url,
                "messageAttributes": {
                    "Title": {
                        "stringValue": "Local Emulation Request"
                    }
                }
            }
        ]
    }
    
    # Invoke the handler
    response = lambda_handler(event, None)
    
    print("\nLambda Execution Complete!")
    print(f"Response: {json.dumps(response, indent=2)}")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python invoke_local.py <url>")
        print("Example: python invoke_local.py http://github.com")
        sys.exit(1)
        
    target_url = sys.argv[1]
    invoke(target_url)
