output "cluster_name" {
  value = module.eks.cluster_name
}

output "kubeconfig_command" {
  value = "aws eks update-kubeconfig --region ${var.region} --name ${module.eks.cluster_name}"
}

output "ecr_backend_url" {
  value = aws_ecr_repository.backend.repository_url
}

output "ecr_web_url" {
  value = aws_ecr_repository.web.repository_url
}

output "api_endpoint" {
  description = "Gateway URL when enable_api_gateway = true; otherwise use the ALB hostname from the Ingress."
  value       = var.enable_api_gateway ? module.api_gateway[0].api_endpoint : "use kubectl get ingress bizchat"
}
