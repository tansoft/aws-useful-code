package main

import (
	"fmt"
	"math/rand"
	"net"
	"net/http"
	"time"

	"github.com/aws/aws-sdk-go/aws"
	"github.com/aws/aws-sdk-go/aws/session"
	"github.com/aws/aws-sdk-go/service/dynamodb"
)

type MultiRowDynamoDBImpl struct {
	client    *dynamodb.DynamoDB
	tableName string
	dataCache map[int][]byte
}

func NewMultiRowDynamoDB(region, tableName string) (*MultiRowDynamoDBImpl, error) {
	httpClient := &http.Client{
		Transport: &http.Transport{
			MaxIdleConns:        10000,
			MaxIdleConnsPerHost: 10000,
			MaxConnsPerHost:     10000,
			IdleConnTimeout:     90 * time.Second,
			DialContext: (&net.Dialer{
				Timeout:   10 * time.Second,
				KeepAlive: 30 * time.Second,
			}).DialContext,
			DisableKeepAlives:  false,
			DisableCompression: true,
			ForceAttemptHTTP2:  false,
		},
		Timeout: 30 * time.Second,
	}

	sess, err := session.NewSession(&aws.Config{
		Region:     aws.String(region),
		HTTPClient: httpClient,
		MaxRetries: aws.Int(2),
	})
	if err != nil {
		return nil, err
	}

	dataCache := make(map[int][]byte)
	for _, size := range []int{100, 1000, 8000, 10000, 50000, 100000} {
		data := make([]byte, size)
		rand.Read(data)
		dataCache[size] = data
	}

	return &MultiRowDynamoDBImpl{
		client:    dynamodb.New(sess),
		tableName: tableName,
		dataCache: dataCache,
	}, nil
}

func (d *MultiRowDynamoDBImpl) PutItem(key string, data map[string]interface{}) error {
	for col, v := range data {
		item := map[string]*dynamodb.AttributeValue{
			"id":    {S: aws.String(key)},
			"sk":    {S: aws.String(col)},
			"value": d.toAttributeValue(v),
		}
		if _, err := d.client.PutItem(&dynamodb.PutItemInput{
			TableName: aws.String(d.tableName),
			Item:      item,
		}); err != nil {
			return err
		}
	}
	return nil
}

func (d *MultiRowDynamoDBImpl) UpdateItem(key string, data map[string]interface{}) error {
	for col, v := range data {
		_, err := d.client.UpdateItem(&dynamodb.UpdateItemInput{
			TableName: aws.String(d.tableName),
			Key: map[string]*dynamodb.AttributeValue{
				"id": {S: aws.String(key)},
				"sk": {S: aws.String(col)},
			},
			UpdateExpression: aws.String("SET #v = :val"),
			ExpressionAttributeNames: map[string]*string{
				"#v": aws.String("value"),
			},
			ExpressionAttributeValues: map[string]*dynamodb.AttributeValue{
				":val": d.toAttributeValue(v),
			},
		})
		if err != nil {
			return err
		}
	}
	return nil
}

func (d *MultiRowDynamoDBImpl) GetItem(key string) (map[string]interface{}, error) {
	result, err := d.client.Query(&dynamodb.QueryInput{
		TableName:              aws.String(d.tableName),
		KeyConditionExpression: aws.String("id = :key"),
		ExpressionAttributeValues: map[string]*dynamodb.AttributeValue{
			":key": {S: aws.String(key)},
		},
	})
	if err != nil {
		return nil, err
	}

	data := make(map[string]interface{})
	for _, item := range result.Items {
		if sk := item["sk"]; sk != nil && sk.S != nil {
			data[*sk.S] = d.fromAttributeValue(item["value"])
		}
	}
	return data, nil
}

func (d *MultiRowDynamoDBImpl) GetSubItem(key string, columns []string) (map[string]interface{}, error) {
	data := make(map[string]interface{})
	for _, col := range columns {
		result, err := d.client.GetItem(&dynamodb.GetItemInput{
			TableName: aws.String(d.tableName),
			Key: map[string]*dynamodb.AttributeValue{
				"id": {S: aws.String(key)},
				"sk": {S: aws.String(col)},
			},
		})
		if err != nil {
			return nil, err
		}
		if result.Item != nil {
			data[col] = d.fromAttributeValue(result.Item["value"])
		}
	}
	return data, nil
}

func (d *MultiRowDynamoDBImpl) BatchGetItem(keys []string) ([]map[string]interface{}, error) {
	results := make([]map[string]interface{}, 0, len(keys))
	for _, key := range keys {
		item, err := d.GetItem(key)
		if err != nil {
			return nil, err
		}
		results = append(results, item)
	}
	return results, nil
}

func (d *MultiRowDynamoDBImpl) BatchPutItem(items map[string]map[string]interface{}) error {
	for key, data := range items {
		if err := d.PutItem(key, data); err != nil {
			return err
		}
	}
	return nil
}

func (d *MultiRowDynamoDBImpl) DeleteItem(key string) error {
	result, err := d.client.Query(&dynamodb.QueryInput{
		TableName:              aws.String(d.tableName),
		KeyConditionExpression: aws.String("id = :key"),
		ExpressionAttributeValues: map[string]*dynamodb.AttributeValue{
			":key": {S: aws.String(key)},
		},
	})
	if err != nil {
		return err
	}

	for _, item := range result.Items {
		_, err := d.client.DeleteItem(&dynamodb.DeleteItemInput{
			TableName: aws.String(d.tableName),
			Key: map[string]*dynamodb.AttributeValue{
				"id": item["id"],
				"sk": item["sk"],
			},
		})
		if err != nil {
			return err
		}
	}
	return nil
}

func (d *MultiRowDynamoDBImpl) Query(key string) error {
	_, err := d.client.Query(&dynamodb.QueryInput{
		TableName:              aws.String(d.tableName),
		KeyConditionExpression: aws.String("id = :key"),
		ExpressionAttributeValues: map[string]*dynamodb.AttributeValue{
			":key": {S: aws.String(key)},
		},
	})
	return err
}

func (d *MultiRowDynamoDBImpl) toAttributeValue(v interface{}) *dynamodb.AttributeValue {
	switch val := v.(type) {
	case string:
		return &dynamodb.AttributeValue{S: aws.String(val)}
	case float64:
		size := int(val)
		if cached, ok := d.dataCache[size]; ok {
			return &dynamodb.AttributeValue{B: cached}
		}
		data := make([]byte, size)
		rand.Read(data)
		return &dynamodb.AttributeValue{B: data}
	default:
		return &dynamodb.AttributeValue{S: aws.String(fmt.Sprintf("%v", val))}
	}
}

func (d *MultiRowDynamoDBImpl) fromAttributeValue(attr *dynamodb.AttributeValue) interface{} {
	if attr.S != nil {
		return *attr.S
	} else if attr.B != nil {
		return attr.B
	} else if attr.N != nil {
		return *attr.N
	}
	return nil
}

func (d *MultiRowDynamoDBImpl) Close() error {
	return nil
}
