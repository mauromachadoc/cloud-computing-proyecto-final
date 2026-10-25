output "site_url" {
  value = "http://${aws_instance.web.public_ip}"
}

output "bucket_name" {
  value = aws_s3_bucket.assets.id
}
