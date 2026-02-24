# `test_s3.py`

## Role
This script is a simple utility or scratchpad for testing interactions with the AWS S3 `boto3` API.

## Workflow
- It explores ways to copy objects between buckets/folders:
  `s3.Object(...).copy_from(...)`
- Uses `S3Path` library to iterate over subdirectories acting identically to local standard paths: `[str(item)[29:] for item in S3Path(...).iterdir() if item.is_dir()]`
- Iterates over generated subdirectories and constructs publicly accessible URLs given a specific domain.
