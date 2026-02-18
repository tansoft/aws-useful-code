package main

import (
	"fmt"
	"math/rand"
	"net"
	"net/http"
	"strings"
	"time"

	"github.com/aws/aws-sdk-go/aws"
	"github.com/aws/aws-sdk-go/aws/session"
	"github.com/aws/aws-sdk-go/service/dynamodb"
)

type DynamoDBImpl struct {
	client    *dynamodb.DynamoDB
	tableName string
	dataCache map[int][]byte // 预生成数据缓存
}

func NewDynamoDB(region, tableName string) (*DynamoDBImpl, error) {
	// 优化 HTTP 连接池
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
			DisableKeepAlives:   false,
			DisableCompression:  true,
			ForceAttemptHTTP2:   false,
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

	// 预生成常用大小的数据
	dataCache := make(map[int][]byte)
	for _, size := range []int{100, 1000, 8000, 10000, 50000, 100000} {
		data := make([]byte, size)
		rand.Read(data)
		dataCache[size] = data
	}

	return &DynamoDBImpl{
		client:    dynamodb.New(sess),
		tableName: tableName,
		dataCache: dataCache,
	}, nil
}

func (d *DynamoDBImpl) PutItem(key string, data map[string]interface{}) error {
	item := make(map[string]*dynamodb.AttributeValue)
	item["id"] = &dynamodb.AttributeValue{S: aws.String(key)}

	for k, v := range data {
		item[k] = d.toAttributeValue(v)
	}

	_, err := d.client.PutItem(&dynamodb.PutItemInput{
		TableName: aws.String(d.tableName),
		Item:      item,
	})
	return err
}

func (d *DynamoDBImpl) UpdateItem(key string, data map[string]interface{}) error {
	updateExpr := "SET "
	exprAttrNames := make(map[string]*string)
	exprAttrValues := make(map[string]*dynamodb.AttributeValue)
	idx := 0
	for k, v := range data {
		if idx > 0 {
			updateExpr += ", "
		}
		namePlaceholder := fmt.Sprintf("#n%d", idx)
		valuePlaceholder := fmt.Sprintf(":val%d", idx)
		updateExpr += fmt.Sprintf("%s = %s", namePlaceholder, valuePlaceholder)
		exprAttrNames[namePlaceholder] = aws.String(k)
		exprAttrValues[valuePlaceholder] = d.toAttributeValue(v)
		idx++
	}

	_, err := d.client.UpdateItem(&dynamodb.UpdateItemInput{
		TableName: aws.String(d.tableName),
		Key: map[string]*dynamodb.AttributeValue{
			"id": {S: aws.String(key)},
		},
		UpdateExpression:          aws.String(updateExpr),
		ExpressionAttributeNames:  exprAttrNames,
		ExpressionAttributeValues: exprAttrValues,
	})
	return err
}

func (d *DynamoDBImpl) GetItem(key string) (map[string]interface{}, error) {
	result, err := d.client.GetItem(&dynamodb.GetItemInput{
		TableName: aws.String(d.tableName),
		Key: map[string]*dynamodb.AttributeValue{
			"id": {S: aws.String(key)},
		},
	})
	if err != nil {
		return nil, err
	}
	return d.fromAttributeValueMap(result.Item), nil
}

func (d *DynamoDBImpl) GetSubItem(key string, columns []string) (map[string]interface{}, error) {
	projection := strings.Join(columns, ", ")
	result, err := d.client.GetItem(&dynamodb.GetItemInput{
		TableName: aws.String(d.tableName),
		Key: map[string]*dynamodb.AttributeValue{
			"id": {S: aws.String(key)},
		},
		ProjectionExpression: aws.String(projection),
	})
	if err != nil {
		return nil, err
	}
	return d.fromAttributeValueMap(result.Item), nil
}

func (d *DynamoDBImpl) BatchGetItem(keys []string) ([]map[string]interface{}, error) {
	keyAttrs := make([]map[string]*dynamodb.AttributeValue, len(keys))
	for i, key := range keys {
		keyAttrs[i] = map[string]*dynamodb.AttributeValue{
			"id": {S: aws.String(key)},
		}
	}

	result, err := d.client.BatchGetItem(&dynamodb.BatchGetItemInput{
		RequestItems: map[string]*dynamodb.KeysAndAttributes{
			d.tableName: {Keys: keyAttrs},
		},
	})
	if err != nil {
		return nil, err
	}

	items := make([]map[string]interface{}, 0)
	for _, item := range result.Responses[d.tableName] {
		items = append(items, d.fromAttributeValueMap(item))
	}
	return items, nil
}

func (d *DynamoDBImpl) BatchPutItem(items map[string]map[string]interface{}) error {
	writeRequests := make([]*dynamodb.WriteRequest, 0, len(items))
	for key, data := range items {
		item := make(map[string]*dynamodb.AttributeValue)
		item["id"] = &dynamodb.AttributeValue{S: aws.String(key)}
		for k, v := range data {
			item[k] = d.toAttributeValue(v)
		}
		writeRequests = append(writeRequests, &dynamodb.WriteRequest{
			PutRequest: &dynamodb.PutRequest{Item: item},
		})
	}

	_, err := d.client.BatchWriteItem(&dynamodb.BatchWriteItemInput{
		RequestItems: map[string][]*dynamodb.WriteRequest{
			d.tableName: writeRequests,
		},
	})
	return err
}

func (d *DynamoDBImpl) DeleteItem(key string) error {
	_, err := d.client.DeleteItem(&dynamodb.DeleteItemInput{
		TableName: aws.String(d.tableName),
		Key: map[string]*dynamodb.AttributeValue{
			"id": {S: aws.String(key)},
		},
	})
	return err
}

func (d *DynamoDBImpl) BatchGetSubItem(keys []string, columns []string) ([]map[string]interface{}, error) {
	projection := strings.Join(columns, ", ")
	keyAttrs := make([]map[string]*dynamodb.AttributeValue, len(keys))
	for i, key := range keys {
		keyAttrs[i] = map[string]*dynamodb.AttributeValue{
			"id": {S: aws.String(key)},
		}
	}

	result, err := d.client.BatchGetItem(&dynamodb.BatchGetItemInput{
		RequestItems: map[string]*dynamodb.KeysAndAttributes{
			d.tableName: {
				Keys:                 keyAttrs,
				ProjectionExpression: aws.String(projection),
			},
		},
	})
	if err != nil {
		return nil, err
	}

	items := make([]map[string]interface{}, 0)
	for _, item := range result.Responses[d.tableName] {
		items = append(items, d.fromAttributeValueMap(item))
	}
	return items, nil
}

func (d *DynamoDBImpl) toAttributeValue(v interface{}) *dynamodb.AttributeValue {
	switch val := v.(type) {
	case string:
		return &dynamodb.AttributeValue{S: aws.String(val)}
	case float64:
		size := int(val)
		// 使用缓存数据，避免每次生成随机数
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

func (d *DynamoDBImpl) fromAttributeValueMap(item map[string]*dynamodb.AttributeValue) map[string]interface{} {
	result := make(map[string]interface{})
	for k, v := range item {
		if v.S != nil {
			result[k] = *v.S
		} else if v.B != nil {
			result[k] = v.B
		} else if v.N != nil {
			result[k] = *v.N
		}
	}
	return result
}

func (d *DynamoDBImpl) Close() error {
	return nil
}
