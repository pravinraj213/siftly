# Siftly test plan

## Local deterministic tests

`python3 -m unittest discover -s tests -v` runs without an AWS account. Mocked responses verify matching labels, malformed responses and service errors, and assert rejected images never reach the S3 client. These are implementation checks, not measurements of Rekognition accuracy.

## After deployment: real end-to-end checks

Use only images you own or are authorized to use. Do not use illegal content. First confirm the bucket is private and note its current object count.

1. **Expected acceptance:** Upload an ordinary photo you took, such as a landscape, flower, or empty desk. Expect an accepted result, though a prediction can vary. Verify one new object exists under `approved/` and compare its SHA-256 with the UI result.
2. **Expected policy match:** Use a suitable authorized non-graphic photo of a kitchen knife or a person in swimwear. These are legitimate images but are included in the *example* strict policy. Rekognition may not detect a label at the chosen threshold; inspect the actual response and do not present a guessed result as proof. Verify no new object is written if the result is rejected.
3. **Invalid file:** POST a text file to `/upload`. Expect an error and no new S3 object.
4. **Moderation error:** In an isolated test deployment, use a controlled service failure (such as a mock or a temporarily restricted execution role) and verify the response fails and no object is written. Restore permissions after the test. Unit tests cover the same branch locally.

Use a labeled dataset with both positive and negative examples to estimate false-positive and false-negative behavior. A few demo examples do not establish accuracy. An S3 write can complete even when its response is lost, so treat storage errors differently from moderation failures.
