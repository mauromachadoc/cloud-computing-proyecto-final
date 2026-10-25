data "aws_availability_zones" "available" { state = "available" }
resource "aws_vpc" "main" {
  cidr_block = "10.20.0.0/16"
  enable_dns_support = true
  enable_dns_hostnames = true
  tags = { Name = "${var.project_name}-vpc" }
}
resource "aws_internet_gateway" "main" { vpc_id = aws_vpc.main.id }
resource "aws_subnet" "public" {
  count = 2
  vpc_id = aws_vpc.main.id
  availability_zone = data.aws_availability_zones.available.names[count.index]
  cidr_block = cidrsubnet("10.20.0.0/16", 8, count.index + 1)
  map_public_ip_on_launch = true
}
resource "aws_subnet" "db" {
  count = 2
  vpc_id = aws_vpc.main.id
  availability_zone = data.aws_availability_zones.available.names[count.index]
  cidr_block = cidrsubnet("10.20.0.0/16", 8, count.index + 11)
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
resource "aws_security_group" "task" {
  name = "${var.project_name}-task"
  description = "HTTP from ALB"
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
  description = "PostgreSQL from ECS"
  vpc_id = aws_vpc.main.id
  ingress {
    protocol = "tcp"
    from_port = 5432
    to_port = 5432
    security_groups = [aws_security_group.task.id]
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
  target_type = "ip"
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
resource "aws_ecs_cluster" "main" { name = var.project_name }
resource "aws_iam_role" "execution" {
  name = "${var.project_name}-execution"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{Effect = "Allow", Principal = {Service = "ecs-tasks.amazonaws.com"}, Action = "sts:AssumeRole"}]
  })
}
resource "aws_iam_role_policy_attachment" "execution" {
  role = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}
resource "aws_ecs_task_definition" "pong" {
  family = var.project_name
  requires_compatibilities = ["FARGATE"]
  network_mode = "awsvpc"
  cpu = "256"
  memory = "512"
  execution_role_arn = aws_iam_role.execution.arn
  container_definitions = jsonencode([{
    name = "pong"
    image = "nginx:stable-alpine"
    essential = true
    portMappings = [{containerPort = 80, protocol = "tcp"}]
    entryPoint = ["/bin/sh", "-c"]
    command = ["wget -qO- '${var.pong_url}' | tar -xz -C /usr/share/nginx/html --strip-components=1 && exec nginx -g 'daemon off;'"]
  }])
}
resource "aws_ecs_service" "main" {
  name = var.project_name
  cluster = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.pong.arn
  desired_count = 1
  launch_type = "FARGATE"
  wait_for_steady_state = true
  deployment_minimum_healthy_percent = 0
  deployment_maximum_percent = 200
  network_configuration {
    subnets = aws_subnet.public[*].id
    security_groups = [aws_security_group.task.id]
    assign_public_ip = true
  }
  load_balancer {
    target_group_arn = aws_lb_target_group.main.arn
    container_name = "pong"
    container_port = 80
  }
  depends_on = [aws_lb_listener.http, aws_iam_role_policy_attachment.execution]
}
resource "aws_db_subnet_group" "db" {
  name = var.project_name
  subnet_ids = aws_subnet.db[*].id
}
resource "aws_db_instance" "db" {
  identifier = var.project_name
  engine = "postgres"
  engine_version = "16.15"
  instance_class = "db.t3.micro"
  allocated_storage = 20
  storage_type = "gp3"
  storage_encrypted = true
  username = "iacbench"
  manage_master_user_password = true
  multi_az = false
  publicly_accessible = false
  deletion_protection = false
  backup_retention_period = 0
  skip_final_snapshot = true
  db_subnet_group_name = aws_db_subnet_group.db.name
  vpc_security_group_ids = [aws_security_group.db.id]
}
