output "alb_dns" {
  value       = aws_lb.main.dns_name
  description = "ALB public DNS — the API endpoint"
}

output "ecr_repo_url" {
  value       = aws_ecr_repository.api.repository_url
  description = "ECR repository URL — push Docker images here"
}

output "db_endpoint" {
  value       = aws_db_instance.postgres.address
  description = "RDS PostgreSQL endpoint (internal)"
}

output "deploy_commands" {
  value = <<-EOT
    # 1. Build and push the Docker image:
    aws ecr get-login-password --region ${var.region} | docker login --username AWS --password-stdin ${aws_ecr_repository.api.repository_url}
    cd backend && docker build -t ${aws_ecr_repository.api.repository_url}:latest . && docker push ${aws_ecr_repository.api.repository_url}:latest

    # 2. Update the ECS service to pull the new image:
    aws ecs update-service --cluster ${var.project} --service ${var.project}-api --force-new-deployment --region ${var.region}

    # 3. The API will be available at:
    #    http://${aws_lb.main.dns_name}
  EOT
  description = "Commands to deploy the application"
}
