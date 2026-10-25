"""iacbench - Simple tier (VPC + EC2 + S3) - Pulumi (Python)."""
import pulumi
import pulumi_aws as aws

PROJECT = "iacbench-simple-pulumi"
INSTANCE_TYPE = "t3.micro"
# Pinned commit of bocaletto-luca/Pong (GPL-3.0)
PONG_URL = "https://codeload.github.com/bocaletto-luca/Pong/tar.gz/58927a56aef0117aa290898d9b48d0f7ee0918b0"

azs = aws.get_availability_zones(state="available")
account = aws.get_caller_identity()
region = aws.get_region()
ami = aws.ssm.get_parameter(name="/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64")

vpc = aws.ec2.Vpc(
    "vpc",
    cidr_block="10.10.0.0/16",
    enable_dns_support=True,
    enable_dns_hostnames=True,
    tags={"Name": f"{PROJECT}-vpc"},
)

igw = aws.ec2.InternetGateway("igw", vpc_id=vpc.id, tags={"Name": f"{PROJECT}-igw"})

subnet = aws.ec2.Subnet(
    "public",
    vpc_id=vpc.id,
    cidr_block="10.10.1.0/24",
    availability_zone=azs.names[0],
    map_public_ip_on_launch=True,
    tags={"Name": f"{PROJECT}-public"},
)

route_table = aws.ec2.RouteTable(
    "public",
    vpc_id=vpc.id,
    routes=[aws.ec2.RouteTableRouteArgs(cidr_block="0.0.0.0/0", gateway_id=igw.id)],
    tags={"Name": f"{PROJECT}-public"},
)

association = aws.ec2.RouteTableAssociation(
    "public", subnet_id=subnet.id, route_table_id=route_table.id
)

web_sg = aws.ec2.SecurityGroup(
    "web",
    name=f"{PROJECT}-web",
    description="HTTP in, all out",
    vpc_id=vpc.id,
    ingress=[
        aws.ec2.SecurityGroupIngressArgs(
            protocol="tcp", from_port=80, to_port=80, cidr_blocks=["0.0.0.0/0"]
        )
    ],
    egress=[
        aws.ec2.SecurityGroupEgressArgs(
            protocol="-1", from_port=0, to_port=0, cidr_blocks=["0.0.0.0/0"]
        )
    ],
    tags={"Name": f"{PROJECT}-web"},
)

USER_DATA = f"""#!/bin/bash
dnf install -y nginx
curl -fsSL "{PONG_URL}" | tar -xz -C /usr/share/nginx/html --strip-components=1
systemctl enable --now nginx
"""

web = aws.ec2.Instance(
    "web",
    ami=ami.value,
    instance_type=INSTANCE_TYPE,
    subnet_id=subnet.id,
    vpc_security_group_ids=[web_sg.id],
    user_data=USER_DATA,
    user_data_replace_on_change=True,
    tags={"Name": f"{PROJECT}-web"},
    opts=pulumi.ResourceOptions(depends_on=[association]),
)

bucket = aws.s3.BucketV2(
    "assets",
    bucket=f"{PROJECT}-{account.account_id}-{region.name}",
    force_destroy=True,
)

aws.s3.BucketVersioningV2(
    "assets",
    bucket=bucket.id,
    versioning_configuration=aws.s3.BucketVersioningV2VersioningConfigurationArgs(status="Enabled"),
)

aws.s3.BucketServerSideEncryptionConfigurationV2(
    "assets",
    bucket=bucket.id,
    rules=[
        aws.s3.BucketServerSideEncryptionConfigurationV2RuleArgs(
            apply_server_side_encryption_by_default=aws.s3.BucketServerSideEncryptionConfigurationV2RuleApplyServerSideEncryptionByDefaultArgs(
                sse_algorithm="AES256"
            )
        )
    ],
)

aws.s3.BucketPublicAccessBlock(
    "assets",
    bucket=bucket.id,
    block_public_acls=True,
    block_public_policy=True,
    ignore_public_acls=True,
    restrict_public_buckets=True,
)

pulumi.export("site_url", web.public_ip.apply(lambda ip: f"http://{ip}"))
pulumi.export("bucket_name", bucket.id)
