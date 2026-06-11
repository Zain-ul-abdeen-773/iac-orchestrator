"""
Mock Terraform AWS Provider Documentation — RAG Knowledge Base

This file contains curated, real-world HCL syntax examples for common AWS
resources. It serves as the RAG context source for the Context Retriever node,
grounding the Architect agent in current, valid Terraform syntax.

In production, this would be replaced with a full ingestion of the official
Terraform AWS Provider documentation.
"""

# ─────────────────────────────────────────────────────────────────────
# DOCUMENT: AWS VPC and Networking
# ─────────────────────────────────────────────────────────────────────

AWS_VPC_DOCS = """
## AWS VPC — Virtual Private Cloud

### Resource: aws_vpc
Creates a VPC with the specified CIDR block.

```hcl
resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name        = "main-vpc"
    Environment = "production"
    ManagedBy   = "terraform"
  }
}
```

### Resource: aws_subnet (Public)
```hcl
resource "aws_subnet" "public" {
  count                   = 2
  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(aws_vpc.main.cidr_block, 8, count.index)
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true

  tags = {
    Name = "public-subnet-${count.index + 1}"
  }
}
```

### Resource: aws_subnet (Private)
```hcl
resource "aws_subnet" "private" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(aws_vpc.main.cidr_block, 8, count.index + 10)
  availability_zone = data.aws_availability_zones.available.names[count.index]

  tags = {
    Name = "private-subnet-${count.index + 1}"
  }
}
```

### Resource: aws_internet_gateway
```hcl
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "main-igw"
  }
}
```

### Resource: aws_nat_gateway
```hcl
resource "aws_eip" "nat" {
  domain = "vpc"
}

resource "aws_nat_gateway" "main" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.public[0].id

  tags = {
    Name = "main-nat-gateway"
  }

  depends_on = [aws_internet_gateway.main]
}
```

### Resource: aws_route_table
```hcl
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = {
    Name = "public-rt"
  }
}

resource "aws_route_table_association" "public" {
  count          = 2
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}
```

### Resource: aws_security_group
```hcl
resource "aws_security_group" "web" {
  name_prefix = "web-sg-"
  description = "Security group for web servers"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "HTTPS from anywhere"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTP from anywhere"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "web-security-group"
  }
}
```

### Resource: aws_flow_log (VPC Flow Logs)
```hcl
resource "aws_flow_log" "vpc" {
  vpc_id               = aws_vpc.main.id
  traffic_type         = "ALL"
  log_destination_type = "cloud-watch-logs"
  log_destination      = aws_cloudwatch_log_group.flow_log.arn
  iam_role_arn         = aws_iam_role.flow_log.arn

  tags = {
    Name = "vpc-flow-log"
  }
}
```
"""

# ─────────────────────────────────────────────────────────────────────
# DOCUMENT: AWS EC2 Instances
# ─────────────────────────────────────────────────────────────────────

AWS_EC2_DOCS = """
## AWS EC2 — Elastic Compute Cloud

### Resource: aws_instance
```hcl
resource "aws_instance" "web" {
  ami                    = data.aws_ami.amazon_linux.id
  instance_type          = "t3.micro"
  subnet_id              = aws_subnet.private[0].id
  vpc_security_group_ids = [aws_security_group.web.id]

  root_block_device {
    volume_type = "gp3"
    volume_size = 20
    encrypted   = true
  }

  metadata_options {
    http_tokens   = "required"   # IMDSv2 enforced
    http_endpoint = "enabled"
  }

  monitoring = true  # Detailed CloudWatch monitoring

  tags = {
    Name        = "web-server"
    Environment = "production"
    ManagedBy   = "terraform"
  }
}
```

### Data Source: aws_ami (Amazon Linux 2023)
```hcl
data "aws_ami" "amazon_linux" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}
```

### Resource: aws_launch_template (for ASG)
```hcl
resource "aws_launch_template" "web" {
  name_prefix   = "web-lt-"
  image_id      = data.aws_ami.amazon_linux.id
  instance_type = "t3.micro"

  network_interfaces {
    associate_public_ip_address = false
    security_groups             = [aws_security_group.web.id]
  }

  block_device_mappings {
    device_name = "/dev/xvda"
    ebs {
      volume_size = 20
      volume_type = "gp3"
      encrypted   = true
    }
  }

  metadata_options {
    http_tokens = "required"
  }

  tag_specifications {
    resource_type = "instance"
    tags = {
      Name = "web-asg-instance"
    }
  }
}
```
"""

