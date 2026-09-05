data "aws_availability_zones" "this" {
  state = "available"
}

locals {
  azs             = slice(data.aws_availability_zones.this.names, 0, 2)
  public_subnets  = [for i, _ in local.azs : cidrsubnet(var.vpc_cidr, 4, i)]
  private_subnets = [for i, _ in local.azs : cidrsubnet(var.vpc_cidr, 4, i + 8)]
}

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.16"

  name = var.name
  cidr = var.vpc_cidr
  azs  = local.azs

  public_subnets  = local.public_subnets
  private_subnets = local.private_subnets

  enable_nat_gateway   = true
  single_nat_gateway   = true
  enable_dns_hostnames = true

  public_subnet_tags  = { "kubernetes.io/role/elb" = 1 }
  private_subnet_tags = { "kubernetes.io/role/internal-elb" = 1 }

  tags = var.tags
}

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.31"

  cluster_name    = var.name
  cluster_version = var.cluster_version

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  # Private-only endpoint when the gateway fronts the cluster.
  cluster_endpoint_public_access = !var.enable_api_gateway

  enable_irsa                              = true
  enable_cluster_creator_admin_permissions = true

  eks_managed_node_groups = {
    default = {
      instance_types = var.node_instance_types
      min_size       = 2
      max_size       = 6
      desired_size   = 2
    }
  }

  tags = var.tags
}

resource "aws_ecr_repository" "backend" {
  name                 = "${var.name}-backend"
  image_tag_mutability = "IMMUTABLE"
  image_scanning_configuration { scan_on_push = true }
  tags = var.tags
}

resource "aws_ecr_repository" "web" {
  name                 = "${var.name}-web"
  image_tag_mutability = "IMMUTABLE"
  image_scanning_configuration { scan_on_push = true }
  tags = var.tags
}

resource "aws_secretsmanager_secret" "app" {
  name = "${var.name}/app"
  tags = var.tags
}

# --- Optional API Gateway front door -----------------------------------------

module "api_gateway" {
  source = "./modules/api-gateway"
  count  = var.enable_api_gateway ? 1 : 0

  name              = var.name
  vpc_id            = module.vpc.vpc_id
  subnet_ids        = module.vpc.private_subnets
  jwt_issuer        = var.jwt_issuer
  jwt_audience      = var.jwt_audience
  alb_listener_arn  = var.internal_alb_listener_arn
  tags              = var.tags
}
