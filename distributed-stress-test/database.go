package main

type Database interface {
	UpdateItem(key string, data map[string]interface{}) error
	Query(key string) error
	PutItem(key string, data map[string]interface{}) error
	GetItem(key string) (map[string]interface{}, error)
	BatchGetItem(keys []string) ([]map[string]interface{}, error)
	BatchPutItem(items map[string]map[string]interface{}) error
	DeleteItem(key string) error
	Close() error
}

func NewDatabase(dbType, region, tableName string) (Database, error) {
	switch dbType {
	case "dynamodb":
		return NewDynamoDB(region, tableName)
	case "redis":
		return NewRedisDB(region, tableName)
	default:
		return nil, nil
	}
}
