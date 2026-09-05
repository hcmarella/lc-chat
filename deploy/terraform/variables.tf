variable "region" {
  type    = string
  default = "us-east-1"
}

variable "name" {
  type    = string
  default = "bizchat"
}

variable "vpc_cidr" {
  type    = string
  default = "10.60.0.0/16"
}

variable "cluster_version" {
  type    = string
  default = "1.31"
}

variable "node_instance_types" {
  type    = list(string)
  default = ["t3.large"]
}

# The switch the requirement hinges on.
#   true  -> API Gateway HTTP API + VPC Link in front of an internal ALB
#            (JWT auth, throttling, WAF, usage plans, per-route metering)
#   false -> internet-facing ALB straight to the EKS services
#            (fewer hops, lower latency and cost, auth handled in-app/OIDC)
variable "enable_api_gateway" {
  type    = bool
  default = true
}

variable "jwt_issuer" {
  type        = string
  default     = ""
  description = "OIDC issuer URL (e.g. Cognito user pool) used by the gateway authorizer."
}

variable "jwt_audience" {
  type    = list(string)
  default = []
}

variable "internal_alb_listener_arn" {
  type        = string
  default     = ""
  description = "ARN of the internal ALB listener created by the AWS Load Balancer Controller. Fill in after the first apply of ingress-vpclink.yaml."
}

variable "tags" {
  type = map(string)
  default = {
    Project = "bizchat"
    Owner   = "platform"
  }
}
