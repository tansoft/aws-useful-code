package main

import (
	"context"
	"crypto/tls"
	"flag"
	"fmt"
	"log"
	"os/exec"
	"strings"
	"sync"
	"sync/atomic"
	"time"

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
	updateCount int64
	queryCount  int64
	errorCount  int64
	startTime   time.Time
}

func (s *WorkerStats) AddUpdate() {
	atomic.AddInt64(&s.updateCount, 1)
}

func (s *WorkerStats) AddQuery() {
	atomic.AddInt64(&s.queryCount, 1)
}

func (s *WorkerStats) AddError() {
	atomic.AddInt64(&s.errorCount, 1)
}

func (s *WorkerStats) Get() (int64, int64, int64, time.Duration) {
	return atomic.SwapInt64(&s.updateCount, 0),
		atomic.SwapInt64(&s.queryCount, 0),
		atomic.SwapInt64(&s.errorCount, 0),
		time.Since(s.startTime)
}

type Worker struct {
	rdb    redis.UniversalClient
	prefix string
	config Config
	db     Database
	stats  *WorkerStats
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
	if !ok && action != "batchGetItem" && action != "batchPutItem" {
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
		err = w.db.PutItem(key, data)
	case "updateItem":
		data := task["data"].(map[string]interface{})
		err = w.db.UpdateItem(key, data)
	case "getItem":
		_, err = w.db.GetItem(key)
	case "deleteItem":
		err = w.db.DeleteItem(key)
	case "query":
		err = w.db.Query(key)
	case "batchGetItem":
		if keys, ok := task["keys"].([]interface{}); ok {
			keyStrs := make([]string, len(keys))
			for i, k := range keys {
				keyStrs[i] = k.(string)
			}
			_, err = w.db.BatchGetItem(keyStrs)
		}
	case "batchPutItem":
		if items, ok := task["items"].(map[string]interface{}); ok {
			itemsMap := make(map[string]map[string]interface{})
			for k, v := range items {
				itemsMap[k] = v.(map[string]interface{})
			}
			err = w.db.BatchPutItem(itemsMap)
		}
	}

	if err != nil {
		log.Printf("[ERROR] Action %s failed for key %s: %v", action, key, err)
		if w.stats != nil {
			w.stats.AddError()
		}
	} else if w.stats != nil {
		w.stats.AddUpdate()
	}
}

func (w *Worker) startWorker(ctx context.Context, threadID int, wg *sync.WaitGroup) {
	defer wg.Done()
	queueKey := w.prefix + "_q" + fmt.Sprintf("%d", threadID)
	
	const batchSize = 100
	const concurrency = 50
	taskChan := make(chan map[string]interface{}, batchSize*2)
	
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
			pipe := w.rdb.Pipeline()
			for i := 0; i < batchSize; i++ {
				pipe.LPop(ctx, queueKey)
			}
			cmds, _ := pipe.Exec(ctx)
			
			processed := 0
			for _, cmd := range cmds {
				if result, err := cmd.(*redis.StringCmd).Result(); err == nil {
					var task map[string]interface{}
					if sonic.UnmarshalString(result, &task) == nil {
						taskChan <- task
						processed++
					}
				}
			}
			
			if processed == 0 {
				result, err := w.rdb.BLPop(ctx, time.Second, queueKey).Result()
				if err == nil && len(result) > 1 {
					var task map[string]interface{}
					if sonic.UnmarshalString(result[1], &task) == nil {
						taskChan <- task
					}
				}
			}
		}
	}
}

func (w *Worker) handleNotify(ctx context.Context) {
	pubsub := w.rdb.Subscribe(ctx, w.prefix+"_notify")
	defer pubsub.Close()

	for msg := range pubsub.Channel() {
		switch msg.Payload {
		case "update_config":
			cfgData, _ := w.rdb.Get(ctx, w.prefix+"_cfg").Result()
			sonic.UnmarshalString(cfgData, &w.config)
			log.Println("Config updated")
		case "execute_bash":
			// Execute bash command (implement as needed)
		case "reboot_instance":
			exec.Command("sudo", "reboot").Run()
		case "terminate_instance":
			// Implement instance termination
		}
	}
}

func statsMonitor(ctx context.Context, rdb redis.UniversalClient, prefix string, threads int, stats *WorkerStats) {
	ticker := time.NewTicker(time.Second)
	defer ticker.Stop()
	
	hostname, _ := exec.Command("hostname").Output()
	workerID := strings.TrimSpace(string(hostname))

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			updates, queries, errors, elapsed := stats.Get()
			
			queueLengths := make([]int64, threads)
			var totalQueued int64
			for i := 0; i < threads; i++ {
				queueKey := fmt.Sprintf("%s_q%d", prefix, i)
				length, _ := rdb.LLen(ctx, queueKey).Result()
				queueLengths[i] = length
				totalQueued += length
			}
			
			total := updates + queries
			
			// 上报到 Redis
			statsData := map[string]interface{}{
				"worker_id": workerID,
				"updates":   updates,
				"queries":   queries,
				"errors":    errors,
				"total":     total,
				"queued":    totalQueued,
				"queues":    queueLengths,
				"elapsed":   int64(elapsed.Seconds()),
				"timestamp": time.Now().Unix(),
			}
			statsJSON, _ := sonic.MarshalString(statsData)
			rdb.Publish(ctx, prefix+"_stats", statsJSON)
			
			log.Printf("[STATS] Update:%d Query:%d Err:%d Total:%d Q:%d%v T:%s",
				updates, queries, errors, total, totalQueued, queueLengths, elapsed.Round(time.Second))
		}
	}
}

func main() {
	redisAddr := flag.String("redis", "localhost:6379", "Redis address")
	prefix := flag.String("prefix", "dst", "Redis key prefix")
	dbType := flag.String("db", "dynamodb", "Database type: dynamodb or redis")
	useTLS := flag.Bool("tls", false, "Use TLS for Redis connection")
	enableStats := flag.Bool("stats", false, "Enable stats monitoring")
	flag.Parse()

	ctx := context.Background()
	var rdb redis.UniversalClient
	
	// 自动检测集群模式
	if strings.Contains(*redisAddr, "cluster") {
		opts := &redis.ClusterOptions{
			Addrs: []string{*redisAddr},
		}
		if *useTLS {
			opts.TLSConfig = &tls.Config{MinVersion: tls.VersionTLS12}
		}
		rdb = redis.NewClusterClient(opts)
	} else {
		opts := &redis.Options{
			Addr: *redisAddr,
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

	var stats *WorkerStats
	if *enableStats {
		stats = &WorkerStats{startTime: time.Now()}
		go statsMonitor(ctx, rdb, *prefix, config.Threads, stats)
	}

	worker := &Worker{rdb: rdb, prefix: *prefix, config: config, db: db, stats: stats}

	go worker.handleNotify(ctx)

	var wg sync.WaitGroup
	for i := 0; i < config.Threads; i++ {
		wg.Add(1)
		go worker.startWorker(ctx, i, &wg)
	}

	log.Printf("Worker started with %d threads, db=%s\n", config.Threads, *dbType)
	wg.Wait()
}
