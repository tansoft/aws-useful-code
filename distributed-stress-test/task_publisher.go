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
	"sync/atomic"
	"time"
	"strings"
	"strconv"
	"runtime/pprof"

	"github.com/redis/go-redis/v9"
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

func (kg *KeyGenerator) NextKeyB(b []byte) {
	tmp := make([]byte, 16)
	if kg.alias != nil {
		idx := kg.alias.Random()
		kg.seeds[idx].Read(tmp)
	} else {
		kg.rkey.Read(tmp)
	}
	hex.Encode(b, tmp)
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
	//mu          sync.Mutex
	currentTask string
	totalTasks  int
	finish      int64
	qps         int
	startTime   time.Time
	
	// 使用 atomic 避免锁
	jsonCount     int64
	batchCount    int64
	redisCount    int64
}

func (s *Stats) Update(task string, total, qps int, reset bool) {
	s.currentTask = task
	s.totalTasks = total
	s.qps = qps
	if reset {
		s.finish = 0
	}
}

func (s *Stats) AddJson(n int) {
	atomic.AddInt64(&s.jsonCount, int64(n))
}

func (s *Stats) AddBatch(n int) {
	atomic.AddInt64(&s.batchCount, int64(n))
}

func (s *Stats) AddRedis(n int) {
	atomic.AddInt64(&s.redisCount, int64(n))
}

func (s *Stats) Get() (string, int64, int, int, time.Duration, int64, int64, int64) {
	json := atomic.SwapInt64(&s.jsonCount, 0)
	batch := atomic.SwapInt64(&s.batchCount, 0)
	redis := atomic.SwapInt64(&s.redisCount, 0)
	s.finish += redis
	
	return s.currentTask, s.finish, s.totalTasks, s.qps, time.Since(s.startTime), json, batch, redis
}

func statsMonitor(ctx context.Context, rdb redis.UniversalClient, prefix string, threads int, stats *Stats) {
	ticker := time.NewTicker(time.Second)
	defer ticker.Stop()
	
	// 订阅 worker 上报的状态
	pubsub := rdb.Subscribe(ctx, prefix+"_stats")
	defer pubsub.Close()
	
	workerStats := make(map[string]map[string]interface{})
	var mu sync.Mutex

	// 接收 worker 状态
	go func() {
		for msg := range pubsub.Channel() {
			var data map[string]interface{}
			if err := json.Unmarshal([]byte(msg.Payload), &data); err == nil {
				mu.Lock()
				workerID := data["worker_id"].(string)
				workerStats[workerID] = data
				mu.Unlock()
			}
		}
	}()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			task, count, total, qps, elapsed, json, batch, redis := stats.Get()
			
			queueLengths := make([]int64, threads)
			var totalQueued int64
			for i := 0; i < threads; i++ {
				queueKey := fmt.Sprintf("%s_q%d", prefix, i)
				length, _ := rdb.LLen(ctx, queueKey).Result()
				length = length/1000
				queueLengths[i] = length
				totalQueued += length
			}
			
			remaining := int64(total) - count
			if len(task) > 0 {
				// remain->[Json/Batch/Redis]->done
				log.Printf("T:%s %s %dk->[%d/%d/%dk]->%dk QPS:%dk Q:%dk%v",
					elapsed.Round(time.Second), task, remaining/1000, json/1000, batch/1000, redis/1000, count/1000,
					qps/1000, totalQueued, queueLengths)
			}
			
			// 打印 worker 状态
			mu.Lock()
			for workerID, data := range workerStats {
				log.Printf("W:%s P:%v U:%v G:%v GS:%v D:%v Q:%v BG:%v BP:%v E:%v T:%v Q:%v",
					workerID, data["put"], data["update"], data["get"], data["get_sub"], data["delete"], 
					data["query"], data["batch_get"], data["batch_put"], data["errors"], 
					data["total"], data["queued"])
			}
			workerStats = make(map[string]map[string]interface{}) // 清空，等待下一秒数据
			mu.Unlock()
		}
	}
}

const placeholderID = "ABCDEF0123456789ABCDEF0123456789"

