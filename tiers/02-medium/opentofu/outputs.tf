output "site_url" { value = "http://${aws_lb.main.dns_name}" }
output "database_endpoint" { value = aws_db_instance.db.address }
