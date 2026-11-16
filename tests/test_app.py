import base64
import importlib.util
import json
import os
import unittest
from unittest.mock import Mock, patch

os.environ.update(AWS_ACCESS_KEY_ID='test', AWS_SECRET_ACCESS_KEY='test', AWS_DEFAULT_REGION='us-east-1', BUCKET_NAME='test-bucket', AWS_EC2_METADATA_DISABLED='true')
spec = importlib.util.spec_from_file_location('siftly_app', os.path.join(os.path.dirname(__file__), '..', 'backend', 'app.py'))
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)


def event(image):
    return {'requestContext': {'http': {'method': 'POST'}}, 'isBase64Encoded': True, 'body': base64.b64encode(image).decode()}


class StorageBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.image = b'\xff\xd8\xffsample-image'
        self.moderator = Mock()
        self.store = Mock()
        self.patches = [patch.object(app, 'rekognition', self.moderator), patch.object(app, 's3', self.store)]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def test_accepted_bytes_are_exactly_the_checked_bytes(self):
        self.moderator.detect_moderation_labels.return_value = {'ModerationLabels': []}
        result = app.handler(event(self.image), None)
        self.assertEqual(json.loads(result['body'])['decision'], 'accepted')
        self.assertEqual(self.moderator.detect_moderation_labels.call_args.kwargs['Image']['Bytes'], self.image)
        self.assertEqual(self.store.put_object.call_args.kwargs['Body'], self.image)

    def test_rejected_image_never_reaches_s3(self):
        self.moderator.detect_moderation_labels.return_value = {'ModerationLabels': [{'Name': 'Explicit', 'Confidence': 99}]}
        result = app.handler(event(self.image), None)
        self.assertEqual(json.loads(result['body'])['decision'], 'rejected')
        self.store.put_object.assert_not_called()

    def test_moderation_failure_does_not_store(self):
        self.moderator.detect_moderation_labels.side_effect = app.BotoCoreError()
        result = app.handler(event(self.image), None)
        self.assertEqual(result['statusCode'], 503)
        self.store.put_object.assert_not_called()

    def test_invalid_image_does_not_call_aws(self):
        self.assertEqual(app.handler(event(b'not an image'), None)['statusCode'], 415)
        self.moderator.detect_moderation_labels.assert_not_called()
        self.store.put_object.assert_not_called()

    def test_incomplete_moderation_response_fails_closed(self):
        self.moderator.detect_moderation_labels.return_value = {}
        self.assertEqual(app.handler(event(self.image), None)['statusCode'], 503)
        self.store.put_object.assert_not_called()

    def test_parent_category_is_blocked(self):
        self.moderator.detect_moderation_labels.return_value = {'ModerationLabels': [{'Name': 'Explicit Nudity', 'ParentName': 'Explicit', 'Confidence': 90}]}
        self.assertEqual(json.loads(app.handler(event(self.image), None)['body'])['decision'], 'rejected')
        self.store.put_object.assert_not_called()

    def test_storage_failure_is_reported_as_error(self):
        self.moderator.detect_moderation_labels.return_value = {'ModerationLabels': []}
        self.store.put_object.side_effect = app.BotoCoreError()
        self.assertEqual(app.handler(event(self.image), None)['statusCode'], 503)

    def test_oversize_image_is_rejected(self):
        self.assertEqual(app.handler(event(b'x' * (app.MAX_BYTES + 1)), None)['statusCode'], 413)
        self.store.put_object.assert_not_called()

if __name__ == '__main__':
    unittest.main()
