package main

import (
	"context"
	"github.com/aws/aws-sdk-go-v2/service/dynamodb"
	"github.com/aws/aws-sdk-go-v2/service/dynamodb/types"
)

/*
父类接口 DDBHandler - 定义6大功能：
1. WriteAllColumns - 指定id多列数据一起写入
2. ReadAllColumns - 指定id多列数据一并返回
3. DeleteAllColumns - 指定id整列删除
4. UpdateSingleColumn - 指定id单列数据更新
5. ReadSingleColumn - 指定id单列数据获取
6. DeleteSingleColumn - 指定id单列数据删除
7. BatchReadAllColumns - 一次性获取多个id的所有列数据

MultiColumnHandler（多列模式） - 最佳实践：
• 写入全部：使用PutItem一次写入所有列
• 读取全部：使用GetItem获取整行
• 删除全部：使用DeleteItem删除整行
• 更新单列：使用UpdateItem的SET表达式（注意：会消耗整行WCU）
• 读取单列：使用GetItem + ProjectionExpression
• 删除单列：使用UpdateItem的REMOVE表达式
• 读取多行：使用 BatchGetItem 一次性获取多个id的所有列数据，返回格式：map[id]map[columnName]data

MultiRowHandler（多行模式） - 最佳实践：
• 写入全部：使用BatchWriteItem批量写入多行（每列一行）
• 读取全部：使用Query按id查询所有行（比BatchGetItem更省RCU）
• 删除全部：先Query获取所有sk，再BatchWriteItem批量删除
• 更新单列：使用PutItem写入单行（只消耗单行WCU）
• 读取单列：使用GetItem指定id+sk
• 删除单列：使用DeleteItem指定id+sk
• 读取多行：对每个id执行 Query 操作（因为多行模式下Query比BatchGetItem更省RCU）

这两个实现遵循了DDB-PATTERN.md中的建议，多行模式在频繁单列更新时更高效。
*/

// DDBHandler 父类接口
type DDBHandler interface {
	// WriteAllColumns 指定id多列数据一起写入
	WriteAllColumns(ctx context.Context, id string, data map[string][]byte) error
	// ReadAllColumns 指定id多列数据一并返回
	ReadAllColumns(ctx context.Context, id string) (map[string][]byte, error)
	// BatchReadAllColumns 多个id同时请求AllColumn
	BatchReadAllColumns(ctx context.Context, ids []string) (map[string]map[string][]byte, error)
	// DeleteAllColumns 指定id整列删除
	DeleteAllColumns(ctx context.Context, id string) error
	// UpdateSingleColumn 指定id单列数据更新
	UpdateSingleColumn(ctx context.Context, id string, columnName string, data []byte) error
	// ReadSingleColumn 指定id单列数据获取
	ReadSingleColumn(ctx context.Context, id string, columnName string) ([]byte, error)
	// DeleteSingleColumn 指定id单列数据删除
	DeleteSingleColumn(ctx context.Context, id string, columnName string) error
}

// MultiColumnHandler 多列模式实现
type MultiColumnHandler struct {
	client    *dynamodb.Client
	tableName string
}

func NewMultiColumnHandler(client *dynamodb.Client, tableName string) *MultiColumnHandler {
	return &MultiColumnHandler{
		client:    client,
		tableName: tableName,
	}
}

func (h *MultiColumnHandler) WriteAllColumns(ctx context.Context, id string, data map[string][]byte) error {
	item := map[string]types.AttributeValue{"id": &types.AttributeValueMemberS{Value: id}}
	for k, v := range data {
		item[k] = &types.AttributeValueMemberB{Value: v}
	}
	_, err := h.client.PutItem(ctx, &dynamodb.PutItemInput{
		TableName: &h.tableName,
		Item:      item,
	})
	return err
}

func (h *MultiColumnHandler) ReadAllColumns(ctx context.Context, id string) (map[string][]byte, error) {
	result, err := h.client.GetItem(ctx, &dynamodb.GetItemInput{
		TableName: &h.tableName,
		Key:       map[string]types.AttributeValue{"id": &types.AttributeValueMemberS{Value: id}},
	})
	if err != nil {
		return nil, err
	}
	data := make(map[string][]byte)
	for k, v := range result.Item {
		if k != "id" {
			if b, ok := v.(*types.AttributeValueMemberB); ok {
				data[k] = b.Value
			}
		}
	}
	return data, nil
}

