"""Siftly: inspect the submitted bytes before any persistent application write."""
import base64
import binascii
import hashlib
import json
import os
import uuid
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

MAX_BYTES = 3 * 1024 * 1024
BLOCKED = frozenset(x.strip().lower() for x in os.getenv('BLOCKED_CATEGORIES', 'Explicit,Non-Explicit Nudity of Intimate parts and Kissing,Swimwear or Underwear,Violence,Visually Disturbing').split(',') if x.strip())
THRESHOLD = float(os.getenv('MODERATION_CONFIDENCE', '70'))
# Keep a moderation failure and a storage attempt within the Lambda timeout.
moderation_config = Config(connect_timeout=2, read_timeout=7, retries={'total_max_attempts': 2, 'mode': 'standard'})
storage_config = Config(connect_timeout=2, read_timeout=5, retries={'total_max_attempts': 1, 'mode': 'standard'})
rekognition = boto3.client('rekognition', config=moderation_config)
s3 = boto3.client('s3', config=storage_config)


def response(status, body):
    return {'statusCode': status, 'headers': {'content-type': 'application/json', 'cache-control': 'no-store', 'x-content-type-options': 'nosniff'}, 'body': json.dumps(body)}


def handler(event, context):
    method = event.get('requestContext', {}).get('http', {}).get('method', '')
    if method == 'GET':
        return {'statusCode': 200, 'headers': {'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-store', 'x-content-type-options': 'nosniff'}, 'body': Path(__file__).with_name('index.html').read_text(encoding='utf-8')}
    if method != 'POST':
        return response(405, {'decision': 'error', 'message': 'Method not allowed.'})
    try:
        if not event.get('isBase64Encoded'):
            return response(400, {'decision': 'error', 'message': 'Send a JPEG or PNG image as binary data.'})
        body = event.get('body') or ''
        if not isinstance(body, str) or len(body) > 4 * ((MAX_BYTES + 2) // 3):
            return response(413, {'decision': 'error', 'message': 'Image must be no larger than 3 MB.'})
        image = base64.b64decode(body, validate=True)
        if not image or len(image) > MAX_BYTES:
            return response(413, {'decision': 'error', 'message': 'Image must be between 1 byte and 3 MB.'})
        if image.startswith(b'\xff\xd8\xff'):
            content_type, extension = 'image/jpeg', 'jpg'
        elif image.startswith(b'\x89PNG\r\n\x1a\n'):
            content_type, extension = 'image/png', 'png'
        else:
            return response(415, {'decision': 'error', 'message': 'Only JPEG and PNG images are supported.'})
        result = rekognition.detect_moderation_labels(Image={'Bytes': image}, MinConfidence=THRESHOLD)
        labels = result.get('ModerationLabels')
        if not isinstance(labels, list) or any(not isinstance(label, dict) or not isinstance(label.get('Name'), str) or not isinstance(label.get('ParentName', ''), str) for label in labels):
            return response(503, {'decision': 'error', 'message': 'The moderation response could not be verified. Please try again.'})
        matches = [label for label in labels if label['Name'].lower() in BLOCKED or label.get('ParentName', '').lower() in BLOCKED]
        if matches:
            return response(200, {'decision': 'rejected', 'message': 'The image matched this site’s content policy.', 'categories': sorted(set(x['Name'] for x in matches)), 'policy_threshold': THRESHOLD})
        key = f"approved/{uuid.uuid4().hex}.{extension}"
        digest = hashlib.sha256(image).hexdigest()
        s3.put_object(Bucket=os.environ['BUCKET_NAME'], Key=key, Body=image, ContentType=content_type, Metadata={'sha256': digest})
        return response(200, {'decision': 'accepted', 'message': 'The checked image was saved.', 'key': key, 'sha256': digest, 'policy_threshold': THRESHOLD})
    except (ValueError, binascii.Error):
        return response(400, {'decision': 'error', 'message': 'Invalid image payload.'})
    except (ClientError, BotoCoreError, KeyError):
        return response(503, {'decision': 'error', 'message': 'The image could not be checked or saved. Please try again.'})
