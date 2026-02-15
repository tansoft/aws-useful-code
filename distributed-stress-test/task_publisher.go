package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"math/rand"
	"os"
	"sync"
	"time"

	"github.com/go-redis/redis/v8"
)

type Config struct {
	TableName  string                   `json:"table_name"`
	Region     string                   `json:"region"`
	Threads    int                      `json:"threads"`
	SampleData []map[string]interface{} `json:"sample_data"`
}

type Task struct {
	Action   string                 `json:"action"`
	Seed     int                    `json:"seed,omitempty"`
	Seeds    []float64              `json:"seeds,omitempty"`
	QPS      int                    `json:"qps,omitempty"`
	QPSs     []float64              `json:"qpss,omitempty"`
	Times    int                    `json:"times,omitempty"`
	Duration int                    `json:"duration,omitempty"`
	Data     map[string]interface{} `json:"data,omitempty"`
}

type AliasMethod struct {
	prob  []float64
	alias []int
	r     *rand.Rand
}

type KeyGenerator struct {
	//mu           sync.Mutex       // 都是同线程调用，不用锁
	rkey  *rand.Rand				// 用于key生成
	rn    *rand.Rand				// 用于其他需要随机数生成，避免影响key生成顺序
	seeds []*rand.Rand				// 用于指定几率选择不同key按顺序生成
	alias *AliasMethod				// 别名采样法，用于快速均匀按几率选择
}

// https://blog.csdn.net/qq_43391414/article/details/123838629
func NewAliasMethod(seed int64, weights []float64) *AliasMethod {
	n := len(weights)
	prob := make([]float64, n)
	alias := make([]int, n)
	if seed == 0 {
		seed = time.Now().UnixNano()
	}

	// 计算总和
	sum := 0.0
	for _, w := range weights {
		sum += w
	}

	// 归一化
	scaled := make([]float64, n)
	for i, w := range weights {
		scaled[i] = w * float64(n) / sum
	}

	// 分类
	small := []int{}
	large := []int{}

	for i, p := range scaled {
		if p < 1.0 {
			small = append(small, i)
		} else {
			large = append(large, i)
		}
		prob[i] = p
	}

	// 构建别名表
	for len(small) > 0 && len(large) > 0 {
		l := small[len(small)-1]
		small = small[:len(small)-1]

		g := large[len(large)-1]
		large = large[:len(large)-1]

		alias[l] = g
		prob[g] = prob[g] + prob[l] - 1.0

		if prob[g] < 1.0 {
			small = append(small, g)
		} else {
			large = append(large, g)
		}
	}
	return &AliasMethod{prob: prob, alias: alias, r: rand.New(rand.NewSource(seed))}
}

func (a *AliasMethod) Random() int {
    i := a.r.Intn(len(a.prob))
    if a.r.Float64() < a.prob[i] {
        return i
    }
    return a.alias[i]
}

func NewKeyGenerator(seed int64, seeds []float64) *KeyGenerator {
	var alias *AliasMethod = nil
	var rseeds []*rand.Rand = nil
	if len(seeds) > 0 {
		alias = NewAliasMethod(seed, seeds)
		rseeds = make([]*rand.Rand, len(seeds))
		for i := 0; i < len(seeds); i++ {
			rseeds[i] = rand.New(rand.NewSource(int64(i+1)))
		}
	}
	if seed == 0 {
		seed = time.Now().UnixNano()
	}

	return &KeyGenerator{
		rkey:  rand.New(rand.NewSource(seed)),
		rn:    rand.New(rand.NewSource(seed)),
		seeds: rseeds,
		alias: alias,
	}
}

func (kg *KeyGenerator) NextKey() string {
	// kg.mu.Lock()
	// defer kg.mu.Unlock()
	if kg.alias != nil {
		idx := kg.alias.Random()
		return fmt.Sprintf("%016x%016x", kg.seeds[idx].Uint64(), kg.seeds[idx].Uint64())
	}
	return fmt.Sprintf("%016x%016x", kg.rkey.Uint64(), kg.rkey.Uint64())
}

func (kg *KeyGenerator) NextIntn(num int) int {
	return kg.rn.Intn(num)
}

func smoothQPSs(qpss []float64) []float64 {
	result := make([]float64, len(qpss))
	copy(result, qpss)
	
	for {
		changed := false
		for i := 0; i < len(result); i++ {
			if result[i] == 0 {
				left, right := i-1, i+1
				for left >= 0 && result[left] == 0 {
					left--
				}
				for right < len(result) && result[right] == 0 {
					right++
				}
				
				leftVal := 0.0
				rightVal := 0.0
				if left >= 0 {
					leftVal = result[left]
				}
				if right < len(result) {
					rightVal = result[right]
				}
				
				if leftVal > 0 || rightVal > 0 {
					result[i] = (leftVal + rightVal) / 2
					changed = true
				}
			}
		}
		if !changed {
			break
		}
	}
	return result
}

