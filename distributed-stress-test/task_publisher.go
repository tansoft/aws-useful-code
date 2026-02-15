package main

import (
	"context"
	"crypto/tls"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"math/rand"
	"encoding/hex"
	"os"
	"sync"
	"time"
	"strings"
	"strconv"
	"runtime/pprof"

	"github.com/go-redis/redis/v8"
	"github.com/bytedance/sonic"
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
	Samples  int                    `json:"samples,omitempty"`
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
	b := make([]byte, 16)
	if kg.alias != nil {
		idx := kg.alias.Random()
		kg.seeds[idx].Read(b)
	} else {
	    kg.rkey.Read(b)
	}
    return hex.EncodeToString(b)
	//使用 Read(b) 500万次 346.519896ms，使用fmt 500万次 886.121717ms
	// return fmt.Sprintf("%016x%016x", kg.rkey.Uint64(), kg.rkey.Uint64())
}

func (kg *KeyGenerator) NextIntn(num int) int {
	return kg.rn.Intn(num)
}

// 运行 500万次 219.649664ms
func (kg *KeyGenerator) NextKeyIntn(k string, num int) string {
    hashVal := kg.rn.Intn(num)
    // 预估容量避免扩容
    result := make([]byte, 0, len(k)+10)
    result = append(result, k...)
    result = strconv.AppendInt(result, int64(hashVal), 10)
    return string(result)
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

type Stats struct {
	mu          sync.Mutex
	currentTask string
	taskCount   int
	lastTaskCount int
	totalTasks  int
	qps         int
	startTime   time.Time
}

func (s *Stats) Update(task string, count, total, qps int) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.currentTask = task
	s.taskCount = count
	s.totalTasks = total
	s.qps = qps
}

func (s *Stats) Get() (string, int, int, int, int, time.Duration) {
	s.mu.Lock()
	defer s.mu.Unlock()
	lastTaskCount := s.lastTaskCount
	s.lastTaskCount = s.taskCount
	return s.currentTask, s.taskCount, lastTaskCount, s.totalTasks, s.qps, time.Since(s.startTime)
}

func statsMonitor(ctx context.Context, rdb redis.UniversalClient, prefix string, threads int, stats *Stats) {
	ticker := time.NewTicker(time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			task, count, last, total, qps, elapsed := stats.Get()
			
			queueLengths := make([]int64, threads)
			var totalQueued int64
			for i := 0; i < threads; i++ {
				queueKey := fmt.Sprintf("%s_q%d", prefix, i)
				length, _ := rdb.LLen(ctx, queueKey).Result()
				queueLengths[i] = length
				totalQueued += length
			}
			
			remaining := total - count
			log.Printf("[STATS] %s | Pub:%d Rem:%d QPS:%d/%d Q:%d%v T:%s",
				task, count, remaining, count-last, qps, totalQueued, queueLengths, elapsed.Round(time.Second))
		}
	}
}

const placeholderID = "ABCDEF0123456789ABCDEF0123456789"

func generateValue(task Task, keyGen *KeyGenerator, init bool) []byte {
	processedData := make(map[string]interface{})
	for k, v := range task.Data {
		if obj, ok := v.(map[string]interface{}); ok {
			r := int(obj["r"].(float64))
			//hashVal := keyGen.NextIntn(r)
			//newKey := fmt.Sprintf("%s%d", k, hashVal)
			newKey := keyGen.NextKeyIntn(k, r)
			processedData[newKey] = obj["len"]
		} else {
			processedData[k] = v
		}
	}
	var key string
	if init {
		key = placeholderID
	} else {
		key = keyGen.NextKey()
	}
	taskData := map[string]interface{}{
		"action": task.Action,
		"key":    key,
		"data":   processedData,
	}
	taskJSON, _ := sonic.Marshal(taskData)
	return taskJSON
}

type taskBatch struct {
	tasks []taskItem
}

type taskItem struct {
	queueKey string
	data     []byte
}

