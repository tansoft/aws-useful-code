package main

import (
	"context"
	"crypto/tls"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"os/exec"
	"strings"
	"sync"
	"time"

	"github.com/redis/go-redis/v9"
)

type Config struct {
	TableName  string `json:"table_name"`
	Region     string `json:"region"`
	Threads    int    `json:"threads"`
	DBType     string `json:"db_type,omitempty"`
	RedisAddr  string `json:"redis_addr,omitempty"`
}

type Worker struct {
	rdb    redis.UniversalClient
	prefix string
	config Config
	db     Database
}

func (w *Worker) processTask(task map[string]interface{}) {
	action := task["action"].(string)
	key := task["key"].(string)
	data := task["data"].(map[string]interface{})

	switch action {
	case "updateItem":
		w.db.UpdateItem(key, data)
	case "query":
		w.db.Query(key)
	}
}

func (w *Worker) startWorker(ctx context.Context, threadID int, wg *sync.WaitGroup) {
	defer wg.Done()
	queueKey := w.prefix + "_q" + fmt.Sprintf("%d", threadID)

	for {
		select {
		case <-ctx.Done():
			return
		default:
			result, err := w.rdb.BLPop(ctx, time.Second, queueKey).Result()
			if err == nil && len(result) > 1 {
				var task map[string]interface{}
				json.Unmarshal([]byte(result[1]), &task)
				w.processTask(task)
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
			json.Unmarshal([]byte(cfgData), &w.config)
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

func main() {
	redisAddr := flag.String("redis", "localhost:6379", "Redis address")
	prefix := flag.String("prefix", "dst", "Redis key prefix")
	dbType := flag.String("db", "dynamodb", "Database type: dynamodb or redis")
	useTLS := flag.Bool("tls", false, "Use TLS for Redis connection")
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
	json.Unmarshal([]byte(cfgData), &config)

	db, err := NewDatabase(*dbType, config.Region, config.TableName)
	if err != nil {
		log.Fatal(err)
	}
	defer db.Close()

	worker := &Worker{rdb: rdb, prefix: *prefix, config: config, db: db}

	go worker.handleNotify(ctx)

	var wg sync.WaitGroup
	for i := 0; i < config.Threads; i++ {
		wg.Add(1)
		go worker.startWorker(ctx, i, &wg)
	}

	log.Printf("Worker started with %d threads, db=%s\n", config.Threads, *dbType)
	wg.Wait()
}
