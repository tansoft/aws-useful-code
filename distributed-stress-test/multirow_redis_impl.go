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
	return &MultiRowRedisImpl{client: client, ctx: ctx}, nil
}

func (r *MultiRowRedisImpl) PutItem(key string, data map[string]interface{}) error {
	//严格上来说，PutItem应该把不在data中的sk项都删除
	return r.UpdateItem(key, data)
}

func (r *MultiRowRedisImpl) UpdateItem(key string, data map[string]interface{}) error {
	pipe := r.client.Pipeline()
	for col, v := range data {
		field := fmt.Sprintf("%s:sk:%s", key, col)
		pipe.Set(r.ctx, field, r.processValue(v), 0)
	}
	_, err := pipe.Exec(r.ctx)
	return err
}

func (r *MultiRowRedisImpl) GetItem(key string) (map[string]interface{}, error) {
	pattern := fmt.Sprintf("%s:sk:*", key)
	keys, err := r.client.Keys(r.ctx, pattern).Result()
	if err != nil {
		return nil, err
	}

	if len(keys) == 0 {
		return make(map[string]interface{}), nil
	}

	pipe := r.client.Pipeline()
	cmds := make([]*redis.StringCmd, len(keys))
	for i, k := range keys {
		cmds[i] = pipe.Get(r.ctx, k)
	}
	if _, err := pipe.Exec(r.ctx); err != nil && err != redis.Nil {
		return nil, err
	}

	result := make(map[string]interface{})
	for i, cmd := range cmds {
		if val, err := cmd.Result(); err == nil {
			col := keys[i][len(key)+4:] // 去掉 "key:sk:" 前缀
			var v interface{}
			if json.Unmarshal([]byte(val), &v) == nil {
				result[col] = v
			} else {
				result[col] = val
			}
		}
	}
	return result, nil
}

func (r *MultiRowRedisImpl) GetSubItem(key string, columns []string) (map[string]interface{}, error) {
	pipe := r.client.Pipeline()
	cmds := make([]*redis.StringCmd, len(columns))
	for i, col := range columns {
		field := fmt.Sprintf("%s:sk:%s", key, col)
		cmds[i] = pipe.Get(r.ctx, field)
	}
	if _, err := pipe.Exec(r.ctx); err != nil && err != redis.Nil {
		return nil, err
	}

	result := make(map[string]interface{})
	for i, cmd := range cmds {
		if val, err := cmd.Result(); err == nil {
			var v interface{}
			if json.Unmarshal([]byte(val), &v) == nil {
				result[columns[i]] = v
			} else {
				result[columns[i]] = val
			}
		}
	}
	return result, nil
}

func (r *MultiRowRedisImpl) BatchGetItem(keys []string) ([]map[string]interface{}, error) {
	results := make([]map[string]interface{}, 0, len(keys))
	for _, key := range keys {
		item, err := r.GetItem(key)
		if err != nil {
			return nil, err
		}
		results = append(results, item)
	}
	return results, nil
}

func (r *MultiRowRedisImpl) BatchPutItem(items map[string]map[string]interface{}) error {
	pipe := r.client.Pipeline()
	for key, data := range items {
		for col, v := range data {
			field := fmt.Sprintf("%s:sk:%s", key, col)
			pipe.Set(r.ctx, field, r.processValue(v), 0)
		}
	}
	_, err := pipe.Exec(r.ctx)
	return err
}

func (r *MultiRowRedisImpl) DeleteItem(key string) error {
	pattern := fmt.Sprintf("%s:sk:*", key)
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
		jsonData, _ := json.Marshal(v)
		return jsonData
	}
}

func (r *MultiRowRedisImpl) Close() error {
	return r.client.Close()
}