func (h *MultiColumnHandler) BatchReadAllColumns(ctx context.Context, ids []string) (map[string]map[string][]byte, error) {
	keys := make([]map[string]types.AttributeValue, len(ids))
	for i, id := range ids {
		keys[i] = map[string]types.AttributeValue{"id": &types.AttributeValueMemberS{Value: id}}
	}
	result, err := h.client.BatchGetItem(ctx, &dynamodb.BatchGetItemInput{
		RequestItems: map[string]types.KeysAndAttributes{h.tableName: {Keys: keys}},
	})
	if err != nil {
		return nil, err
	}
	data := make(map[string]map[string][]byte)
	for _, item := range result.Responses[h.tableName] {
		if idAttr, ok := item["id"].(*types.AttributeValueMemberS); ok {
			columns := make(map[string][]byte)
			for k, v := range item {
				if k != "id" {
					if b, ok := v.(*types.AttributeValueMemberB); ok {
						columns[k] = b.Value
					}
				}
			}
			data[idAttr.Value] = columns
		}
	}
	return data, nil
}

func (h *MultiColumnHandler) DeleteAllColumns(ctx context.Context, id string) error {
	_, err := h.client.DeleteItem(ctx, &dynamodb.DeleteItemInput{
		TableName: &h.tableName,
		Key:       map[string]types.AttributeValue{"id": &types.AttributeValueMemberS{Value: id}},
	})
	return err
}

func (h *MultiColumnHandler) UpdateSingleColumn(ctx context.Context, id string, columnName string, data []byte) error {
	updateExpr := "SET " + columnName + " = :val"
	_, err := h.client.UpdateItem(ctx, &dynamodb.UpdateItemInput{
		TableName:        &h.tableName,
		Key:              map[string]types.AttributeValue{"id": &types.AttributeValueMemberS{Value: id}},
		UpdateExpression: &updateExpr,
		ExpressionAttributeValues: map[string]types.AttributeValue{
			":val": &types.AttributeValueMemberB{Value: data},
		},
	})
	return err
}

func (h *MultiColumnHandler) ReadSingleColumn(ctx context.Context, id string, columnName string) ([]byte, error) {
	result, err := h.client.GetItem(ctx, &dynamodb.GetItemInput{
		TableName:            &h.tableName,
		Key:                  map[string]types.AttributeValue{"id": &types.AttributeValueMemberS{Value: id}},
		ProjectionExpression: &columnName,
	})
	if err != nil {
		return nil, err
	}
	if b, ok := result.Item[columnName].(*types.AttributeValueMemberB); ok {
		return b.Value, nil
	}
	return nil, nil
}

func (h *MultiColumnHandler) DeleteSingleColumn(ctx context.Context, id string, columnName string) error {
	removeExpr := "REMOVE " + columnName
	_, err := h.client.UpdateItem(ctx, &dynamodb.UpdateItemInput{
		TableName:        &h.tableName,
		Key:              map[string]types.AttributeValue{"id": &types.AttributeValueMemberS{Value: id}},
		UpdateExpression: &removeExpr,
	})
	return err
}

// MultiRowHandler 多行模式实现
type MultiRowHandler struct {
	client    *dynamodb.Client
	tableName string
}

func NewMultiRowHandler(client *dynamodb.Client, tableName string) *MultiRowHandler {
	return &MultiRowHandler{
		client:    client,
		tableName: tableName,
	}
}

func (h *MultiRowHandler) WriteAllColumns(ctx context.Context, id string, data map[string][]byte) error {
	requests := make([]types.WriteRequest, 0, len(data))
	for k, v := range data {
		item := map[string]types.AttributeValue{
			"id":  &types.AttributeValueMemberS{Value: id},
			"sk":  &types.AttributeValueMemberS{Value: k},
			"val": &types.AttributeValueMemberB{Value: v},
		}
		requests = append(requests, types.WriteRequest{PutRequest: &types.PutRequest{Item: item}})
	}
	
	// BatchWriteItem限制25条，需要分批
	for i := 0; i < len(requests); i += 25 {
		end := i + 25
		if end > len(requests) {
			end = len(requests)
		}
		_, err := h.client.BatchWriteItem(ctx, &dynamodb.BatchWriteItemInput{
			RequestItems: map[string][]types.WriteRequest{h.tableName: requests[i:end]},
		})
		if err != nil {
			return err
		}
	}
	return nil
}

