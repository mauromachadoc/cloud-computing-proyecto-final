output "site_url" { value = "https://${aws_cloudfront_distribution.cdn.domain_name}" }
output "alb_url" { value = "http://${aws_lb.main.dns_name}" }
output "bucket_name" { value = aws_s3_bucket.assets.id }
output "database_endpoint" { value = aws_db_instance.db.address }
output "redis_endpoint" { value = aws_elasticache_replication_group.redis.primary_endpoint_address }
