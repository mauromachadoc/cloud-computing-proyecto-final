"""Reusable S3 component hiding internal AWS resources behind one interface."""
import pulumi
import pulumi_aws as aws

class PrivateBucket(pulumi.ComponentResource):
    def __init__(self, name: str, bucket_name: str, opts=None):
        super().__init__("iacbench:components:PrivateBucket", name, None, opts)
        child_opts = pulumi.ResourceOptions(parent=self)
        bucket = aws.s3.BucketV2(f"{name}-bucket", bucket=bucket_name,
                                 force_destroy=True, opts=child_opts)
        aws.s3.BucketServerSideEncryptionConfigurationV2(f"{name}-encryption", bucket=bucket.id,
            rules=[aws.s3.BucketServerSideEncryptionConfigurationV2RuleArgs(
                apply_server_side_encryption_by_default=aws.s3.BucketServerSideEncryptionConfigurationV2RuleApplyServerSideEncryptionByDefaultArgs(
                    sse_algorithm="AES256"))], opts=child_opts)
        aws.s3.BucketPublicAccessBlock(f"{name}-access", bucket=bucket.id,
            block_public_acls=True, block_public_policy=True,
            ignore_public_acls=True, restrict_public_buckets=True, opts=child_opts)
        self.name = bucket.id
        self.register_outputs({"name": self.name})
