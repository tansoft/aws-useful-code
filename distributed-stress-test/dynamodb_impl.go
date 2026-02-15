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

func (d *DynamoDBImpl) UpdateItem(key string, data map[string]interface{}) error {
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

func (d *DynamoDBImpl) Close() error {
	return nil
}