func generateValue(task Task, keyGen *KeyGenerator, init bool) []byte {
	var taskData map[string]interface{}
	if task.Action == "batchGetItem" || task.Action == "batchPutItem" {
		taskData = map[string]interface{}{
			"action": task.Action,
		}
	} else {
		var key string
		if init {
			key = placeholderID
		} else {
			key = keyGen.NextKey()
		}
		taskData = map[string]interface{}{
			"action": task.Action,
			"key":    key,
		}
	}
	// 根据不同的 action 生成不同的数据结构
	switch task.Action {
	case "putItem", "updateItem", "getSubItem":
		processedData := make(map[string]interface{})
		for k, v := range task.Data {
			if obj, ok := v.(map[string]interface{}); ok {
				r := int(obj["r"].(float64))
				newKey := keyGen.NextKeyIntn(k, r)
				processedData[newKey] = obj["len"]
			} else {
				processedData[k] = v
			}
		}
		taskData["data"] = processedData

	case "getItem", "deleteItem", "query":
		// 只需要 key，不需要 data

	case "batchGetItem":
		// 使用 samples 字段指定批量大小
		batchSize := task.Samples
		if batchSize == 0 {
			batchSize = 10 // 默认批量大小
		}
		keys := make([]string, batchSize)
		for i := 0; i < batchSize; i++ {
			if init {
				keys[i] = placeholderID
			} else {
				keys[i] = keyGen.NextKey()
			}
		}
		taskData["items"] = keys
		
	case "batchPutItem":
		// 使用 samples 字段指定批量大小
		batchSize := task.Samples
		if batchSize == 0 {
			batchSize = 10 // 默认批量大小
		}
		items := make(map[string]map[string]interface{})
		for i := 0; i < batchSize; i++ {
			var itemKey string
			if init {
				itemKey = placeholderID
			} else {
				itemKey = keyGen.NextKey()
			}
			processedData := make(map[string]interface{})
			for k, v := range task.Data {
				if obj, ok := v.(map[string]interface{}); ok {
					r := int(obj["r"].(float64))
					newKey := keyGen.NextKeyIntn(k, r)
					processedData[newKey] = obj["len"]
				} else {
					processedData[k] = v
				}
			}
			items[itemKey] = processedData
		}
		taskData["items"] = items
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

func publishTask(ctx context.Context, rdb redis.UniversalClient, prefix string, threads int, task Task, stats *Stats, debug bool) {
	totalTasks := task.Times
	var endTime time.Time
	if task.Duration > 0 {
		endTime = time.Now().Add(time.Duration(task.Duration) * time.Second)
		if task.Times == 0 {
			totalTasks = task.QPS * task.Duration
		}
	} else {
		endTime = time.Now().Add(time.Duration(100) * 365 * 86400 * time.Second)
	}

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

	var samples [][]byte = nil
	var samples_keypos []int = nil
	// batchGetItem/batchPutItem 模式下，Data都全新生成不提前造数据，相当于putItem不指定samples参数生成的效果。
	if task.Samples != 0 && task.Action != "batchGetItem" && task.Action != "batchPutItem" {
		samples = make([][]byte, task.Samples)
		samples_keypos = make([]int, task.Samples)
		for i := 0; i < task.Samples; i++ {
			samples[i] = generateValue(task, keyGen, true)
			samples_keypos[i] = strings.Index(string(samples[i]), placeholderID)
		}
	}

	runQPS := task.QPS
	var batchIntval,jsonBuffer,batchBuffer,taskIntval,redisThread int

	if runQPS > 100000 {
		batchIntval = 100
		jsonBuffer = 30
		batchBuffer = 80
		taskIntval = 160000
		redisThread = 30
	} else {
		batchIntval = 10
		jsonBuffer = 3
		batchBuffer = 3
		taskIntval = 1000
		redisThread = 5
	}

	if stats != nil {
		stats.Update(task.Action, totalTasks, runQPS, true)
	}

	jsonChan := make(chan *taskItem, jsonBuffer)
	batchChan := make(chan *taskBatch, batchBuffer)
	
	var batchWg sync.WaitGroup  // 打包线程
	var sendWg sync.WaitGroup   // 发送线程

	// 批量打包线程
	batchWg.Add(1)
	go func() {
		defer batchWg.Done()
		batch := &taskBatch{tasks: make([]taskItem, 0, taskIntval)}
		
		for item := range jsonChan {
			batch.tasks = append(batch.tasks, *item)
			if len(batch.tasks) >= taskIntval {
				batchChan <- batch
				if stats != nil {
					stats.AddBatch(len(batch.tasks))
				}
				batch = &taskBatch{tasks: make([]taskItem, 0, taskIntval)}
			}
		}
		
		if len(batch.tasks) > 0 {
			batchChan <- batch
			if stats != nil {
				stats.AddBatch(len(batch.tasks))
			}
		}
	}()
	
	// 等待打包线程结束后关闭 batchChan
	go func() {
		batchWg.Wait()
		close(batchChan)
	}()

	// Redis发送线程池
	for i := 0; i < redisThread; i++ {
		sendWg.Add(1)
		go func() {
			defer sendWg.Done()
			queueMap := make(map[string][]interface{}, threads)
			for batch := range batchChan {
				for k := range queueMap {
					queueMap[k] = queueMap[k][:0]
				}
				for _, item := range batch.tasks {
					if debug {
						fmt.Println(item.queueKey, string(item.data))
					}
					queueMap[item.queueKey] = append(queueMap[item.queueKey], item.data)
				}
				pipe := rdb.Pipeline()
				for qkey, items := range queueMap {
					if len(items) > 0 {
						if err := pipe.RPush(ctx, qkey, items...).Err(); err != nil {
							log.Printf("RPush error for %s: %v", qkey, err)
						}
					}
				}
				_, _ = pipe.Exec(ctx)
				if stats != nil {
					stats.AddRedis(len(batch.tasks))
				}
			}
		}()
	}

	// 主线程: 数据生成
	taskCounter := 0
	startTime := time.Now()
	nextTime := startTime
	lastHour := -1
	threadIdx := 0
	var i int

	for {
		if nextTime.After(endTime) || taskCounter >= totalTasks {
			break
		}
		if len(qpss) > 0 {
			hour := int(nextTime.Hour()) % 24
			if hour != lastHour {
				lastHour = hour
				runQPS = int(float64(task.QPS) * qpss[hour])
				if task.Times == 0 {
					totalTasks = runQPS * task.Duration
				}
				if stats != nil {
					stats.Update(task.Action, totalTasks, runQPS, false)
				}
			}
		}

		batchSize := runQPS / batchIntval
		if batchSize == 0 {
			batchSize = 1
		}

		for i = 0; i < batchSize && taskCounter < totalTasks; i++ {
			taskCounter++
			var b []byte
			if samples != nil {
				hashVal := keyGen.NextIntn(len(samples))
				sample := samples[hashVal]
				keypos := samples_keypos[hashVal]
				
				b = make([]byte, len(sample))
				copy(b, sample)
				keyGen.NextKeyB(b[keypos:keypos+32])
			} else {
				b = generateValue(task, keyGen, false)
			}
			jsonChan <- &taskItem{
				queueKey: queueKeys[threadIdx],
				data:     b,
			}
			
			threadIdx++
			if threadIdx >= threads {
				threadIdx = 0
			}
		}
		if stats != nil {
			stats.AddJson(i)
		}

		nextTime = nextTime.Add(time.Millisecond * 10)
		sleepDuration := time.Until(nextTime)
		if sleepDuration > 0 {
			time.Sleep(sleepDuration)
		}
	}
	
	close(jsonChan)
	sendWg.Wait()
	if stats != nil {
		// for final print
		time.Sleep(1 * time.Second)
	}
}

func processTraffic(ctx context.Context, rdb redis.UniversalClient, prefix string, threads int, traffic interface{}, stats *Stats, debug bool) {
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
						publishTask(ctx, rdb, prefix, threads, task, stats, debug)
					}(subItem)
				}
				wg.Wait()
			} else {
				taskJSON, _ := json.Marshal(item)
				var task Task
				json.Unmarshal(taskJSON, &task)
				log.Printf("Publishing list task: action=%s, qps=%d\n", task.Action, task.QPS)
				publishTask(ctx, rdb, prefix, threads, task, stats, debug)
			}
		}
	case map[string]interface{}:
		taskJSON, _ := json.Marshal(v)
		var task Task
		json.Unmarshal(taskJSON, &task)
		log.Printf("Publishing task: action=%s, qps=%d\n", task.Action, task.QPS)
		publishTask(ctx, rdb, prefix, threads, task, stats, debug)
	}
}

