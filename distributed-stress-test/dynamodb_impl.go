package main

import (
	"fmt"
	"math/rand"

	"github.com/aws/aws-sdk-go/aws"
	"github.com/aws/aws-sdk-go/aws/session"
	"github.com/aws/aws-sdk-go/service/dynamodb"
)

type DynamoDBImpl struct {
	client    *dynamodb.DynamoDB
	tableName string
}

func NewDynamoDB(region, tableName string) (*DynamoDBImpl, error) {
	sess, err := session.NewSession(&aws.Config{Region: aws.String(region)})
	if err != nil {
		return nil, err
	}
	return &DynamoDBImpl{
		client:    dynamodb.New(sess),
		tableName: tableName,
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

func (d *DynamoDBImpl) Query(key string) error {
	_, err := d.client.Query(&dynamodb.QueryInput{
		TableName:              aws.String(d.tableName),
		KeyConditionExpression: aws.String("id = :key"),
		ExpressionAttributeValues: map[string]*dynamodb.AttributeValue{
			":key": {S: aws.String(key)},
		},
		Limit: aws.Int64(10),
	})
	return err
}

func (d *DynamoDBImpl) toAttributeValue(v interface{}) *dynamodb.AttributeValue {
	switch val := v.(type) {
	case string:
		return &dynamodb.AttributeValue{S: aws.String(val)}
	case float64:
		data := make([]byte, int(val))
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