func publishTask(ctx context.Context, rdb redis.UniversalClient, prefix string, threads int, task Task, stats *Stats) {
	totalTasks := task.Times
	if task.Duration > 0 {
		//fixme，这里如果是流量曲线图会不准，改为判断时间会好一点
		totalTasks = task.QPS * task.Duration
	}
	if task.Times > 0 && task.Duration > 0 {
		if task.Times < totalTasks {
			totalTasks = task.Times
		}
	}

	currentQPS := task.QPS
	qpss := task.QPSs
	if len(qpss) > 0 {
		qpss = smoothQPSs(qpss)
		fmt.Println(qpss)
	}

	queueKeys := make([]string, threads)
	for i := 0; i < threads; i++ {
		queueKeys[i] = fmt.Sprintf("%s_q%d", prefix, i)
	}

	keyGen := NewKeyGenerator(int64(task.Seed), task.Seeds)

	var samples []string = nil
	var samples_keypos []int = nil
	if task.Samples != 0 {
		samples = make([]string, task.Samples)
		samples_keypos = make([]int, task.Samples)
		for i := 0; i < task.Samples; i++ {
			samples[i] = string(generateValue(task, keyGen, true))
			samples_keypos[i] = strings.Index(samples[i], placeholderID)
		}
	}

	dataChan := make(chan *taskBatch, 1000)
	var wg sync.WaitGroup

	// 多个Redis发送线程（并发发送）
	numSenders := 20
	for i := 0; i < numSenders; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for batch := range dataChan {
				pipe := rdb.Pipeline()
				for _, item := range batch.tasks {
					pipe.RPush(ctx, item.queueKey, item.data)
				}
				_, _ = pipe.Exec(ctx)
			}
		}()
	}

	// 数据生成线程
	startTime := time.Now()
	nextTime := startTime
	taskCount := 0

	for taskCount < totalTasks {
		if len(qpss) > 0 {
			elapsed := time.Since(startTime)
			if elapsed > time.Minute {
				startTime = time.Now()
				hour := int(elapsed.Hours()) % 24
				currentQPS = int(float64(task.QPS) * qpss[hour])
				fmt.Println("Change QPS:", currentQPS)
			}
		}

		batchSize := currentQPS / 10
		if batchSize == 0 {
			batchSize = 1
		}

		batch := &taskBatch{tasks: make([]taskItem, 0, batchSize)}
		for i := 0; i < batchSize && taskCount < totalTasks; i++ {
			var taskJSON []byte
			if samples != nil {
				hashVal := keyGen.NextIntn(len(samples))
				// 这里更高效做法是直接转byte b := []byte(samples[hashVal]) 不用make和copy，只copy NextKey就行
				b := make([]byte, len(samples[hashVal]))
				copy(b, samples[hashVal])
				copy(b[samples_keypos[hashVal]:], keyGen.NextKey())
				taskJSON = b
			} else {
				taskJSON = generateValue(task, keyGen, false)
			}
			batch.tasks = append(batch.tasks, taskItem{
				queueKey: queueKeys[taskCount%threads],
				data:     taskJSON,
			})
			taskCount++
		}
		if stats != nil {
			stats.Update(task.Action, taskCount, totalTasks, currentQPS)
		}
		dataChan <- batch

		nextTime = nextTime.Add(time.Millisecond * 10)
		sleepDuration := time.Until(nextTime)
		//如果性能赶不上，就不sleep了
		if sleepDuration > 0 {
			fmt.Println("sleep", sleepDuration, taskCount)
			time.Sleep(sleepDuration)
		}
	}

	close(dataChan)
	wg.Wait()
}

func processTraffic(ctx context.Context, rdb redis.UniversalClient, prefix string, threads int, traffic interface{}, stats *Stats) {
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
						publishTask(ctx, rdb, prefix, threads, task, stats)
					}(subItem)
				}
				wg.Wait()
			} else {
				taskJSON, _ := json.Marshal(item)
				var task Task
				json.Unmarshal(taskJSON, &task)
				log.Printf("Publishing list task: action=%s, qps=%d\n", task.Action, task.QPS)
				publishTask(ctx, rdb, prefix, threads, task, stats)
			}
		}
	case map[string]interface{}:
		taskJSON, _ := json.Marshal(v)
		var task Task
		json.Unmarshal(taskJSON, &task)
		log.Printf("Publishing task: action=%s, qps=%d\n", task.Action, task.QPS)
		publishTask(ctx, rdb, prefix, threads, task, stats)
	}
}

func main() {
	redisAddr := flag.String("redis", "localhost:6379", "Redis address")
	prefix := flag.String("prefix", "dst", "Redis key prefix")
	configFile := flag.String("config", "config.json", "Config file path")
	trafficFile := flag.String("traffic", "traffic.json", "Traffic file path")
	enableStats := flag.Bool("stats", false, "Enable stats monitoring")
	enableTLS := flag.Bool("tls", false, "Enable TLS connection to Redis")
	flag.Parse()

	ctx := context.Background()
	opts := &redis.UniversalOptions{Addrs: []string{*redisAddr}}
	if *enableTLS {
		opts.TLSConfig = &tls.Config{MinVersion: tls.VersionTLS12}
	}
	rdb := redis.NewUniversalClient(opts)

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

	var stats *Stats
	if *enableStats {
		stats = &Stats{startTime: time.Now()}
		go statsMonitor(ctx, rdb, *prefix, config.Threads, stats)
	}

	f, _ := os.Create("cpu.prof")
    defer f.Close()
    // 开始 CPU 分析
    pprof.StartCPUProfile(f)
    defer pprof.StopCPUProfile()

	// performanceTest()

	processTraffic(ctx, rdb, *prefix, config.Threads, traffic, stats)

	log.Println("All tasks published")
}

func timeTrack(start time.Time, name string) {
    elapsed := time.Since(start)
    fmt.Printf("%s took %s\n", name, elapsed)
}

//go tool pprof cpu.prof
// (pprof) top10
// (pprof) list publishTask
func performanceTest() {
	defer timeTrack(time.Now(), "expensiveFunc")

	keyGen := NewKeyGenerator(int64(1), nil)
	for i:=0;i<5000000;i++ {
		_ = keyGen.NextKeyIntn("keyd", 16)
	}
}