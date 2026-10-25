"""Medium - ALB + ECS Fargate + single-AZ RDS, matching the HCL/CFN topology."""
import pulumi
import pulumi_aws as aws

PROJECT = "iacbench-medium-pulumi"
PONG_URL = "https://codeload.github.com/bocaletto-luca/Pong/tar.gz/58927a56aef0117aa290898d9b48d0f7ee0918b0"
azs = aws.get_availability_zones(state="available").names
vpc = aws.ec2.Vpc("vpc", cidr_block="10.20.0.0/16", enable_dns_support=True,
                 enable_dns_hostnames=True, tags={"Name": f"{PROJECT}-vpc"})
igw = aws.ec2.InternetGateway("igw", vpc_id=vpc.id)
public = [aws.ec2.Subnet(f"public-{i}", vpc_id=vpc.id, availability_zone=azs[i],
                         cidr_block=f"10.20.{i+1}.0/24", map_public_ip_on_launch=True)
          for i in range(2)]
db_subnets = [aws.ec2.Subnet(f"db-{i}", vpc_id=vpc.id,
                             availability_zone=azs[i], cidr_block=f"10.20.{i+11}.0/24")
              for i in range(2)]
rt = aws.ec2.RouteTable("public", vpc_id=vpc.id, routes=[aws.ec2.RouteTableRouteArgs(
    cidr_block="0.0.0.0/0", gateway_id=igw.id)])
associations = [aws.ec2.RouteTableAssociation(f"public-{i}", subnet_id=s.id,
                                               route_table_id=rt.id)
                for i, s in enumerate(public)]
alb_sg = aws.ec2.SecurityGroup("alb", name=f"{PROJECT}-alb", description="Public HTTP", vpc_id=vpc.id,
    ingress=[aws.ec2.SecurityGroupIngressArgs(protocol="tcp", from_port=80, to_port=80,
                                               cidr_blocks=["0.0.0.0/0"])],
    egress=[aws.ec2.SecurityGroupEgressArgs(protocol="-1", from_port=0, to_port=0,
                                             cidr_blocks=["0.0.0.0/0"])])
task_sg = aws.ec2.SecurityGroup("task", name=f"{PROJECT}-task", description="HTTP from ALB", vpc_id=vpc.id,
    ingress=[aws.ec2.SecurityGroupIngressArgs(protocol="tcp", from_port=80, to_port=80,
                                               security_groups=[alb_sg.id])],
    egress=[aws.ec2.SecurityGroupEgressArgs(protocol="-1", from_port=0, to_port=0,
                                             cidr_blocks=["0.0.0.0/0"])])
db_sg = aws.ec2.SecurityGroup("db", name=f"{PROJECT}-db", description="Postgres from ECS", vpc_id=vpc.id,
    ingress=[aws.ec2.SecurityGroupIngressArgs(protocol="tcp", from_port=5432, to_port=5432,
                                               security_groups=[task_sg.id])],
    egress=[aws.ec2.SecurityGroupEgressArgs(protocol="-1", from_port=0, to_port=0,
                                             cidr_blocks=["0.0.0.0/0"])])
alb = aws.lb.LoadBalancer("alb", internal=False, load_balancer_type="application",
                          security_groups=[alb_sg.id], subnets=[s.id for s in public],
                          opts=pulumi.ResourceOptions(depends_on=associations))
target = aws.lb.TargetGroup("target", port=80, protocol="HTTP", vpc_id=vpc.id,
                            target_type="ip", health_check=aws.lb.TargetGroupHealthCheckArgs(path="/", matcher="200"))
listener = aws.lb.Listener("http", load_balancer_arn=alb.arn, port=80, protocol="HTTP",
    default_actions=[aws.lb.ListenerDefaultActionArgs(type="forward", target_group_arn=target.arn)])
cluster = aws.ecs.Cluster("cluster", name=PROJECT)
role = aws.iam.Role("execution", name=f"{PROJECT}-execution", assume_role_policy='''{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ecs-tasks.amazonaws.com"},"Action":"sts:AssumeRole"}]}''')
attachment = aws.iam.RolePolicyAttachment("execution", role=role.name,
    policy_arn="arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy")
import json
container = json.dumps([{"name": "pong", "image": "nginx:stable-alpine", "essential": True,
    "portMappings": [{"containerPort": 80, "protocol": "tcp"}],
    "entryPoint": ["/bin/sh", "-c"],
    "command": [f"wget -qO- '{PONG_URL}' | tar -xz -C /usr/share/nginx/html --strip-components=1 && exec nginx -g 'daemon off;'"]}])
task = aws.ecs.TaskDefinition("pong", family=PROJECT, network_mode="awsvpc",
    requires_compatibilities=["FARGATE"], cpu="256", memory="512",
    execution_role_arn=role.arn, container_definitions=container)
service = aws.ecs.Service("service", name=PROJECT, cluster=cluster.arn, task_definition=task.arn,
    desired_count=1, launch_type="FARGATE", wait_for_steady_state=True, deployment_minimum_healthy_percent=0,
    deployment_maximum_percent=200, network_configuration=aws.ecs.ServiceNetworkConfigurationArgs(
        subnets=[s.id for s in public], security_groups=[task_sg.id], assign_public_ip=True),
    load_balancers=[aws.ecs.ServiceLoadBalancerArgs(target_group_arn=target.arn,
                                                  container_name="pong", container_port=80)],
    opts=pulumi.ResourceOptions(depends_on=[listener, attachment]))
db_group = aws.rds.SubnetGroup("db", name=PROJECT, subnet_ids=[s.id for s in db_subnets])
db = aws.rds.Instance("db", identifier=PROJECT, engine="postgres", engine_version="16.15",
    instance_class="db.t3.micro", allocated_storage=20, storage_type="gp3", storage_encrypted=True,
    username="iacbench", manage_master_user_password=True, multi_az=False,
    publicly_accessible=False, deletion_protection=False, backup_retention_period=0,
    skip_final_snapshot=True, db_subnet_group_name=db_group.name,
    vpc_security_group_ids=[db_sg.id])
pulumi.export("site_url", alb.dns_name.apply(lambda x: f"http://{x}"))
pulumi.export("database_endpoint", db.address)
