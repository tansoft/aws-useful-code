package main

import (
	"context"
	"crypto/tls"
	"flag"
	"fmt"
	"log"
	"os"
	"os/exec"
	"strings"
	"sync"
	"sync/atomic"
	"syscall"
	"time"
	"runtime/pprof"

	"github.com/bytedance/sonic"
	"github.com/redis/go-redis/v9"
)

type Config struct {
	TableName  string `json:"table_name"`
	Region     string `json:"region"`
	Threads    int    `json:"threads"`
	DBType     string `json:"db_type,omitempty"`
	RedisAddr  string `json:"redis_addr,omitempty"`
}

type WorkerStats struct {
	putCount       int64
	updateCount    int64
	getCount       int64
	getSubCount    int64
	deleteCount    int64
	batchGetCount  int64
	batchGetSubCount int64
	batchPutCount  int64
	errorCount     int64
	startTime      time.Time
}

func (s *WorkerStats) Add(action string) {
	switch action {
	case "putItem":
		atomic.AddInt64(&s.putCount, 1)
	case "updateItem":
		atomic.AddInt64(&s.updateCount, 1)
	case "getItem":
		atomic.AddInt64(&s.getCount, 1)
	case "getSubItem":
		atomic.AddInt64(&s.getSubCount, 1)
	case "deleteItem":
		atomic.AddInt64(&s.deleteCount, 1)
	case "batchGetItem":
		atomic.AddInt64(&s.batchGetCount, 1)
	case "batchGetSubItem":
		atomic.AddInt64(&s.batchGetSubCount, 1)
	case "batchPutItem":
		atomic.AddInt64(&s.batchPutCount, 1)
	}
}

func (s *WorkerStats) AddError() {
	atomic.AddInt64(&s.errorCount, 1)
}

func (s *WorkerStats) Get() (int64, int64, int64, int64, int64, int64, int64, int64, int64, time.Duration) {
	return atomic.SwapInt64(&s.putCount, 0),
		atomic.SwapInt64(&s.updateCount, 0),
		atomic.SwapInt64(&s.getCount, 0),
		atomic.SwapInt64(&s.getSubCount, 0),
		atomic.SwapInt64(&s.deleteCount, 0),
		atomic.SwapInt64(&s.batchGetCount, 0),
		atomic.SwapInt64(&s.batchGetSubCount, 0),
		atomic.SwapInt64(&s.batchPutCount, 0),
		atomic.SwapInt64(&s.errorCount, 0),
		time.Since(s.startTime)
}

type Worker struct {
	rdb    redis.UniversalClient
	prefix string
	config Config
	db     Database
	stats  *WorkerStats
	debug  bool
}

