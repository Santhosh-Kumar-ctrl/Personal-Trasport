# IAM user with scoped access to only the bus-tracking deployment.
# Santhosh gets credentials to deploy and monitor — nothing else.

resource "aws_iam_user" "deployer" {
  name = "${var.project}-deployer"
}

resource "aws_iam_access_key" "deployer" {
  user = aws_iam_user.deployer.name
}

resource "aws_iam_user_policy" "deployer" {
  name = "bus-tracking-deploy-only"
  user = aws_iam_user.deployer.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ECRPushPull"
        Effect = "Allow"
        Action = [
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:BatchCheckLayerAvailability",
          "ecr:PutImage",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload",
          "ecr:GetAuthorizationToken",
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "ecr:ResourceTag/Project" = var.project
          }
        }
      },
      {
        Sid      = "ECRAuth"
        Effect   = "Allow"
        Action   = ["ecr:GetAuthorizationToken"]
        Resource = "*"
      },
      {
        Sid    = "ECSDeployAndMonitor"
        Effect = "Allow"
        Action = [
          "ecs:UpdateService",
          "ecs:DescribeServices",
          "ecs:DescribeTasks",
          "ecs:ListTasks",
          "ecs:DescribeTaskDefinition",
          "ecs:RegisterTaskDefinition",
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "aws:ResourceTag/Project" = var.project
          }
        }
      },
      {
        Sid    = "ECSListAndPassRole"
        Effect = "Allow"
        Action = [
          "iam:PassRole",
        ]
        Resource = [
          aws_iam_role.ecs_execution.arn,
          aws_iam_role.ecs_task.arn,
          "arn:aws:ecs:${var.region}:*:*",
        ]
      },
      {
        Sid      = "ECSList"
        Effect   = "Allow"
        Action   = ["ecs:ListServices", "ecs:ListClusters"]
        Resource = "*"
      },
      {
        Sid    = "Logs"
        Effect = "Allow"
        Action = [
          "logs:GetLogEvents",
          "logs:FilterLogEvents",
          "logs:DescribeLogStreams",
        ]
        Resource = "${aws_cloudwatch_log_group.api.arn}:*"
      },
      {
        Sid    = "RDSReadOnly"
        Effect = "Allow"
        Action = [
          "rds:DescribeDBInstances",
        ]
        Resource = aws_db_instance.postgres.arn
      },
    ]
  })
}

output "deployer_access_key_id" {
  value       = aws_iam_access_key.deployer.id
  description = "Access Key ID for the deployer user"
}

output "deployer_secret_access_key" {
  value       = aws_iam_access_key.deployer.secret
  sensitive   = true
  description = "Secret Access Key for the deployer user (terraform output -raw deployer_secret_access_key)"
}
