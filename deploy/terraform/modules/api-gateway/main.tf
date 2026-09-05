variable "name" { type = string }
variable "vpc_id" { type = string }
variable "subnet_ids" { type = list(string) }
variable "alb_listener_arn" { type = string }
variable "jwt_issuer" { type = string }
variable "jwt_audience" { type = list(string) }
variable "tags" { type = map(string) }

resource "aws_security_group" "vpclink" {
  name        = "${var.name}-vpclink"
  description = "API Gateway VPC Link to the internal ALB"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = var.tags
}

resource "aws_apigatewayv2_vpc_link" "this" {
  name               = var.name
  subnet_ids         = var.subnet_ids
  security_group_ids = [aws_security_group.vpclink.id]
  tags               = var.tags
}

resource "aws_apigatewayv2_api" "this" {
  name          = var.name
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins = ["https://${var.name}.example.com"]
    allow_methods = ["GET", "POST", "OPTIONS"]
    allow_headers = ["content-type", "authorization"]
    max_age       = 3600
  }

  tags = var.tags
}

resource "aws_apigatewayv2_integration" "alb" {
  api_id             = aws_apigatewayv2_api.this.id
  integration_type   = "HTTP_PROXY"
  integration_uri    = var.alb_listener_arn
  integration_method = "ANY"
  connection_type    = "VPC_LINK"
  connection_id      = aws_apigatewayv2_vpc_link.this.id

  # Long enough for a multi-tool agent turn; 30s is the default and will cut SSE off.
  timeout_milliseconds = 29000

  # Hand the verified subject to the app so it can scope threads per user.
  request_parameters = {
    "overwrite:header.x-principal-id" = "$context.authorizer.claims.sub"
  }
}

resource "aws_apigatewayv2_authorizer" "jwt" {
  count            = var.jwt_issuer == "" ? 0 : 1
  api_id           = aws_apigatewayv2_api.this.id
  authorizer_type  = "JWT"
  identity_sources = ["$request.header.Authorization"]
  name             = "${var.name}-jwt"

  jwt_configuration {
    issuer   = var.jwt_issuer
    audience = var.jwt_audience
  }
}

resource "aws_apigatewayv2_route" "api" {
  api_id             = aws_apigatewayv2_api.this.id
  route_key          = "ANY /api/{proxy+}"
  target             = "integrations/${aws_apigatewayv2_integration.alb.id}"
  authorization_type = var.jwt_issuer == "" ? "NONE" : "JWT"
  authorizer_id      = var.jwt_issuer == "" ? null : aws_apigatewayv2_authorizer.jwt[0].id
}

resource "aws_apigatewayv2_route" "spa" {
  api_id    = aws_apigatewayv2_api.this.id
  route_key = "ANY /{proxy+}"
  target    = "integrations/${aws_apigatewayv2_integration.alb.id}"
}

resource "aws_cloudwatch_log_group" "access" {
  name              = "/aws/apigw/${var.name}"
  retention_in_days = 30
  tags              = var.tags
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.this.id
  name        = "$default"
  auto_deploy = true

  default_route_settings {
    throttling_burst_limit   = 200
    throttling_rate_limit    = 100
    detailed_metrics_enabled = true
  }

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.access.arn
    format = jsonencode({
      requestId = "$context.requestId"
      route     = "$context.routeKey"
      status    = "$context.status"
      latency   = "$context.responseLatency"
      principal = "$context.authorizer.claims.sub"
    })
  }

  tags = var.tags
}

output "api_endpoint" {
  value = aws_apigatewayv2_api.this.api_endpoint
}
