"""Intentional failure after the bucket is created; never use for production."""
import json
import pulumi
import pulumi_aws as aws
account = aws.get_caller_identity().account_id
region = aws.get_region().name
bucket = aws.s3.BucketV2("valid", bucket=f"iacbench-fail-pulumi-{account}-{region}",
                         force_destroy=True)
aws.s3.BucketPolicy("broken", bucket=bucket.id, policy=json.dumps({
    "Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Principal": "*",
    "Action": "s3:GetObject", "Resource": "arn:aws:s3:::iacbench-deliberately-wrong-resource/*"}]
}))
