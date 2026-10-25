"""Consumer of a reusable Pulumi component."""
import pulumi
import pulumi_aws as aws
from component import PrivateBucket
account = aws.get_caller_identity().account_id
region = aws.get_region().name
bucket = PrivateBucket("assets", f"iacbench-module-pulumi-{account}-{region}")
pulumi.export("bucket_name", bucket.name)
