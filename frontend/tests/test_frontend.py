import pytest

def test_index_get(client):
    """Test that the index renders our homepage"""
    response = client.get('/')
    assert response.status_code == 200
    # ensure it loads some basic HTML layout
    assert b"<!DOCTYPE html>" in response.data

def test_index_post_new_url(client, aws_setup):
    """Test generating a new crawl request puts an SQS msg."""
    response = client.post('/', data={'url': 'www.example.com'})
    
    # It should redirect to the clean domain
    assert response.status_code == 302
    assert response.location == '/www.example.com'
    
    # Check if a message was put into the websiteovertime-geturl.fifo queue
    sqs = aws_setup['sqs']
    messages = sqs.receive_message(
        QueueUrl=aws_setup['geturl_queue_url'],
        MaxNumberOfMessages=1
    )
    
    assert 'Messages' in messages
    assert len(messages['Messages']) == 1
    
    msg_body = messages['Messages'][0]['Body']
    assert msg_body == 'http://www.example.com'
