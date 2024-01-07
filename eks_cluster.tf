provider "aws" {
  region = "eu-north-1"
}

# Create a VPC
resource "aws_vpc" "msd_hw_vpc" {
  cidr_block = "10.0.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name = "msd_hw-vpc"
  }
}

# Create subnets in two different AZs
resource "aws_subnet" "msd_hw_subnet1" {
  vpc_id     = aws_vpc.msd_hw_vpc.id
  cidr_block = "10.0.1.0/24"
  availability_zone = "eu-north-1a"
  map_public_ip_on_launch = true

  tags = {
    Name = "msd_hw-subnet1"
  }
}

resource "aws_subnet" "msd_hw_subnet2" {
  vpc_id     = aws_vpc.msd_hw_vpc.id
  cidr_block = "10.0.2.0/24"
  availability_zone = "eu-north-1b"
  map_public_ip_on_launch = true

  tags = {
    Name = "msd_hw-subnet2"
  }
}

# IAM role for EKS
resource "aws_iam_role" "msd_hw_eks_role" {
  name = "msd_hw-eks-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Principal = {
          Service = ["eks.amazonaws.com", "ec2.amazonaws.com"]
        },
        Action = "sts:AssumeRole"
      }
    ]
  })
}

# Attach necessary policies to the EKS role
resource "aws_iam_role_policy_attachment" "eks-worker-node" {
  role       = aws_iam_role.msd_hw_eks_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"
}

resource "aws_iam_role_policy_attachment" "eks-cni-policy" {
  role       = aws_iam_role.msd_hw_eks_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
}

resource "aws_iam_role_policy_attachment" "ec2-container-registry-read" {
  role       = aws_iam_role.msd_hw_eks_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

resource "aws_iam_role_policy_attachment" "ec2-loadbalancing" {
  role       = aws_iam_role.msd_hw_eks_role.name
  policy_arn = "arn:aws:iam::aws:policy/ElasticLoadBalancingFullAccess"
}

# EKS Cluster
resource "aws_eks_cluster" "msd_hw_cluster" {
  name     = "msd_hw-cluster"
  role_arn = aws_iam_role.msd_hw_eks_role.arn

  vpc_config {
    subnet_ids = [aws_subnet.msd_hw_subnet1.id, aws_subnet.msd_hw_subnet2.id]
  }
}

# Create an Internet Gateway for public subnet
resource "aws_internet_gateway" "msd_hw_igw" {
  vpc_id = aws_vpc.msd_hw_vpc.id
}

# Create a NAT Gateway for private subnet (Assuming you have a public subnet)
resource "aws_eip" "msd_hw_eip" {
  vpc = true
}

resource "aws_nat_gateway" "msd_hw_nat" {
  allocation_id = aws_eip.msd_hw_eip.id
  subnet_id     = aws_subnet.msd_hw_subnet1.id  # Replace with your public subnet ID
}

# Route table and association for public subnet (Internet Gateway)
resource "aws_route_table" "public_route_table" {
  vpc_id = aws_vpc.msd_hw_vpc.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.msd_hw_igw.id
  }
}

resource "aws_route_table_association" "public_route_table_association" {
  subnet_id      = aws_subnet.msd_hw_subnet1.id  # Replace with your public subnet ID
  route_table_id = aws_route_table.public_route_table.id
}

# Route table and association for private subnet (NAT Gateway)
resource "aws_route_table" "private_route_table" {
  vpc_id = aws_vpc.msd_hw_vpc.id

  route {
    cidr_block = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.msd_hw_nat.id
  }
}

resource "aws_route_table_association" "private_route_table_association" {
  subnet_id      = aws_subnet.msd_hw_subnet2.id  # Replace with your private subnet ID
  route_table_id = aws_route_table.private_route_table.id
}

# VPC Endpoint for EKS
resource "aws_vpc_endpoint" "eks_endpoint" {
  vpc_id             = aws_vpc.msd_hw_vpc.id
  service_name       = "com.amazonaws.eu-north-1.eks"
  vpc_endpoint_type  = "Interface"
  subnet_ids         = [aws_subnet.msd_hw_subnet2.id]  # Replace with your private subnet ID

  private_dns_enabled = true

  tags = {
    Name = "eks-vpc-endpoint"
  }
}



# EKS Node Group with minimal size
resource "aws_eks_node_group" "msd_hw_node_group" {
  cluster_name    = aws_eks_cluster.msd_hw_cluster.name
  node_group_name = "msd_hw-node-group"
  node_role_arn   = aws_iam_role.msd_hw_eks_role.arn
  subnet_ids      = [aws_subnet.msd_hw_subnet1.id, aws_subnet.msd_hw_subnet2.id]

  scaling_config {
    desired_size = 1
    max_size     = 1
    min_size     = 1
  }
}
