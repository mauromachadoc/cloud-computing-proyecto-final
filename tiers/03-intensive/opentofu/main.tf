data "aws_availability_zones" "available" { state = "available" }
data "aws_caller_identity" "current" {}
data "aws_ssm_parameter" "al2023" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}
resource "aws_vpc" "main" {
  cidr_block = "10.30.0.0/16"
  enable_dns_support = true
  enable_dns_hostnames = true
}
resource "aws_internet_gateway" "main" { vpc_id = aws_vpc.main.id }
resource "aws_subnet" "public" {
  count = 2
  vpc_id = aws_vpc.main.id
  availability_zone = data.aws_availability_zones.available.names[count.index]
  cidr_block = cidrsubnet("10.30.0.0/16", 8, count.index + 1)
  map_public_ip_on_launch = true
}
resource "aws_subnet" "app" {
  count = 2
  vpc_id = aws_vpc.main.id
  availability_zone = data.aws_availability_zones.available.names[count.index]
  cidr_block = cidrsubnet("10.30.0.0/16", 8, count.index + 11)
}
resource "aws_subnet" "data" {
  count = 2
  vpc_id = aws_vpc.main.id
  availability_zone = data.aws_availability_zones.available.names[count.index]
  cidr_block = cidrsubnet("10.30.0.0/16", 8, count.index + 21)
}
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }
}
resource "aws_route_table_association" "public" {
  count = 2
  subnet_id = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}
resource "aws_eip" "nat" { domain = "vpc" }
resource "aws_nat_gateway" "nat" {
  allocation_id = aws_eip.nat.id
  subnet_id = aws_subnet.public[0].id
  depends_on = [aws_internet_gateway.main]
}
resource "aws_route_table" "app" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.nat.id
  }
}
resource "aws_route_table_association" "app" {
  count = 2
  subnet_id = aws_subnet.app[count.index].id
  route_table_id = aws_route_table.app.id
}
resource "aws_security_group" "alb" {
  name = "${var.project_name}-alb"
  description = "Public HTTP"
  vpc_id = aws_vpc.main.id
  ingress {
    protocol = "tcp"
    from_port = 80
    to_port = 80
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    protocol = "-1"
    from_port = 0
    to_port = 0
    cidr_blocks = ["0.0.0.0/0"]
  }
}
resource "aws_security_group" "app" {
  name = "${var.project_name}-app"
  description = "HTTP only from ALB"
  vpc_id = aws_vpc.main.id
  ingress {
    protocol = "tcp"
    from_port = 80
    to_port = 80
    security_groups = [aws_security_group.alb.id]
  }
  egress {
    protocol = "-1"
    from_port = 0
    to_port = 0
    cidr_blocks = ["0.0.0.0/0"]
  }
}
resource "aws_security_group" "db" {
  name = "${var.project_name}-db"
  description = "Postgres only from app"
  vpc_id = aws_vpc.main.id
  ingress {
    protocol = "tcp"
    from_port = 5432
    to_port = 5432
    security_groups = [aws_security_group.app.id]
  }
  egress {
    protocol = "-1"
    from_port = 0
    to_port = 0
    cidr_blocks = ["0.0.0.0/0"]
  }
}
resource "aws_security_group" "redis" {
  name = "${var.project_name}-cache"
  description = "Redis only from app"
  vpc_id = aws_vpc.main.id
  ingress {
    protocol = "tcp"
    from_port = 6379
    to_port = 6379
    security_groups = [aws_security_group.app.id]
  }
  egress {
    protocol = "-1"
    from_port = 0
    to_port = 0
    cidr_blocks = ["0.0.0.0/0"]
  }
}
resource "aws_lb" "main" {
  load_balancer_type = "application"
  internal = false
  security_groups = [aws_security_group.alb.id]
  subnets = aws_subnet.public[*].id
  depends_on = [aws_route_table_association.public]
}
resource "aws_lb_target_group" "main" {
  port = 80
  protocol = "HTTP"
  vpc_id = aws_vpc.main.id
  target_type = "instance"
  health_check {
    path = "/"
    matcher = "200"
  }
}
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port = 80
  protocol = "HTTP"
  default_action {
    type = "forward"
    target_group_arn = aws_lb_target_group.main.arn
  }
}
resource "aws_iam_role" "instance" {
  name = "${var.project_name}-instance"
  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{ Effect = "Allow", Action = "sts:AssumeRole", Principal = { Service = "ec2.amazonaws.com" } }]
  })
}
resource "aws_iam_role_policy_attachment" "ssm" {
  role = aws_iam_role.instance.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}
