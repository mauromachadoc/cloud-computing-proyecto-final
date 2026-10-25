"""Intensive - 2-AZ three-tier architecture with one cost-saving NAT Gateway."""
import json
import pulumi
import pulumi_aws as aws

PROJECT = "iacbench-intensive-pulumi"
PONG_URL = "https://codeload.github.com/bocaletto-luca/Pong/tar.gz/58927a56aef0117aa290898d9b48d0f7ee0918b0"
azs = aws.get_availability_zones(state="available").names
account = aws.get_caller_identity().account_id
region = aws.get_region().name
ami = aws.ssm.get_parameter(name="/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64")
vpc = aws.ec2.Vpc("vpc", cidr_block="10.30.0.0/16", enable_dns_support=True,
                 enable_dns_hostnames=True)
igw = aws.ec2.InternetGateway("igw", vpc_id=vpc.id)
public = [aws.ec2.Subnet(f"public-{i}", vpc_id=vpc.id, availability_zone=azs[i],
                         cidr_block=f"10.30.{i+1}.0/24", map_public_ip_on_launch=True)
          for i in range(2)]
app = [aws.ec2.Subnet(f"app-{i}", vpc_id=vpc.id, availability_zone=azs[i],
                      cidr_block=f"10.30.{i+11}.0/24") for i in range(2)]
data = [aws.ec2.Subnet(f"data-{i}", vpc_id=vpc.id, availability_zone=azs[i],
                       cidr_block=f"10.30.{i+21}.0/24") for i in range(2)]
public_rt = aws.ec2.RouteTable("public", vpc_id=vpc.id, routes=[aws.ec2.RouteTableRouteArgs(
    cidr_block="0.0.0.0/0", gateway_id=igw.id)])
public_assocs = [aws.ec2.RouteTableAssociation(f"public-{i}", subnet_id=s.id,
                    route_table_id=public_rt.id) for i, s in enumerate(public)]
eip = aws.ec2.Eip("nat", domain="vpc")
nat = aws.ec2.NatGateway("nat", allocation_id=eip.id, subnet_id=public[0].id,
                         opts=pulumi.ResourceOptions(depends_on=[igw]))
app_rt = aws.ec2.RouteTable("app", vpc_id=vpc.id, routes=[aws.ec2.RouteTableRouteArgs(
    cidr_block="0.0.0.0/0", nat_gateway_id=nat.id)])
app_assocs = [aws.ec2.RouteTableAssociation(f"app-{i}", subnet_id=s.id,
                 route_table_id=app_rt.id) for i, s in enumerate(app)]

def sg(name, description, port, source=None):
    ingress = aws.ec2.SecurityGroupIngressArgs(protocol="tcp", from_port=port, to_port=port,
        security_groups=[source] if source is not None else None,
        cidr_blocks=None if source is not None else ["0.0.0.0/0"])
    return aws.ec2.SecurityGroup(name, name=f"{PROJECT}-{name}", description=description,
        vpc_id=vpc.id, ingress=[ingress], egress=[aws.ec2.SecurityGroupEgressArgs(
            protocol="-1", from_port=0, to_port=0, cidr_blocks=["0.0.0.0/0"])])

alb_sg = sg("alb", "Public HTTP", 80)
app_sg = sg("app", "HTTP from ALB", 80, alb_sg.id)
db_sg = sg("db", "PostgreSQL from app", 5432, app_sg.id)
cache_sg = sg("cache", "Redis from app", 6379, app_sg.id)
alb = aws.lb.LoadBalancer("alb", load_balancer_type="application", internal=False,
    subnets=[s.id for s in public], security_groups=[alb_sg.id],
    opts=pulumi.ResourceOptions(depends_on=public_assocs))
target = aws.lb.TargetGroup("target", port=80, protocol="HTTP", target_type="instance",
    vpc_id=vpc.id, health_check=aws.lb.TargetGroupHealthCheckArgs(path="/", matcher="200"))
listener = aws.lb.Listener("http", load_balancer_arn=alb.arn, port=80, protocol="HTTP",
    default_actions=[aws.lb.ListenerDefaultActionArgs(type="forward", target_group_arn=target.arn)])
role = aws.iam.Role("instance", name=f"{PROJECT}-instance", assume_role_policy=json.dumps({
    "Version":"2012-10-17", "Statement":[{"Effect":"Allow", "Principal":{"Service":"ec2.amazonaws.com"},
    "Action":"sts:AssumeRole"}]}))
aws.iam.RolePolicyAttachment("ssm", role=role.name,
    policy_arn="arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore")
profile = aws.iam.InstanceProfile("instance", name=f"{PROJECT}-instance", role=role.name)
user_data = f"""#!/bin/bash
set -e
dnf install -y nginx
curl -fsSL "{PONG_URL}" | tar -xz -C /usr/share/nginx/html --strip-components=1
systemctl enable --now nginx
"""
import base64
launch = aws.ec2.LaunchTemplate("app", name_prefix=f"{PROJECT}-", image_id=ami.value,
    instance_type="t3.micro", iam_instance_profile=aws.ec2.LaunchTemplateIamInstanceProfileArgs(
        arn=profile.arn), vpc_security_group_ids=[app_sg.id],
    user_data=base64.b64encode(user_data.encode()).decode())