# ─────────────────────────────────────────────────────────────────────
# DOCUMENT: AWS S3 Buckets
# ─────────────────────────────────────────────────────────────────────

AWS_S3_DOCS = """
## AWS S3 — Simple Storage Service

### Resource: aws_s3_bucket
```hcl
resource "aws_s3_bucket" "data" {
  bucket = "my-secure-data-bucket-${random_id.suffix.hex}"

  tags = {
    Name        = "data-bucket"
    Environment = "production"
    ManagedBy   = "terraform"
  }
}
```

### Resource: aws_s3_bucket_versioning
```hcl
resource "aws_s3_bucket_versioning" "data" {
  bucket = aws_s3_bucket.data.id

  versioning_configuration {
    status = "Enabled"
  }
}
```

### Resource: aws_s3_bucket_server_side_encryption_configuration
```hcl
resource "aws_s3_bucket_server_side_encryption_configuration" "data" {
  bucket = aws_s3_bucket.data.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.s3.arn
    }
    bucket_key_enabled = true
  }
}
```

### Resource: aws_s3_bucket_public_access_block
```hcl
resource "aws_s3_bucket_public_access_block" "data" {
  bucket = aws_s3_bucket.data.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
```

### Resource: aws_s3_bucket_logging
```hcl
resource "aws_s3_bucket_logging" "data" {
  bucket = aws_s3_bucket.data.id

  target_bucket = aws_s3_bucket.log_bucket.id
  target_prefix = "s3-access-logs/"
}
```

### Resource: aws_s3_bucket_lifecycle_configuration
```hcl
resource "aws_s3_bucket_lifecycle_configuration" "data" {
  bucket = aws_s3_bucket.data.id

  rule {
    id     = "archive-old-objects"
    status = "Enabled"

    transition {
      days          = 90
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 180
      storage_class = "GLACIER"
    }

    noncurrent_version_expiration {
      noncurrent_days = 365
    }
  }
}
```
"""

# ─────────────────────────────────────────────────────────────────────
# DOCUMENT: AWS RDS — Relational Database Service
# ─────────────────────────────────────────────────────────────────────

AWS_RDS_DOCS = """
## AWS RDS — Relational Database Service

### Resource: aws_db_subnet_group
```hcl
resource "aws_db_subnet_group" "main" {
  name       = "main-db-subnet-group"
  subnet_ids = aws_subnet.private[*].id

  tags = {
    Name = "main-db-subnet-group"
  }
}
```

### Resource: aws_db_instance (PostgreSQL)
```hcl
resource "aws_db_instance" "postgres" {
  identifier     = "main-postgres"
  engine         = "postgres"
  engine_version = "15.4"
  instance_class = "db.t3.micro"

  allocated_storage     = 20
  max_allocated_storage = 100
  storage_type          = "gp3"
  storage_encrypted     = true
  kms_key_id            = aws_kms_key.rds.arn

  db_name  = "appdb"
  username = "dbadmin"
  password = var.db_password

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.database.id]

  multi_az            = true
  publicly_accessible = false
  deletion_protection = true

  backup_retention_period = 7
  backup_window           = "03:00-04:00"
  maintenance_window      = "Mon:04:00-Mon:05:00"

  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]

  skip_final_snapshot       = false
  final_snapshot_identifier = "main-postgres-final"

  tags = {
    Name        = "main-postgres"
    Environment = "production"
    ManagedBy   = "terraform"
  }
}
```

### Resource: aws_security_group (Database)
```hcl
resource "aws_security_group" "database" {
  name_prefix = "db-sg-"
  description = "Security group for RDS database"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "PostgreSQL from app servers"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.web.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "database-security-group"
  }
}
```
"""

# ─────────────────────────────────────────────────────────────────────
# DOCUMENT: AWS EKS — Elastic Kubernetes Service
# ─────────────────────────────────────────────────────────────────────

