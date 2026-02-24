import boto3

def purge_queues():
    sqs = boto3.client('sqs')
    
    queues = [
        "websiteovertime-getscreenshot.fifo",
        "websiteovertime-geturl.fifo"
    ]
    
    for q_name in queues:
        try:
            url = sqs.get_queue_url(QueueName=q_name)['QueueUrl']
            print(f"Purging {q_name} at {url}...")
            sqs.purge_queue(QueueUrl=url)
            print("Purge command sent successfully.")
        except Exception as e:
            print(f"Failed to purge {q_name}: {e}")

if __name__ == '__main__':
    purge_queues()
