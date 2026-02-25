package main

import (
	"context"
	"crypto/tls"
	"fmt"
	"strings"
	"time"

	"github.com/aws/aws-sdk-go/aws"
	"github.com/aws/aws-sdk-go/aws/session"
	"github.com/aws/aws-sdk-go/service/elasticache"
	"github.com/bytedance/sonic"
	"github.com/redis/go-redis/v9"
)

type HashRedisImpl struct {
	client redis.UniversalClient
	ctx    context.Context
}

func NewHashRedisDB(region, tableName string) (*HashRedisImpl, error) {
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
			MinIdleConns: 100,
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
			MinIdleConns: 100,
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
	return &HashRedisImpl{client: client, ctx: ctx}, nil
}

func (r *HashRedisImpl) processValue(v interface{}) string {
	switch val := v.(type) {
	case int:
		data := make([]byte, val)
		return string(data)
	case string:
		return val
	default:
		jsonData, _ := sonic.MarshalString(v)
		return jsonData
	}
}

// PutItem 覆盖整个 hash
func (r *HashRedisImpl) PutItem(key string, data map[string]interface{}) error {
	pipe := r.client.Pipeline()
	pipe.Del(r.ctx, key)
	
	fields := make([]interface{}, 0, len(data)*2)
	for col, v := range data {
		fields = append(fields, col, r.processValue(v))
	}
	if len(fields) > 0 {
		pipe.HSet(r.ctx, key, fields...)
	}
	_, err := pipe.Exec(r.ctx)
	return err
}

// UpdateItem 只更新指定列，无需先读取
func (r *HashRedisImpl) UpdateItem(key string, data map[string]interface{}) error {
	fields := make([]interface{}, 0, len(data)*2)
	for col, v := range data {
		fields = append(fields, col, r.processValue(v))
	}
	return r.client.HSet(r.ctx, key, fields...).Err()
}

// GetItem 获取所有列
func (r *HashRedisImpl) GetItem(key string) (map[string]interface{}, error) {
	vals, err := r.client.HGetAll(r.ctx, key).Result()
	if err != nil {
		return nil, err
	}
	
	result := make(map[string]interface{})
	for col, val := range vals {
		var v interface{}
		if sonic.UnmarshalString(val, &v) == nil {
			result[col] = v
		} else {
			result[col] = val
		}
	}
	return result, nil
}

// GetSubItem 只获取指定列
func (r *HashRedisImpl) GetSubItem(key string, columns []string) (map[string]interface{}, error) {
	vals, err := r.client.HMGet(r.ctx, key, columns...).Result()
	if err != nil {
		return nil, err
	}
	
	result := make(map[string]interface{})
	for i, val := range vals {
		if val != nil {
			if str, ok := val.(string); ok {
				var v interface{}
				if sonic.UnmarshalString(str, &v) == nil {
					result[columns[i]] = v
				} else {
					result[columns[i]] = str
				}
			}
		}
	}
	return result, nil
}

// DeleteItem 删除整个 hash
func (r *HashRedisImpl) DeleteItem(key string) error {
	return r.client.Del(r.ctx, key).Err()
}

// BatchGetItem 批量获取
func (r *HashRedisImpl) BatchGetItem(keys []string) ([]map[string]interface{}, error) {
	pipe := r.client.Pipeline()
	cmds := make([]*redis.MapStringStringCmd, len(keys))
	for i, key := range keys {
		cmds[i] = pipe.HGetAll(r.ctx, key)
	}
	
	if _, err := pipe.Exec(r.ctx); err != nil && err != redis.Nil {
		return nil, err
	}
	
	results := make([]map[string]interface{}, 0, len(keys))
	for _, cmd := range cmds {
		vals, _ := cmd.Result()
		result := make(map[string]interface{})
		for col, val := range vals {
			var v interface{}
			if sonic.UnmarshalString(val, &v) == nil {
				result[col] = v
			} else {
				result[col] = val
			}
		}
		results = append(results, result)
	}
	return results, nil
}

// BatchGetSubItem 批量获取指定列
func (r *HashRedisImpl) BatchGetSubItem(keys []string, columns []string) ([]map[string]interface{}, error) {
	pipe := r.client.Pipeline()
	cmds := make([]*redis.SliceCmd, len(keys))
	for i, key := range keys {
		cmds[i] = pipe.HMGet(r.ctx, key, columns...)
	}
	
	if _, err := pipe.Exec(r.ctx); err != nil && err != redis.Nil {
		return nil, err
	}
	
	results := make([]map[string]interface{}, 0, len(keys))
	for _, cmd := range cmds {
		vals, _ := cmd.Result()
		result := make(map[string]interface{})
		for i, val := range vals {
			if val != nil {
				if str, ok := val.(string); ok {
					var v interface{}
					if sonic.UnmarshalString(str, &v) == nil {
						result[columns[i]] = v
					} else {
						result[columns[i]] = str
					}
				}
			}
		}
		results = append(results, result)
	}
	return results, nil
}

// BatchPutItem 批量写入
func (r *HashRedisImpl) BatchPutItem(items map[string]map[string]interface{}) error {
	pipe := r.client.Pipeline()
	for key, data := range items {
		pipe.Del(r.ctx, key)
		fields := make([]interface{}, 0, len(data)*2)
		for col, v := range data {
			fields = append(fields, col, r.processValue(v))
		}
		if len(fields) > 0 {
			pipe.HSet(r.ctx, key, fields...)
		}
	}
	_, err := pipe.Exec(r.ctx)
	return err
}

func (r *HashRedisImpl) Close() error {
	return r.client.Close()
}

func (r *HashRedisImpl) GetImplName() string {
	return "HashRedis"
}