asg = aws.autoscaling.Group("app", name=PROJECT, min_size=2, desired_capacity=2, max_size=4,
    vpc_zone_identifiers=[s.id for s in app], health_check_type="ELB", health_check_grace_period=300,
    target_group_arns=[target.arn], launch_template=aws.autoscaling.GroupLaunchTemplateArgs(
        id=launch.id, version=launch.latest_version.apply(str)),
    opts=pulumi.ResourceOptions(depends_on=[listener, *app_assocs]))
up = aws.autoscaling.Policy("up", name=f"{PROJECT}-up", autoscaling_group_name=asg.name,
    adjustment_type="ChangeInCapacity", scaling_adjustment=1, cooldown=300)
down = aws.autoscaling.Policy("down", name=f"{PROJECT}-down", autoscaling_group_name=asg.name,
    adjustment_type="ChangeInCapacity", scaling_adjustment=-1, cooldown=300)
for name, threshold, op, policy in [("high",70,"GreaterThanThreshold",up),
                                    ("low",20,"LessThanThreshold",down)]:
    aws.cloudwatch.MetricAlarm(name, name=f"{PROJECT}-{name}", namespace="AWS/EC2",
        metric_name="CPUUtilization", statistic="Average", period=300, evaluation_periods=2,
        threshold=threshold, comparison_operator=op, dimensions={"AutoScalingGroupName":asg.name},
        alarm_actions=[policy.arn])
db_group = aws.rds.SubnetGroup("db", name=PROJECT, subnet_ids=[s.id for s in data])
db = aws.rds.Instance("db", identifier=PROJECT, engine="postgres", engine_version="16",
    instance_class="db.t3.micro", allocated_storage=20, storage_type="gp3", storage_encrypted=True,
    username="iacbench", manage_master_user_password=True, multi_az=True,
    publicly_accessible=False, deletion_protection=False, backup_retention_period=1,
    skip_final_snapshot=True, db_subnet_group_name=db_group.name,
    vpc_security_group_ids=[db_sg.id])
cache_group = aws.elasticache.SubnetGroup("cache", name=PROJECT, subnet_ids=[s.id for s in data])
redis = aws.elasticache.ReplicationGroup("redis", replication_group_id=PROJECT,
    description="iacbench two-node redis", engine="redis", engine_version="7.0",
    node_type="cache.t3.micro", num_cache_clusters=2, automatic_failover_enabled=True,
    multi_az_enabled=True, subnet_group_name=cache_group.name,
    security_group_ids=[cache_sg.id])
bucket = aws.s3.BucketV2("assets", bucket=f"{PROJECT}-{account}-{region}", force_destroy=True)
aws.s3.BucketVersioningV2("assets", bucket=bucket.id,
    versioning_configuration=aws.s3.BucketVersioningV2VersioningConfigurationArgs(status="Enabled"))
aws.s3.BucketServerSideEncryptionConfigurationV2("assets", bucket=bucket.id, rules=[
    aws.s3.BucketServerSideEncryptionConfigurationV2RuleArgs(
        apply_server_side_encryption_by_default=aws.s3.BucketServerSideEncryptionConfigurationV2RuleApplyServerSideEncryptionByDefaultArgs(
            sse_algorithm="AES256"))])
aws.s3.BucketPublicAccessBlock("assets", bucket=bucket.id, block_public_acls=True,
    block_public_policy=True, ignore_public_acls=True, restrict_public_buckets=True)
cdn = aws.cloudfront.Distribution("cdn", enabled=True, price_class="PriceClass_100",
    comment="Pong via ALB; S3 is private independent asset storage",
    origins=[aws.cloudfront.DistributionOriginArgs(domain_name=alb.dns_name, origin_id="app-alb",
        custom_origin_config=aws.cloudfront.DistributionOriginCustomOriginConfigArgs(
            http_port=80, https_port=443, origin_protocol_policy="http-only", origin_ssl_protocols=["TLSv1.2"]))],
    default_cache_behavior=aws.cloudfront.DistributionDefaultCacheBehaviorArgs(
        target_origin_id="app-alb", viewer_protocol_policy="redirect-to-https",
        allowed_methods=["GET", "HEAD"], cached_methods=["GET", "HEAD"],
        forwarded_values=aws.cloudfront.DistributionDefaultCacheBehaviorForwardedValuesArgs(
            query_string=False, cookies=aws.cloudfront.DistributionDefaultCacheBehaviorForwardedValuesCookiesArgs(
                forward="none")), min_ttl=0, default_ttl=0, max_ttl=0),
    restrictions=aws.cloudfront.DistributionRestrictionsArgs(
        geo_restriction=aws.cloudfront.DistributionRestrictionsGeoRestrictionArgs(restriction_type="none")),
    viewer_certificate=aws.cloudfront.DistributionViewerCertificateArgs(cloudfront_default_certificate=True))
pulumi.export("site_url", cdn.domain_name.apply(lambda x: f"https://{x}"))
pulumi.export("alb_url", alb.dns_name.apply(lambda x: f"http://{x}"))
pulumi.export("bucket_name", bucket.id)
pulumi.export("database_endpoint", db.address)
pulumi.export("redis_endpoint", redis.primary_endpoint_address)