resource "aws_iam_instance_profile" "instance" {
  name = "${var.project_name}-instance"
  role = aws_iam_role.instance.name
}
resource "aws_launch_template" "app" {
  name_prefix = "${var.project_name}-"
  image_id = data.aws_ssm_parameter.al2023.value
  instance_type = "t3.micro"
  iam_instance_profile { arn = aws_iam_instance_profile.instance.arn }
  vpc_security_group_ids = [aws_security_group.app.id]
  user_data = base64encode(<<-EOT
    #!/bin/bash
    set -e
    dnf install -y nginx
    curl -fsSL "${var.pong_url}" | tar -xz -C /usr/share/nginx/html --strip-components=1
    systemctl enable --now nginx
  EOT
  )
}
resource "aws_autoscaling_group" "app" {
  name = var.project_name
  min_size = 2
  desired_capacity = 2
  max_size = 4
  vpc_zone_identifier = aws_subnet.app[*].id
  health_check_type = "ELB"
  health_check_grace_period = 300
  target_group_arns = [aws_lb_target_group.main.arn]
  launch_template {
    id = aws_launch_template.app.id
    version = aws_launch_template.app.latest_version
  }
  depends_on = [aws_lb_listener.http, aws_route_table_association.app]
}
resource "aws_autoscaling_policy" "up" {
  name = "${var.project_name}-up"
  autoscaling_group_name = aws_autoscaling_group.app.name
  adjustment_type = "ChangeInCapacity"
  scaling_adjustment = 1
  cooldown = 300
}
resource "aws_autoscaling_policy" "down" {
  name = "${var.project_name}-down"
  autoscaling_group_name = aws_autoscaling_group.app.name
  adjustment_type = "ChangeInCapacity"
  scaling_adjustment = -1
  cooldown = 300
}
resource "aws_cloudwatch_metric_alarm" "high" {
  alarm_name = "${var.project_name}-high"
  namespace = "AWS/EC2"
  metric_name = "CPUUtilization"
  statistic = "Average"
  period = 300
  evaluation_periods = 2
  threshold = 70
  comparison_operator = "GreaterThanThreshold"
  dimensions = { AutoScalingGroupName = aws_autoscaling_group.app.name }
  alarm_actions = [aws_autoscaling_policy.up.arn]
}
resource "aws_cloudwatch_metric_alarm" "low" {
  alarm_name = "${var.project_name}-low"
  namespace = "AWS/EC2"
  metric_name = "CPUUtilization"
  statistic = "Average"
  period = 300
  evaluation_periods = 2
  threshold = 20
  comparison_operator = "LessThanThreshold"
  dimensions = { AutoScalingGroupName = aws_autoscaling_group.app.name }
  alarm_actions = [aws_autoscaling_policy.down.arn]
}
resource "aws_db_subnet_group" "main" {
  name = var.project_name
  subnet_ids = aws_subnet.data[*].id
}
resource "aws_db_instance" "db" {
  identifier = var.project_name
  engine = "postgres"
  engine_version = "16"
  instance_class = "db.t3.micro"
  allocated_storage = 20
  storage_type = "gp3"
  storage_encrypted = true
  username = "iacbench"
  manage_master_user_password = true
  multi_az = true
  publicly_accessible = false
  deletion_protection = false
  backup_retention_period = 1
  skip_final_snapshot = true
  db_subnet_group_name = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.db.id]
}
resource "aws_elasticache_subnet_group" "main" {
  name = var.project_name
  subnet_ids = aws_subnet.data[*].id
}
resource "aws_elasticache_replication_group" "redis" {
  replication_group_id = var.project_name
  description = "iacbench two-node redis"
  engine = "redis"
  engine_version = "7.0"
  node_type = "cache.t3.micro"
  num_cache_clusters = 2
  automatic_failover_enabled = true
  multi_az_enabled = true
  subnet_group_name = aws_elasticache_subnet_group.main.name
  security_group_ids = [aws_security_group.redis.id]
}
resource "aws_s3_bucket" "assets" {
  bucket = "${var.project_name}-${data.aws_caller_identity.current.account_id}-${var.region}"
  force_destroy = true
}
resource "aws_s3_bucket_versioning" "assets" {
  bucket = aws_s3_bucket.assets.id
  versioning_configuration { status = "Enabled" }
}
resource "aws_s3_bucket_server_side_encryption_configuration" "assets" {
  bucket = aws_s3_bucket.assets.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}
resource "aws_s3_bucket_public_access_block" "assets" {
  bucket = aws_s3_bucket.assets.id
  block_public_acls = true
  block_public_policy = true
  ignore_public_acls = true
  restrict_public_buckets = true
}
resource "aws_cloudfront_distribution" "cdn" {
  enabled = true
  comment = "Pong via ALB; S3 bucket is private independent asset storage"
  price_class = "PriceClass_100"
  origin {
    domain_name = aws_lb.main.dns_name
    origin_id = "app-alb"
    custom_origin_config {
      http_port = 80
      https_port = 443
      origin_protocol_policy = "http-only"
      origin_ssl_protocols = ["TLSv1.2"]
    }
  }
  default_cache_behavior {
    allowed_methods = ["GET", "HEAD"]
    cached_methods = ["GET", "HEAD"]
    target_origin_id = "app-alb"
    viewer_protocol_policy = "redirect-to-https"
    min_ttl = 0
    default_ttl = 0
    max_ttl = 0
    forwarded_values {
      query_string = false
      cookies { forward = "none" }
    }
  }
  restrictions { geo_restriction { restriction_type = "none" } }
  viewer_certificate { cloudfront_default_certificate = true }
}
