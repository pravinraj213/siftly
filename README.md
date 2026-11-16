# Siftly

**Only the right images make it through.**

Siftly is a serverless image-upload demo that runs a configurable Amazon Rekognition moderation check before saving the image. The browser silently prepares a JPEG from the selected JPEG or PNG, then sends it through API Gateway to Lambda. Lambda passes those exact bytes to Rekognition. A policy match or a moderation error causes no S3 write; when allowed, those same bytes are saved to a private S3 bucket.

```text
Browser -> API Gateway -> Lambda -> Rekognition
                             |          |
                             |      policy match/error -> no S3 write
                             +------ pass -> private S3
```

See [architecture and moderation policy](docs/ARCHITECTURE.md) and the [test plan](docs/TESTING.md).

## Run locally

The core policy and storage boundary can be verified without AWS credentials:

```bash
python3 -m unittest discover -s tests -v
```

The browser interface is served by the Lambda `GET /` route; `POST /upload` accepts a raw JPEG or PNG request body. Browser preprocessing outputs a JPEG of up to 3 MiB and at most 2500 pixels on the longest side. The backend validates size and file signature independently. It stores the exact submitted bytes, not the original file; the result includes a SHA-256 digest for comparison. A client can bypass browser preprocessing, so only the backend's limits are authoritative.

## Deploy with Terraform

Prerequisites: Terraform 1.5+, AWS credentials, an AWS region with Rekognition image moderation, and permission to create API Gateway, Lambda, IAM, CloudWatch Logs, and S3 resources. Terraform downloads the AWS provider during init; the package script uses the local zip utility. The API is public and incurs per-request charges; use it for a limited demo only. API throttling reduces but does not eliminate abuse or charges. Reserved concurrency is optional and disabled by default because some AWS accounts have low concurrency quotas; set `reserved_concurrency` only when sufficient capacity is available.

```bash
./terraform/package.sh
cd terraform
terraform init
terraform validate
terraform plan -out=siftly.tfplan
terraform apply siftly.tfplan
terraform output -raw demo_url
```

Re-run `./terraform/package.sh` from the project root before planning whenever backend files change. Apply the saved plan without changing the package. Run `./terraform/check.sh` for tests, formatting, packaging and provider validation once Terraform is initialized. Open `demo_url` in a browser. The app and API share the same origin. Upload a normal synthetic image to exercise the accepted path. For an automated reproducible rejected-path demonstration, the tests simulate Rekognition responses rather than upload harmful imagery. Verify the actual model behavior with suitable authorized test fixtures; no moderation outcome is guaranteed.

`blocked_categories`, `moderation_confidence`, `region`, and `function_name` can be changed as Terraform variables. The default policy is illustrative, not a universal definition of unacceptable content. Each moderation label is compared by name or immediate parent. Evaluate the taxonomy and thresholds against your policy and labeled images before using it for real decisions.

## Boundaries

- Rejected images and images whose moderation fails are not written to **the application's S3 bucket**. They are transmitted through API Gateway, Lambda and Rekognition, and service processing and retention policies apply. Application code does not log image bytes. API access, execution and third-party logs must likewise never capture request bodies.
- Model results are probabilistic; an accepted image is not guaranteed safe. Browser resizing may remove details. JPEG re-encoding changes and strips metadata from the submitted file.
- A storage request can time out after S3 accepts it; the caller may see an error although an approved image was stored. Retrying can create duplicates. No write is attempted until moderation has passed.
- The endpoint has no authentication and is not production-ready. Add authentication, quotas, input decoding validation, abuse controls and operational monitoring before public use. Public invocation can incur AWS charges.
- Terraform protects the image bucket against accidental destroy (`prevent_destroy`). It and its objects require an intentional cleanup process.
