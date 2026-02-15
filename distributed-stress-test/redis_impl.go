package main

import (
	"context"
	"encoding/json"
	"fmt"
	"math/rand"

	"github.com/aws/aws-sdk-go/aws"
	"github.com/aws/aws-sdk-go/aws/session"
	"github.com/aws/aws-sdk-go/service/elasticache"
	"github.com/go-redis/redis/v8"
)

type RedisImpl struct {
	client redis.UniversalClient
	ctx    context.Context
}

func NewRedisDB(region, tableName string) (*RedisImpl, error) {
	sess, err := session.NewSession(&aws.Config{Region: aws.String(region)})
	if err != nil {
		return nil, err
	}

	ec := elasticache.New(sess)
	resp, err := ec.DescribeReplicationGroups(&elasticache.DescribeReplicationGroupsInput{
		ReplicationGroupId: aws.String(tableName),
	})
	if err != nil {
		return nil, err
	}

	var client redis.UniversalClient
	if resp.ReplicationGroups[0].ConfigurationEndpoint != nil {
		endpoint := resp.ReplicationGroups[0].ConfigurationEndpoint
		addr := fmt.Sprintf("%s:%d", *endpoint.Address, *endpoint.Port)
		client = redis.NewClusterClient(&redis.ClusterOptions{Addrs: []string{addr}})
	} else {
		endpoint := resp.ReplicationGroups[0].NodeGroups[0].PrimaryEndpoint
		addr := fmt.Sprintf("%s:%d", *endpoint.Address, *endpoint.Port)
		client = redis.NewClient(&redis.Options{Addr: addr})
	}

	ctx := context.Background()
	if err := client.Ping(ctx).Err(); err != nil {
		return nil, err
	}
	return &RedisImpl{client: client, ctx: ctx}, nil
}

func (r *RedisImpl) UpdateItem(key string, data map[string]interface{}) error {
	processedData := make(map[string]interface{})
	for k, v := range data {
		processedData[k] = r.processValue(v)
	}
	jsonData, _ := json.Marshal(processedData)
	return r.client.Set(r.ctx, key, jsonData, 0).Err()
}

func (r *RedisImpl) Query(key string) error {
	return r.client.Get(r.ctx, key).Err()
}

func (r *RedisImpl) processValue(v interface{}) interface{} {
	switch val := v.(type) {
	case float64:
		data := make([]byte, int(val))
		rand.Read(data)
		return data
	default:
		return v
	}
}

func (r *RedisImpl) Close() error {
	return r.client.Close()
}