func (h *MultiRowHandler) ReadAllColumns(ctx context.Context, id string) (map[string][]byte, error) {
	keyCondExpr := "id = :id"
	result, err := h.client.Query(ctx, &dynamodb.QueryInput{
		TableName:              &h.tableName,
		KeyConditionExpression: &keyCondExpr,
		ExpressionAttributeValues: map[string]types.AttributeValue{
			":id": &types.AttributeValueMemberS{Value: id},
		},
	})
	if err != nil {
		return nil, err
	}
	data := make(map[string][]byte)
	for _, item := range result.Items {
		if sk, ok := item["sk"].(*types.AttributeValueMemberS); ok {
			if val, ok := item["val"].(*types.AttributeValueMemberB); ok {
				data[sk.Value] = val.Value
			}
		}
	}
	return data, nil
}

func (h *MultiRowHandler) BatchReadAllColumns(ctx context.Context, ids []string) (map[string]map[string][]byte, error) {
	data := make(map[string]map[string][]byte)
	for _, id := range ids {
		columns, err := h.ReadAllColumns(ctx, id)
		if err != nil {
			return nil, err
		}
		data[id] = columns
	}
	return data, nil
}

func (h *MultiRowHandler) DeleteAllColumns(ctx context.Context, id string) error {
	keyCondExpr := "id = :id"
	result, err := h.client.Query(ctx, &dynamodb.QueryInput{
		TableName:              &h.tableName,
		KeyConditionExpression: &keyCondExpr,
		ExpressionAttributeValues: map[string]types.AttributeValue{
			":id": &types.AttributeValueMemberS{Value: id},
		},
	})
	if err != nil {
		return err
	}
	requests := make([]types.WriteRequest, 0, len(result.Items))
	for _, item := range result.Items {
		key := map[string]types.AttributeValue{
			"id": item["id"],
			"sk": item["sk"],
		}
		requests = append(requests, types.WriteRequest{DeleteRequest: &types.DeleteRequest{Key: key}})
	}
	
	// BatchWriteItem限制25条，需要分批
	for i := 0; i < len(requests); i += 25 {
		end := i + 25
		if end > len(requests) {
			end = len(requests)
		}
		_, err = h.client.BatchWriteItem(ctx, &dynamodb.BatchWriteItemInput{
			RequestItems: map[string][]types.WriteRequest{h.tableName: requests[i:end]},
		})
		if err != nil {
			return err
		}
	}
	return nil
}

func (h *MultiRowHandler) UpdateSingleColumn(ctx context.Context, id string, columnName string, data []byte) error {
	_, err := h.client.PutItem(ctx, &dynamodb.PutItemInput{
		TableName: &h.tableName,
		Item: map[string]types.AttributeValue{
			"id":  &types.AttributeValueMemberS{Value: id},
			"sk":  &types.AttributeValueMemberS{Value: columnName},
			"val": &types.AttributeValueMemberB{Value: data},
		},
	})
	return err
}

func (h *MultiRowHandler) ReadSingleColumn(ctx context.Context, id string, columnName string) ([]byte, error) {
	result, err := h.client.GetItem(ctx, &dynamodb.GetItemInput{
		TableName: &h.tableName,
		Key: map[string]types.AttributeValue{
			"id": &types.AttributeValueMemberS{Value: id},
			"sk": &types.AttributeValueMemberS{Value: columnName},
		},
	})
	if err != nil {
		return nil, err
	}
	if val, ok := result.Item["val"].(*types.AttributeValueMemberB); ok {
		return val.Value, nil
	}
	return nil, nil
}

func (h *MultiRowHandler) DeleteSingleColumn(ctx context.Context, id string, columnName string) error {
	_, err := h.client.DeleteItem(ctx, &dynamodb.DeleteItemInput{
		TableName: &h.tableName,
		Key: map[string]types.AttributeValue{
			"id": &types.AttributeValueMemberS{Value: id},
			"sk": &types.AttributeValueMemberS{Value: columnName},
		},
	})
	return err
}
