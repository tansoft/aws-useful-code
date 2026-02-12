go run test_handler.go ddb_handler.go -table stress-test-multicolumn10 -writeAll 10 -times 10 -printkey

go run test_handler.go ddb_handler.go -table stress-test-multirow10 -sortkey -writeAll 10 -times 10 -printkey

go run test_handler.go ddb_handler.go -table stress-test-multicolumn10 -readAll 10 -times 10 -printkey

go run test_handler.go ddb_handler.go -table stress-test-multirow10 -sortkey -readAll 10 -times 10 -printkey
