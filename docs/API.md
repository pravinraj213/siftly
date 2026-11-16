# Siftly upload API

`POST /upload` accepts a binary JPEG or PNG of at most 3 MiB. The image itself is the request body. Use HTTPS and send a matching `Content-Type`. The endpoint validates the image signature; Rekognition performs image decoding and analysis.

```bash
curl --fail-with-body -X POST "$SIFTLY_URL/upload" \
  -H 'Content-Type: image/jpeg' --data-binary @photo.jpg
```

Responses are JSON. `decision` is one of:

- `accepted`: the image passed the configured policy and the S3 write returned success. `key` is the private object key, and `sha256` identifies the inspected and saved bytes.
- `rejected`: the policy matched; `categories` lists matching labels. No image write is attempted.
- `error`: the image was invalid or a service call failed. No image write is attempted before successful moderation. A storage error can be ambiguous if S3 completed a write but the response was lost.

The application must interpret errors as an unsuccessful upload; do not assume the image is safe. The model may miss content, so moderation is a policy signal rather than a guarantee. The endpoint has no authentication and should not be used for production traffic without access controls.

When integrating with an existing application, submit the **exact bytes that should be saved**. The demo browser converts the selected image to a bounded JPEG; this may reduce detail and remove metadata. API callers may choose their own preprocessing but must send a JPEG or PNG that fits the size limit.
