import pytest
import boto3
from moto import mock_sqs, mock_s3
import os
import sys

# Add our source directories to the path so tests can import them
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

@pytest.fixture(scope='function')
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
    os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
    os.environ['AWS_SECURITY_TOKEN'] = 'testing'
    os.environ['AWS_SESSION_TOKEN'] = 'testing'
    os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'

@pytest.fixture(scope='function')
def aws_setup(aws_credentials):
    with mock_sqs(), mock_s3():
        sqs = boto3.client('sqs', region_name='us-east-1')
        s3 = boto3.client('s3', region_name='us-east-1')

        # Set up the expected queues
        geturl_queue = sqs.create_queue(
            QueueName='websiteovertime-geturl.fifo',
            Attributes={'FifoQueue': 'true'}
        )
        getscreenshot_queue = sqs.create_queue(
            QueueName='websiteovertime-getscreenshot.fifo',
            Attributes={'FifoQueue': 'true'}
        )
        
        # Set up the expected S3 bucket
        s3.create_bucket(Bucket='websiteovertime')
        
        yield {
            'sqs': sqs,
            's3': s3,
            'geturl_queue_url': geturl_queue['QueueUrl'],
            'getscreenshot_queue_url': getscreenshot_queue['QueueUrl']
        }

@pytest.fixture
def app(aws_setup):
    """Create and configure a new app instance for each test."""
    # We import inside the fixture to ensure 'moto' mocks are active
    # before the global boto3.resource() calls inside the modules run
    from app_lambda import app
    app.config.update({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False
    })
    yield app

@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()
