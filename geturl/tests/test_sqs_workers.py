import pytest

def test_geturl_lambda_spawn_subtasks(aws_setup):
    """
    Test that the geturl lambda reads a domain, seeds the S3 bucket with
    placeholder images, and spawns 24 subtasks (years) into the next queue.
    """
    # Import inside the test so moto intercepts boto3 globally inside the module
    from sqs_geturl_lambda import lambda_handler
    
    s3 = aws_setup['s3']
    sqs = aws_setup['sqs']

    # 1. Seed the working image in the mock S3 so `copy_from` doesn't throw NoSuchKey
    s3.put_object(
        Bucket='websiteovertime',
        Key='screenshots/websiteovertime-working.png',
        Body=b'fake-png-data'
    )
    
    # 2. Mock SQS Event that the lambda would receive
    event = {
        "Records": [
            {
                "messageId": "mock-uuid-1234",
                "body": "http://www.facebook.com"
            }
        ]
    }
    
    # 3. Invoke the lambda handler
    response = lambda_handler(event, None)
    
    # Assure it parsed successfully without falling into batchItemFailures
    assert response.get("batchItemFailures") == []
    
    # 4. Assert that 24 placeholder images were copied to S3
    objects = s3.list_objects_v2(Bucket='websiteovertime', Prefix='screenshots/www.facebook.com/')
    assert 'Contents' in objects
    # 2000 to 2023 inclusive is 24 files
    assert len(objects['Contents']) == 24
    
    # 5. Assert 24 subtask messages were queued
    messages_found = 0
    while True:
        msgs = sqs.receive_message(
            QueueUrl=aws_setup['getscreenshot_queue_url'],
            MaxNumberOfMessages=10
        ).get('Messages', [])
        if not msgs:
            break
        messages_found += len(msgs)
        for msg in msgs:
            sqs.delete_message(
                QueueUrl=aws_setup['getscreenshot_queue_url'], 
                ReceiptHandle=msg['ReceiptHandle']
            )
            
    assert messages_found == 24