func publishTask(ctx context.Context, rdb *redis.Client, prefix string, threads int, task Task) {
	totalTasks := task.Times
	if task.Duration > 0 {
		totalTasks = task.QPS * task.Duration
	}
	if task.Times > 0 && task.Duration > 0 {
		if task.Times < totalTasks {
			totalTasks = task.Times
		}
	}

	qpss := task.QPSs
	if len(qpss) > 0 {
		qpss = smoothQPSs(qpss)
	}

	startTime := time.Now()
	nextTime := startTime
	taskCount := 0

	keyGen := NewKeyGenerator(int64(task.Seed), task.Seeds)

	for taskCount < totalTasks {
		currentQPS := task.QPS
		if len(qpss) > 0 {
			elapsed := time.Since(startTime)
			hour := int(elapsed.Hours()) % 24
			currentQPS = int(float64(task.QPS) * qpss[hour])
		}

		if currentQPS == 0 {
			time.Sleep(time.Second)
			continue
		}

		batchSize := currentQPS / 100
		if batchSize == 0 {
			batchSize = 1
		}

		for i := 0; i < batchSize && taskCount < totalTasks; i++ {
			processedData := make(map[string]interface{})
			for k, v := range task.Data {
				if obj, ok := v.(map[string]interface{}); ok {
					r := int(obj["r"].(float64))
					hashVal := keyGen.NextIntn(r)
					newKey := fmt.Sprintf("%s%d", k, hashVal)
					processedData[newKey] = obj["len"]
				} else {
					processedData[k] = v
				}
			}
			
			queueKey := fmt.Sprintf("%s_q%d", prefix, taskCount%threads)
			taskData := map[string]interface{}{
				"action": task.Action,
				"key":    keyGen.NextKey(),
				"data":   processedData,
			}
			taskJSON, _ := json.Marshal(taskData)
			rdb.RPush(ctx, queueKey, taskJSON)
			taskCount++
		}

		nextTime = nextTime.Add(time.Millisecond * 10)
		sleepDuration := time.Until(nextTime)
		if sleepDuration > 0 {
			time.Sleep(sleepDuration)
		} else {
			nextTime = time.Now()
		}
	}
}

func processTraffic(ctx context.Context, rdb *redis.Client, prefix string, threads int, traffic interface{}) {
	switch v := traffic.(type) {
	case []interface{}:
		for _, item := range v {
			if arr, ok := item.([]interface{}); ok {
				var wg sync.WaitGroup
				for _, subItem := range arr {
					wg.Add(1)
					go func(t interface{}) {
						defer wg.Done()
						taskJSON, _ := json.Marshal(t)
						var task Task
						json.Unmarshal(taskJSON, &task)
						log.Printf("Publishing parallel task: action=%s, qps=%d\n", task.Action, task.QPS)
						publishTask(ctx, rdb, prefix, threads, task)
					}(subItem)
				}
				wg.Wait()
			} else {
				taskJSON, _ := json.Marshal(item)
				var task Task
				json.Unmarshal(taskJSON, &task)
				log.Printf("Publishing list task: action=%s, qps=%d\n", task.Action, task.QPS)
				publishTask(ctx, rdb, prefix, threads, task)
			}
		}
	case map[string]interface{}:
		taskJSON, _ := json.Marshal(v)
		var task Task
		json.Unmarshal(taskJSON, &task)
		log.Printf("Publishing task: action=%s, qps=%d\n", task.Action, task.QPS)
		publishTask(ctx, rdb, prefix, threads, task)
	}
}

func main() {
	redisAddr := flag.String("redis", "localhost:6379", "Redis address")
	prefix := flag.String("prefix", "dst", "Redis key prefix")
	configFile := flag.String("config", "config.json", "Config file path")
	trafficFile := flag.String("traffic", "traffic.json", "Traffic file path")
	flag.Parse()

	ctx := context.Background()
	rdb := redis.NewClient(&redis.Options{Addr: *redisAddr})

	// Load config
	configData, err := os.ReadFile(*configFile)
	if err != nil {
		log.Fatal(err)
	}
	var config Config
	json.Unmarshal(configData, &config)

	// Check and update config in Redis
	cfgKey := *prefix + "_cfg"
	existingCfg, _ := rdb.Get(ctx, cfgKey).Result()
	if existingCfg != string(configData) {
		rdb.Set(ctx, cfgKey, configData, 0)
		rdb.Publish(ctx, *prefix+"_notify", "update_config")
		log.Println("Config updated and notification sent")
	}

	// Load traffic
	trafficData, err := os.ReadFile(*trafficFile)
	if err != nil {
		log.Fatal(err)
	}
	var traffic interface{}
	json.Unmarshal(trafficData, &traffic)

	processTraffic(ctx, rdb, *prefix, config.Threads, traffic)

	log.Println("All tasks published")
}