func (w *Worker) processTask(task map[string]interface{}) {
	action, ok := task["action"].(string)
	if !ok {
		log.Printf("[ERROR] Invalid action type: %+v", task)
		if w.stats != nil {
			w.stats.AddError()
		}
		return
	}
	
	key, ok := task["key"].(string)
	if !ok && action != "batchGetItem" && action != "batchGetSubItem" && action != "batchPutItem" {
		log.Printf("[ERROR] Invalid key type for action %s: %+v", action, task)
		if w.stats != nil {
			w.stats.AddError()
		}
		return
	}
	
	var err error
	switch action {
	case "putItem":
		data := task["data"].(map[string]interface{})
		if w.debug {
			log.Printf("[DEBUG] putItem key=%s data=%+v", key, data)
		}
		err = w.db.PutItem(key, data)
	case "updateItem":
		data := task["data"].(map[string]interface{})
		if w.debug {
			log.Printf("[DEBUG] updateItem key=%s data=%+v", key, data)
		}
		err = w.db.UpdateItem(key, data)
	case "getItem":
		if w.debug {
			log.Printf("[DEBUG] getItem key=%s", key)
		}
		result, err := w.db.GetItem(key)
		if w.debug {
			if err == nil {
				log.Printf("[DEBUG] getItem result=%+v", result)
			} else {
				log.Printf("[DEBUG] getItem error=%v", err)
			}
		}
	case "getSubItem":
		data := task["data"].(map[string]interface{})
		columns := make([]string, 0, len(data))
		for col := range data {
			columns = append(columns, col)
		}
		if w.debug {
			log.Printf("[DEBUG] getSubItem key=%s columns=%v", key, columns)
		}
		result, err := w.db.GetSubItem(key, columns)
		if w.debug {
			if err == nil {
				log.Printf("[DEBUG] getSubItem result=%+v", result)
			} else {
				log.Printf("[DEBUG] getSubItem error=%v", err)
			}
		}
	case "deleteItem":
		if w.debug {
			log.Printf("[DEBUG] deleteItem key=%s", key)
		}
		err = w.db.DeleteItem(key)
		if w.debug && err != nil {
			log.Printf("[DEBUG] deleteItem error=%v", err)
		}
	case "batchGetItem":
		if keys, ok := task["items"].([]interface{}); ok {
			keyStrs := make([]string, len(keys))
			for i, k := range keys {
				keyStrs[i] = k.(string)
			}
			if w.debug {
				log.Printf("[DEBUG] batchGetItem keys=%v", keyStrs)
			}
			result, err := w.db.BatchGetItem(keyStrs)
			if w.debug {
				if err == nil {
					log.Printf("[DEBUG] batchGetItem result=%+v", result)
				} else {
					log.Printf("[DEBUG] batchGetItem error=%v", err)
				}
			}
		}
	case "batchGetSubItem":
		if keys, ok := task["items"].([]interface{}); ok {
			keyStrs := make([]string, len(keys))
			for i, k := range keys {
				keyStrs[i] = k.(string)
			}
			data := task["data"].(map[string]interface{})
			columns := make([]string, 0, len(data))
			for col := range data {
				columns = append(columns, col)
			}
			if w.debug {
				log.Printf("[DEBUG] batchGetSubItem keys=%v columns=%v", keyStrs, columns)
			}
			result, err := w.db.BatchGetSubItem(keyStrs, columns)
			if w.debug {
				if err == nil {
					log.Printf("[DEBUG] batchGetSubItem result=%+v", result)
				} else {
					log.Printf("[DEBUG] batchGetSubItem error=%v", err)
				}
			}
		}
	case "batchPutItem":
		if items, ok := task["items"].(map[string]interface{}); ok {
			itemsMap := make(map[string]map[string]interface{})
			for k, v := range items {
				itemsMap[k] = v.(map[string]interface{})
			}
			if w.debug {
				log.Printf("[DEBUG] batchPutItem items=%+v", itemsMap)
			}
			err = w.db.BatchPutItem(itemsMap)
			if w.debug && err != nil {
				log.Printf("[DEBUG] batchPutItem error=%v", err)
			}
		}
	}

	if err != nil {
		if w.debug {
			log.Printf("[ERROR] Action %s failed for key %s: %v", action, key, err)
		}
		if w.stats != nil {
			w.stats.AddError()
		}
	} else if w.stats != nil {
		w.stats.Add(action)
	}
}

func (w *Worker) startWorker(ctx context.Context, threadID int, wg *sync.WaitGroup) {
	defer wg.Done()
	queueKey := w.prefix + "_q" + fmt.Sprintf("%d", threadID)
	
	const batchSize = 500
	const concurrency = 2000
	taskChan := make(chan map[string]interface{}, batchSize*10)
	
	// 并发处理协程池
	var procWg sync.WaitGroup
	for i := 0; i < concurrency; i++ {
		procWg.Add(1)
		go func() {
			defer procWg.Done()
			for task := range taskChan {
				w.processTask(task)
			}
		}()
	}

	for {
		select {
		case <-ctx.Done():
			close(taskChan)
			procWg.Wait()
			return
		default:
			results, err := w.rdb.LPopCount(ctx, queueKey, batchSize).Result()
			if err != nil || len(results) == 0 {
				time.Sleep(10 * time.Millisecond)
				continue
			}
			
			for _, result := range results {
				var task map[string]interface{}
				if sonic.UnmarshalString(result, &task) == nil {
					select {
					case taskChan <- task:
					case <-ctx.Done():
						close(taskChan)
						procWg.Wait()
						return
					}
				}
			}
		}
	}
}

func (w *Worker) handleNotify(ctx context.Context, cancel context.CancelFunc) {
	pubsub := w.rdb.Subscribe(ctx, w.prefix+"_notify")
	defer pubsub.Close()

	for msg := range pubsub.Channel() {
		switch msg.Payload {
		case "update_config":
			log.Println("Received update_config, restarting worker...")
			cmd := exec.Command(os.Args[0], os.Args[1:]...)
			cmd.Stdout = os.Stdout
			cmd.Stderr = os.Stderr
			cmd.Start()
			cancel()
			return
		case "stop":
			log.Println("Received stop, quit worker...")
			cancel()
			return
		case "execute_bash":
			// Execute bash command (implement as needed)
		case "reboot_instance":
			exec.Command("sudo", "reboot").Run()
		case "terminate_instance":
			syscall.Kill(os.Getpid(), syscall.SIGTERM)
		}
	}
}

