package main

import "strings"

type Database interface {
	UpdateItem(key string, data map[string]interface{}) error
	PutItem(key string, data map[string]interface{}) error
	GetItem(key string) (map[string]interface{}, error)
	GetSubItem(key string, columns []string) (map[string]interface{}, error)
	BatchGetItem(keys []string) ([]map[string]interface{}, error)
	BatchGetSubItem(keys []string, columns []string) ([]map[string]interface{}, error)
	BatchPutItem(items map[string]map[string]interface{}) error
	DeleteItem(key string) error
	Close() error
	GetImplName() string
}

func NewDatabase(dbType, region, tableName string) (Database, error) {
	isMultiRow := strings.HasPrefix(tableName, "multirow")
	
	switch dbType {
	case "dynamodb":
		if isMultiRow {
			return NewMultiRowDynamoDB(region, tableName)
		}
		return NewDynamoDB(region, tableName)
	case "redis":
		if isMultiRow {
			return NewMultiRowRedisDB(region, tableName)
		}
		return NewRedisDB(region, tableName)
	default:
		return nil, nil
	}
}
