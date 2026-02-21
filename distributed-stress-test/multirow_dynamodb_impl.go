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
	//严格上来说，PutItem应该把不在data中的sk项都删除
	return d.UpdateItem(key, data)
}

func (d *MultiRowDynamoDBImpl) UpdateItem(key string, data map[string]interface{}) error {
	writeRequests := make([]*dynamodb.WriteRequest, 0, len(data))
	for col, v := range data {
		item := map[string]*dynamodb.AttributeValue{
			"id":  {S: aws.String(key)},
			"sk":  {S: aws.String(col)},
			"val": d.toAttributeValue(v),
		}
		writeRequests = append(writeRequests, &dynamodb.WriteRequest{
			PutRequest: &dynamodb.PutRequest{Item: item},
		})
	}
	
	if len(writeRequests) > 0 {
		_, err := d.client.BatchWriteItem(&dynamodb.BatchWriteItemInput{
			RequestItems: map[string][]*dynamodb.WriteRequest{
				d.tableName: writeRequests,
			},
		})
		return err
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
			data[*sk.S] = d.fromAttributeValue(item["val"])
		}
	}
	return data, nil
}

func (d *MultiRowDynamoDBImpl) GetSubItem(key string, columns []string) (map[string]interface{}, error) {
	keyAttrs := make([]map[string]*dynamodb.AttributeValue, len(columns))
	for i, col := range columns {
		keyAttrs[i] = map[string]*dynamodb.AttributeValue{
			"id": {S: aws.String(key)},
			"sk": {S: aws.String(col)},
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

	data := make(map[string]interface{})
	for _, item := range result.Responses[d.tableName] {
		if sk := item["sk"]; sk != nil && sk.S != nil {
			data[*sk.S] = d.fromAttributeValue(item["val"])
		}
	}
	return data, nil
}

func (d *MultiRowDynamoDBImpl) BatchGetItem(keys []string) ([]map[string]interface{}, error) {
	type result struct {
		data map[string]interface{}
		err  error
		idx  int
	}
	
	resultChan := make(chan result, len(keys))
	for i, key := range keys {
		go func(idx int, k string) {
			queryResult, err := d.client.Query(&dynamodb.QueryInput{
				TableName:              aws.String(d.tableName),
				KeyConditionExpression: aws.String("id = :key"),
				ExpressionAttributeValues: map[string]*dynamodb.AttributeValue{
					":key": {S: aws.String(k)},
				},
			})
			if err != nil {
				resultChan <- result{err: err, idx: idx}
				return
			}
			
			data := make(map[string]interface{})
			for _, item := range queryResult.Items {
				if sk := item["sk"]; sk != nil && sk.S != nil {
					data[*sk.S] = d.fromAttributeValue(item["val"])
				}
			}
			resultChan <- result{data: data, idx: idx}
		}(i, key)
	}
	
	resultMap := make(map[int]map[string]interface{})
	for i := 0; i < len(keys); i++ {
		r := <-resultChan
		if r.err != nil {
			return nil, r.err
		}
		resultMap[r.idx] = r.data
	}
	
	results := make([]map[string]interface{}, len(keys))
	for i := 0; i < len(keys); i++ {
		results[i] = resultMap[i]
	}
	
	return results, nil
}

func (d *MultiRowDynamoDBImpl) BatchPutItem(items map[string]map[string]interface{}) error {
	writeRequests := make([]*dynamodb.WriteRequest, 0)
	
	for key, data := range items {
		for col, v := range data {
			item := map[string]*dynamodb.AttributeValue{
				"id":  {S: aws.String(key)},
				"sk":  {S: aws.String(col)},
				"val": d.toAttributeValue(v),
			}
			writeRequests = append(writeRequests, &dynamodb.WriteRequest{
				PutRequest: &dynamodb.PutRequest{Item: item},
			})
		}
	}
	
	// DynamoDB BatchWriteItem 限制每次最多25个item，需要分批
	for i := 0; i < len(writeRequests); i += 25 {
		end := i + 25
		if end > len(writeRequests) {
			end = len(writeRequests)
		}
		
		_, err := d.client.BatchWriteItem(&dynamodb.BatchWriteItemInput{
			RequestItems: map[string][]*dynamodb.WriteRequest{
				d.tableName: writeRequests[i:end],
			},
		})
		if err != nil {
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

func (d *MultiRowDynamoDBImpl) BatchGetSubItem(keys []string, columns []string) ([]map[string]interface{}, error) {
	keyAttrs := make([]map[string]*dynamodb.AttributeValue, 0)
	for _, key := range keys {
		for _, col := range columns {
			keyAttrs = append(keyAttrs, map[string]*dynamodb.AttributeValue{
				"id": {S: aws.String(key)},
				"sk": {S: aws.String(col)},
			})
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

	itemMap := make(map[string]map[string]interface{})
	for _, item := range result.Responses[d.tableName] {
		if id := item["id"]; id != nil && id.S != nil {
			if sk := item["sk"]; sk != nil && sk.S != nil {
				keyStr := *id.S
				if itemMap[keyStr] == nil {
					itemMap[keyStr] = make(map[string]interface{})
				}
				itemMap[keyStr][*sk.S] = d.fromAttributeValue(item["val"])
			}
		}
	}

	items := make([]map[string]interface{}, 0)
	for _, key := range keys {
		if data, ok := itemMap[key]; ok {
			items = append(items, data)
		} else {
			items = append(items, make(map[string]interface{}))
		}
	}
	return items, nil
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

func (d *MultiRowDynamoDBImpl) GetImplName() string {
	return "MultiRowDynamoDBImpl"
}
