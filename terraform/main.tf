terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}

provider "aws" { region = var.region }

data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

resource "aws_s3_bucket" "approved" {
  force_destroy = false
  lifecycle { prevent_destroy = true }
}
resource "aws_s3_bucket_public_access_block" "approved" {
  bucket                  = aws_s3_bucket.approved.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
resource "aws_s3_bucket_server_side_encryption_configuration" "approved" {
  bucket = aws_s3_bucket.approved.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}
resource "aws_s3_bucket_versioning" "approved" {
  bucket = aws_s3_bucket.approved.id
  versioning_configuration { status = "Enabled" }
}
resource "aws_s3_bucket_policy" "tls" {
  bucket = aws_s3_bucket.approved.id
  policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Sid = "DenyInsecureTransport", Effect = "Deny", Principal = "*", Action = "s3:*", Resource = [aws_s3_bucket.approved.arn, "${aws_s3_bucket.approved.arn}/*"], Condition = { Bool = { "aws:SecureTransport" = "false" } } }]
  })
}
resource "aws_iam_role" "lambda" {
  name_prefix        = "siftly-lambda-"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Principal = { Service = "lambda.amazonaws.com" }, Action = "sts:AssumeRole" }] })
}
resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${aws_lambda_function.moderate.function_name}"
  retention_in_days = 7
}
resource "aws_iam_role_policy" "lambda" {
  role = aws_iam_role.lambda.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = "rekognition:DetectModerationLabels", Resource = "*" },
    { Effect = "Allow", Action = "s3:PutObject", Resource = "${aws_s3_bucket.approved.arn}/approved/*" },
    { Effect = "Allow", Action = ["logs:CreateLogStream", "logs:PutLogEvents"], Resource = "arn:${data.aws_partition.current.partition}:logs:${var.region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/siftly-*:log-stream:*" }
  ] })
}
resource "aws_lambda_function" "moderate" {
  function_name                  = var.function_name
  role                           = aws_iam_role.lambda.arn
  handler                        = "app.handler"
  runtime                        = "python3.12"
  filename                       = "${path.module}/siftly-lambda.zip"
  source_code_hash               = filebase64sha256("${path.module}/siftly-lambda.zip")
  timeout                        = 25
  memory_size                    = 512
  reserved_concurrent_executions = var.reserved_concurrency
  environment {
    variables = {
      BUCKET_NAME           = aws_s3_bucket.approved.id
      BLOCKED_CATEGORIES    = var.blocked_categories
      MODERATION_CONFIDENCE = tostring(var.moderation_confidence)
    }
  }
}
resource "aws_apigatewayv2_api" "api" {
  name          = "siftly"
  protocol_type = "HTTP"
}
resource "aws_apigatewayv2_integration" "lambda" {
  api_id                 = aws_apigatewayv2_api.api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.moderate.invoke_arn
  payload_format_version = "2.0"
  timeout_milliseconds   = 29000
}
resource "aws_apigatewayv2_route" "index" {
  api_id    = aws_apigatewayv2_api.api.id
  route_key = "GET /"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}
resource "aws_apigatewayv2_route" "upload" {
  api_id    = aws_apigatewayv2_api.api.id
  route_key = "POST /upload"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}
resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.api.id
  name        = "$default"
  auto_deploy = true
  default_route_settings {
    throttling_burst_limit = 10
    throttling_rate_limit  = 5
  }
}
resource "aws_lambda_permission" "api" {
  statement_id  = "AllowApiGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.moderate.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.api.execution_arn}/*/*"
}
output "demo_url" { value = aws_apigatewayv2_api.api.api_endpoint }
output "approved_bucket" { value = aws_s3_bucket.approved.id }
