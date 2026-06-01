data "aws_caller_identity" "current" {}

resource "aws_iam_role" "pipeline_runner" {
  name = "nbahl-pipeline-runner-dev"

  assume_role_policy = jsonencode(
    {
      Version = "2012-10-17"
      Statement = [
        {
          Effect    = "Allow"
          Principal = { AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root" }
          Action    = "sts:AssumeRole"
        }
      ]
    }
  )

  tags = local.common_tags
}

resource "aws_iam_role_policy" "pipeline_runner_s3" {
  name = "nbahl-pipeline-runner-s3-dev"
  role = aws_iam_role.pipeline_runner.id
  policy = jsonencode(
    {
      Version = "2012-10-17"
      Statement = [
        {
          Effect = "Allow"
          Action = [
            "s3:PutObject",
            "s3:GetObject",
            "s3:DeleteObject",
            "s3:ListBucket",
            "s3:GetBucketLocation",
            "s3:AbortMultipartUpload",
            "s3:ListMultipartUploadParts",
          ]
          Resource = [
            aws_s3_bucket.bronze.arn,
            "${aws_s3_bucket.bronze.arn}/*",
            aws_s3_bucket.silver.arn,
            "${aws_s3_bucket.silver.arn}/*",
            aws_s3_bucket.gold.arn,
            "${aws_s3_bucket.gold.arn}/*"
          ]
        }
      ]
    }
  )
}

resource "aws_iam_role_policy" "pipeline_runner_logs" {
  name = "nbahl-pipeline-runner-logs-dev"
  role = aws_iam_role.pipeline_runner.id
  policy = jsonencode(
    {
      Version = "2012-10-17"
      Statement = [
        {
          Sid    = "LogGroupActions"
          Effect = "Allow"
          Action = [
            "logs:CreateLogGroup",
            "logs:DescribeLogGroups",
            "logs:DescribeLogStreams"
          ]
          Resource = "arn:aws:logs:${var.region}:${data.aws_caller_identity.current.account_id}:log-group:/nbahl/dev/*"
        },
        {
          Sid    = "LogStreamActions"
          Effect = "Allow"
          Action = [
            "logs:CreateLogStream",
            "logs:PutLogEvents"
          ]
          Resource = "arn:aws:logs:${var.region}:${data.aws_caller_identity.current.account_id}:log-group:/nbahl/dev/*:log-stream:*"
        }
      ]
    }
  )
}