func statsMonitor(ctx context.Context, rdb redis.UniversalClient, prefix string, threads int, stats *WorkerStats, debug bool) {
	ticker := time.NewTicker(time.Second)
	defer ticker.Stop()
	
	hostname, _ := exec.Command("hostname").Output()
	workerID := strings.TrimSpace(string(hostname))

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			put, update, get, getSub, del, batchGet, batchGetSub, batchPut, errors, elapsed := stats.Get()
			
			queueLengths := make([]int64, threads)
			var totalQueued int64
			for i := 0; i < threads; i++ {
				queueKey := fmt.Sprintf("%s_q%d", prefix, i)
				length, _ := rdb.LLen(ctx, queueKey).Result()
				queueLengths[i] = length
				totalQueued += length
			}
			
			total := put + update + get + getSub + del + batchGet + batchGetSub + batchPut
			
			// 上报到 Redis
			statsData := map[string]interface{}{
				"worker_id": workerID,
				"put":       put,
				"update":    update,
				"get":       get,
				"get_sub":   getSub,
				"delete":    del,
				"batch_get": batchGet,
				"batch_get_sub": batchGetSub,
				"batch_put": batchPut,
				"errors":    errors,
				"total":     total,
				"queued":    totalQueued,
				"queues":    queueLengths,
				"elapsed":   int64(elapsed.Seconds()),
				"timestamp": time.Now().Unix(),
			}
			statsJSON, _ := sonic.MarshalString(statsData)
			rdb.Publish(ctx, prefix+"_stats", statsJSON)
			
			log.Printf("T:%s P:%d U:%d G:%d GS:%d D:%d BG:%d BGS:%d BP:%d E:%d T:%d Q:%d%v",
				elapsed.Round(time.Second),
				put, update, get, getSub, del, batchGet, batchGetSub, batchPut, errors, total, totalQueued, queueLengths)
		}
	}
}

func main() {
	redisAddr := flag.String("redis", "localhost:6379", "Redis address")
	prefix := flag.String("prefix", "dst", "Redis key prefix")
	dbType := flag.String("db", "dynamodb", "Database type: dynamodb or redis")
	useTLS := flag.Bool("tls", false, "Use TLS for Redis connection")
	enableStats := flag.Bool("stats", false, "Enable stats monitoring")
	debug := flag.Bool("debug", false, "Enable debug logging")
	prof := flag.Bool("prof", false, "Enable CPU Prof")
	flag.Parse()

	ctx := context.Background()
	var rdb redis.UniversalClient
	
	// 自动检测集群模式
	if strings.Contains(*redisAddr, "cluster") {
		opts := &redis.ClusterOptions{
			Addrs:        []string{*redisAddr},
			PoolSize:     100,
			MinIdleConns: 20,
			DialTimeout:  30 * time.Second,
			ReadTimeout:  30 * time.Second,
			WriteTimeout: 30 * time.Second,
			PoolTimeout:  60 * time.Second,
		}
		if *useTLS {
			opts.TLSConfig = &tls.Config{MinVersion: tls.VersionTLS12}
		}
		rdb = redis.NewClusterClient(opts)
	} else {
		opts := &redis.Options{
			Addr:         *redisAddr,
			PoolSize:     100,
			MinIdleConns: 20,
			DialTimeout:  30 * time.Second,
			ReadTimeout:  30 * time.Second,
			WriteTimeout: 30 * time.Second,
			PoolTimeout:  60 * time.Second,
		}
		if *useTLS {
			opts.TLSConfig = &tls.Config{MinVersion: tls.VersionTLS12}
		}
		rdb = redis.NewClient(opts)
	}

	cfgData, err := rdb.Get(ctx, *prefix+"_cfg").Result()
	if err != nil {
		log.Fatal("Failed to get config from Redis")
	}
	var config Config
	sonic.UnmarshalString(cfgData, &config)

	db, err := NewDatabase(*dbType, config.Region, config.TableName)
	if err != nil {
		log.Fatal(err)
	}
	defer db.Close()
	log.Printf("Using database implementation: %s", db.GetImplName())

	var stats *WorkerStats
	if *enableStats {
		stats = &WorkerStats{startTime: time.Now()}
		go statsMonitor(ctx, rdb, *prefix, config.Threads, stats, *debug)
	}

	// CPU 性能分析
	if *prof {
		f, _ := os.Create("cpu.prof")
    	defer f.Close()
    	pprof.StartCPUProfile(f)
    	defer pprof.StopCPUProfile()
		// performanceTest()
	}

	worker := &Worker{rdb: rdb, prefix: *prefix, config: config, db: db, stats: stats, debug: *debug}

	ctx, cancel := context.WithCancel(ctx)
	defer cancel()

	go worker.handleNotify(ctx, cancel)

	var wg sync.WaitGroup
	for i := 0; i < config.Threads; i++ {
		wg.Add(1)
		go worker.startWorker(ctx, i, &wg)
	}

	log.Printf("Worker started with %d threads, db=%s\n", config.Threads, *dbType)
	wg.Wait()
}
