go mod tidy
go build -o task_publisher task_publisher.go
go build -o worker worker.go database.go dynamodb_impl.go redis_impl.go multirow_dynamodb_impl.go multirow_redis_impl.go
