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

type MultiRowRedisImpl struct {
	client redis.UniversalClient
	ctx    context.Context
}

func NewMultiRowRedisDB(region, tableName string) (*MultiRowRedisImpl, error) {
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
	return &MultiRowRedisImpl{client: client, ctx: ctx}, nil
}

func (r *MultiRowRedisImpl) PutItem(key string, data map[string]interface{}) error {
	//严格上来说，PutItem应该把不在data中的sk项都删除
	return r.UpdateItem(key, data)
}

func (r *MultiRowRedisImpl) UpdateItem(key string, data map[string]interface{}) error {
	kvPairs := make([]interface{}, 0, len(data)*2)
	for col, v := range data {
		field := fmt.Sprintf("{%s}:%s", key, col)
		kvPairs = append(kvPairs, field, r.processValue(v))
	}
	return r.client.MSet(r.ctx, kvPairs...).Err()
}

func (r *MultiRowRedisImpl) GetItem(key string) (map[string]interface{}, error) {
	pattern := fmt.Sprintf("{%s}:*", key)
	keys, err := r.client.Keys(r.ctx, pattern).Result()
	if err != nil {
		return nil, err
	}

	if len(keys) == 0 {
		return make(map[string]interface{}), nil
	}

	vals, err := r.client.MGet(r.ctx, keys...).Result()
	if err != nil {
		return nil, err
	}

	result := make(map[string]interface{})
	for i, val := range vals {
		if val != nil {
			col := keys[i][len(key)+3:] // 去掉 "{key}:" 前缀
			if str, ok := val.(string); ok {
				var v interface{}
				if sonic.UnmarshalString(str, &v) == nil {
					result[col] = v
				} else {
					result[col] = str
				}
			}
		}
	}
	return result, nil
}

func (r *MultiRowRedisImpl) GetSubItem(key string, columns []string) (map[string]interface{}, error) {
	keys := make([]string, len(columns))
	for i, col := range columns {
		keys[i] = fmt.Sprintf("{%s}:%s", key, col)
	}

	vals, err := r.client.MGet(r.ctx, keys...).Result()
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

func (r *MultiRowRedisImpl) BatchGetItem(keys []string) ([]map[string]interface{}, error) {
	results := make([]map[string]interface{}, 0, len(keys))
	
	for _, key := range keys {
		pattern := fmt.Sprintf("{%s}:*", key)
		redisKeys, err := r.client.Keys(r.ctx, pattern).Result()
		if err != nil {
			return nil, err
		}

		result := make(map[string]interface{})
		if len(redisKeys) > 0 {
			vals, err := r.client.MGet(r.ctx, redisKeys...).Result()
			if err != nil {
				return nil, err
			}

			for i, val := range vals {
				if val != nil {
					col := redisKeys[i][len(key)+3:] // 去掉 "{key}:" 前缀
					if str, ok := val.(string); ok {
						var v interface{}
						if sonic.UnmarshalString(str, &v) == nil {
							result[col] = v
						} else {
							result[col] = str
						}
					}
				}
			}
		}
		results = append(results, result)
	}
	return results, nil
}

func (r *MultiRowRedisImpl) BatchPutItem(items map[string]map[string]interface{}) error {
	pipe := r.client.Pipeline()
	for key, data := range items {
		for col, v := range data {
			field := fmt.Sprintf("{%s}:%s", key, col)
			pipe.Set(r.ctx, field, r.processValue(v), 0)
		}
	}
	_, err := pipe.Exec(r.ctx)
	return err
}

func (r *MultiRowRedisImpl) DeleteItem(key string) error {
	pattern := fmt.Sprintf("{%s}:*", key)
	keys, err := r.client.Keys(r.ctx, pattern).Result()
	if err != nil {
		return err
	}
	if len(keys) > 0 {
		return r.client.Del(r.ctx, keys...).Err()
	}
	return nil
}

func (r *MultiRowRedisImpl) BatchGetSubItem(keys []string, columns []string) ([]map[string]interface{}, error) {
	results := make([]map[string]interface{}, 0, len(keys))
	for _, key := range keys {
		item, err := r.GetSubItem(key, columns)
		if err != nil {
			return nil, err
		}
		results = append(results, item)
	}
	return results, nil
}

func (r *MultiRowRedisImpl) processValue(v interface{}) interface{} {
	switch val := v.(type) {
	case float64:
		data := make([]byte, int(val))
		rand.Read(data)
		return data
	default:
		jsonData, _ := sonic.Marshal(v)
		return jsonData
	}
}

func (r *MultiRowRedisImpl) Close() error {
	return r.client.Close()
}

func (r *MultiRowRedisImpl) GetImplName() string {
	return "MultiRowRedisImpl"
}
