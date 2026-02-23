package main

import (
	"context"
	"crypto/tls"
	"fmt"
	"math/rand"
	"strings"
	"time"

	"github.com/aws/aws-sdk-go/aws"
	"github.com/aws/aws-sdk-go/aws/session"
	"github.com/aws/aws-sdk-go/service/elasticache"
	"github.com/bytedance/sonic"
	"github.com/redis/go-redis/v9"
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
		useTLS := strings.Contains(addr, "cache.amazonaws.com")
		opts := &redis.ClusterOptions{
			Addrs:        []string{addr},
			PoolSize:     100,
			MinIdleConns: 20,
			DialTimeout:  30 * time.Second,
			ReadTimeout:  30 * time.Second,
			WriteTimeout: 30 * time.Second,
			PoolTimeout:  60 * time.Second,
		}
		if useTLS {
			opts.TLSConfig = &tls.Config{MinVersion: tls.VersionTLS12}
		}
		client = redis.NewClusterClient(opts)
	} else {
		endpoint := resp.ReplicationGroups[0].NodeGroups[0].PrimaryEndpoint
		addr := fmt.Sprintf("%s:%d", *endpoint.Address, *endpoint.Port)
		useTLS := strings.Contains(addr, "cache.amazonaws.com")
		opts := &redis.Options{
			Addr:         addr,
			PoolSize:     100,
			MinIdleConns: 20,
			DialTimeout:  30 * time.Second,
			ReadTimeout:  30 * time.Second,
			WriteTimeout: 30 * time.Second,
			PoolTimeout:  60 * time.Second,
		}
		if useTLS {
			opts.TLSConfig = &tls.Config{MinVersion: tls.VersionTLS12}
		}
		client = redis.NewClient(opts)
	}

	ctx := context.Background()
	if err := client.Ping(ctx).Err(); err != nil {
		return nil, err
	}
	return &RedisImpl{client: client, ctx: ctx}, nil
}

func (r *RedisImpl) PutItem(key string, data map[string]interface{}) error {
	processedData := make(map[string]interface{})
	for k, v := range data {
		processedData[k] = r.processValue(v)
	}
	jsonData, _ := sonic.MarshalString(processedData)
	return r.client.Set(r.ctx, key, jsonData, 0).Err()
}

func (r *RedisImpl) UpdateItem(key string, data map[string]interface{}) error {
	// 先获取现有数据，可以考虑 hget hset 等进行单列修改
	existing := make(map[string]interface{})
	if val, err := r.client.Get(r.ctx, key).Result(); err == nil {
		sonic.UnmarshalString(val, &existing)
	}

	// 更新指定列
	for k, v := range data {
		existing[k] = r.processValue(v)
	}

	jsonData, _ := sonic.MarshalString(existing)
	return r.client.Set(r.ctx, key, jsonData, 0).Err()
}

func (r *RedisImpl) GetItem(key string) (map[string]interface{}, error) {
	val, err := r.client.Get(r.ctx, key).Result()
	if err != nil {
		return nil, err
	}
	var result map[string]interface{}
	if err := sonic.UnmarshalString(val, &result); err != nil {
		return nil, err
	}
	return result, nil
}

func (r *RedisImpl) GetSubItem(key string, columns []string) (map[string]interface{}, error) {
	// 指定列返回的需求，可以通过 hget hset 来实现
	val, err := r.client.Get(r.ctx, key).Result()
	if err != nil {
		return nil, err
	}
	var allData map[string]interface{}
	if err := sonic.UnmarshalString(val, &allData); err != nil {
		return nil, err
	}
	result := make(map[string]interface{})
	for _, col := range columns {
		if value, ok := allData[col]; ok {
			result[col] = value
		}
	}
	return result, nil
}

func (r *RedisImpl) BatchGetItem(keys []string) ([]map[string]interface{}, error) {
	pipe := r.client.Pipeline()
	cmds := make([]*redis.StringCmd, len(keys))
	for i, key := range keys {
		cmds[i] = pipe.Get(r.ctx, key)
	}
	if _, err := pipe.Exec(r.ctx); err != nil && err != redis.Nil {
		return nil, err
	}

	results := make([]map[string]interface{}, 0)
	for _, cmd := range cmds {
		if val, err := cmd.Result(); err == nil {
			var item map[string]interface{}
			if sonic.UnmarshalString(val, &item) == nil {
				results = append(results, item)
			}
		}
	}
	return results, nil
}

func (r *RedisImpl) BatchPutItem(items map[string]map[string]interface{}) error {
	pipe := r.client.Pipeline()
	for key, data := range items {
		processedData := make(map[string]interface{})
		for k, v := range data {
			processedData[k] = r.processValue(v)
		}
		jsonData, _ := sonic.MarshalString(processedData)
		pipe.Set(r.ctx, key, jsonData, 0)
	}
	_, err := pipe.Exec(r.ctx)
	return err
}

func (r *RedisImpl) DeleteItem(key string) error {
	return r.client.Del(r.ctx, key).Err()
}

func (r *RedisImpl) BatchGetSubItem(keys []string, columns []string) ([]map[string]interface{}, error) {
	pipe := r.client.Pipeline()
	cmds := make([]*redis.StringCmd, len(keys))
	for i, key := range keys {
		cmds[i] = pipe.Get(r.ctx, key)
	}
	if _, err := pipe.Exec(r.ctx); err != nil && err != redis.Nil {
		return nil, err
	}

	results := make([]map[string]interface{}, 0)
	for _, cmd := range cmds {
		result := make(map[string]interface{})
		if val, err := cmd.Result(); err == nil {
			var allData map[string]interface{}
			if sonic.UnmarshalString(val, &allData) == nil {
				for _, col := range columns {
					if value, ok := allData[col]; ok {
						result[col] = value
					}
				}
			}
		}
		results = append(results, result)
	}
	return results, nil
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

func (r *RedisImpl) GetImplName() string {
	return "RedisImpl"
}