AWS_EKS_DOCS = """
## AWS EKS — Elastic Kubernetes Service

### Resource: aws_eks_cluster
```hcl
resource "aws_eks_cluster" "main" {
  name     = "main-cluster"
  role_arn = aws_iam_role.eks_cluster.arn
  version  = "1.29"

  vpc_config {
    subnet_ids              = aws_subnet.private[*].id
    endpoint_private_access = true
    endpoint_public_access  = false
    security_group_ids      = [aws_security_group.eks_cluster.id]
  }

  encryption_config {
    provider {
      key_arn = aws_kms_key.eks.arn
    }
    resources = ["secrets"]
  }

  enabled_cluster_log_types = [
    "api", "audit", "authenticator",
    "controllerManager", "scheduler"
  ]

  tags = {
    Name        = "main-eks-cluster"
    Environment = "production"
    ManagedBy   = "terraform"
  }

  depends_on = [
    aws_iam_role_policy_attachment.eks_cluster_policy,
    aws_iam_role_policy_attachment.eks_service_policy,
  ]
}
```

### Resource: aws_eks_node_group
```hcl
resource "aws_eks_node_group" "workers" {
  cluster_name    = aws_eks_cluster.main.name
  node_group_name = "workers"
  node_role_arn   = aws_iam_role.eks_node.arn
  subnet_ids      = aws_subnet.private[*].id

  scaling_config {
    desired_size = 2
    max_size     = 5
    min_size     = 1
  }

  instance_types = ["t3.medium"]
  ami_type       = "AL2_x86_64"

  disk_size = 20

  update_config {
    max_unavailable = 1
  }

  tags = {
    Name = "eks-worker-nodes"
  }

  depends_on = [
    aws_iam_role_policy_attachment.eks_worker_node_policy,
    aws_iam_role_policy_attachment.eks_cni_policy,
    aws_iam_role_policy_attachment.ecr_read_only,
  ]
}
```

### Resource: aws_iam_role (EKS Cluster)
```hcl
resource "aws_iam_role" "eks_cluster" {
  name = "eks-cluster-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "eks.amazonaws.com"
      }
    }]
  })

  tags = {
    Name = "eks-cluster-role"
  }
}

resource "aws_iam_role_policy_attachment" "eks_cluster_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
  role       = aws_iam_role.eks_cluster.name
}

resource "aws_iam_role_policy_attachment" "eks_service_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSServicePolicy"
  role       = aws_iam_role.eks_cluster.name
}
```
"""

# ─────────────────────────────────────────────────────────────────────
# DOCUMENT: AWS IAM — Identity and Access Management
# ─────────────────────────────────────────────────────────────────────

AWS_IAM_DOCS = """
## AWS IAM — Identity and Access Management

### Resource: aws_iam_role (Generic)
```hcl
resource "aws_iam_role" "app" {
  name = "app-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ec2.amazonaws.com"
      }
    }]
  })

  tags = {
    Name = "app-role"
  }
}
```

### Resource: aws_iam_policy (Least Privilege)
```hcl
resource "aws_iam_policy" "s3_read" {
  name        = "s3-read-policy"
  description = "Allow read access to specific S3 bucket"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "s3:GetObject",
        "s3:ListBucket"
      ]
      Resource = [
        aws_s3_bucket.data.arn,
        "${aws_s3_bucket.data.arn}/*"
      ]
    }]
  })
}
```

### Resource: aws_iam_instance_profile
```hcl
resource "aws_iam_instance_profile" "app" {
  name = "app-instance-profile"
  role = aws_iam_role.app.name
}
```
"""

# ─────────────────────────────────────────────────────────────────────
# DOCUMENT: AWS KMS — Key Management Service
# ─────────────────────────────────────────────────────────────────────

AWS_KMS_DOCS = """
## AWS KMS — Key Management Service

### Resource: aws_kms_key
```hcl
resource "aws_kms_key" "main" {
  description             = "KMS key for encrypting application data"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      }
    ]
  })

  tags = {
    Name        = "main-kms-key"
    Environment = "production"
    ManagedBy   = "terraform"
  }
}
```

### Resource: aws_kms_alias
```hcl
resource "aws_kms_alias" "main" {
  name          = "alias/main-key"
  target_key_id = aws_kms_key.main.key_id
}
```
"""

# ─────────────────────────────────────────────────────────────────────
# All documents collected for loading
# ─────────────────────────────────────────────────────────────────────

ALL_DOCUMENTS = {
    "aws_vpc_networking": AWS_VPC_DOCS,
    "aws_ec2_compute": AWS_EC2_DOCS,
    "aws_s3_storage": AWS_S3_DOCS,
    "aws_rds_database": AWS_RDS_DOCS,
    "aws_eks_kubernetes": AWS_EKS_DOCS,
    "aws_iam_identity": AWS_IAM_DOCS,
    "aws_kms_encryption": AWS_KMS_DOCS,
}