func main() {
	redisAddr := flag.String("redis", "localhost:6379", "Redis address")
	prefix := flag.String("prefix", "dst", "Redis key prefix")
	configFile := flag.String("config", "config.json", "Config file path")
	trafficFile := flag.String("traffic", "traffic.json", "Traffic file path")
	enableStats := flag.Bool("stats", false, "Enable stats monitoring")
	enableTLS := flag.Bool("tls", false, "Enable TLS connection to Redis")
	debug := flag.Bool("debug", false, "Enable debug logging")
	flag.Parse()

	ctx := context.Background()
	var rdb redis.UniversalClient
	
	// 自动检测集群模式
	if strings.Contains(*redisAddr, "cluster") {
		opts := &redis.ClusterOptions{
			Addrs: []string{*redisAddr},
		}
		if *enableTLS {
			opts.TLSConfig = &tls.Config{MinVersion: tls.VersionTLS12}
		}
		rdb = redis.NewClusterClient(opts)
	} else {
		opts := &redis.Options{
			Addr: *redisAddr,
		}
		if *enableTLS {
			opts.TLSConfig = &tls.Config{MinVersion: tls.VersionTLS12}
		}
		rdb = redis.NewClient(opts)
	}

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

	// 预热：触发 GC 和 JIT 优化
	log.Println("Warming up...")
	time.Sleep(2 * time.Second)

	f, _ := os.Create("cpu.prof")
    defer f.Close()
    // 开始 CPU 分析
    pprof.StartCPUProfile(f)
    defer pprof.StopCPUProfile()

	// performanceTest()

	processTraffic(ctx, rdb, *prefix, config.Threads, traffic, stats, *debug)

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