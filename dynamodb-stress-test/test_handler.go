package main

import (
	"context"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"log"
	"math/rand"
	"os"
	"sync"
	"sync/atomic"
	"time"

	"github.com/aws/aws-sdk-go-v2/config"
	"github.com/aws/aws-sdk-go-v2/service/dynamodb"
)

type TestKeyGenerator struct {
	mu         sync.Mutex
	r          *rand.Rand
	jsonGroups []map[string]int
}

func NewTestKeyGenerator(seed int64, jsonGroups []map[string]int) *TestKeyGenerator {
	return &TestKeyGenerator{
		r:          rand.New(rand.NewSource(seed)),
		jsonGroups: jsonGroups,
	}
}

func (kg *TestKeyGenerator) Next() (string, map[string][]byte) {
	kg.mu.Lock()
	defer kg.mu.Unlock()
	id := fmt.Sprintf("%016x%016x", kg.r.Uint64(), kg.r.Uint64())
	groupIdx := kg.r.Intn(len(kg.jsonGroups))
	data := make(map[string][]byte)
	for k, v := range kg.jsonGroups[groupIdx] {
		data[k] = make([]byte, v)
	}
	return id, data
}

func main() {
	tableName := flag.String("table", "stress-test", "DynamoDB table name")
	region := flag.String("region", "us-east-1", "AWS region")
	configFile := flag.String("config", "package-batch-big.json", "Configuration file path")
	useSortKey := flag.Bool("sortkey", false, "Use sort key (multirow mode)")
	seed := flag.Int64("seed", 0, "Random seed (0 for fixed, -1 for random)")
	duration := flag.Int("t", 3600, "Test duration in seconds")
	times := flag.Int("times", 0, "Number of iterations (0 for unlimited)")
	printKey := flag.Bool("printkey", false, "Print the generated key")
	readConsistency := flag.Bool("consistentRead", false, "Use strongly consistent reads")
	writeThreads := flag.Int("writeAll", 0, "Number of write all columns threads")
	readThreads := flag.Int("readAll", 0, "Number of read all columns threads")
	batchReadThreads := flag.Int("batchReadAll", 0, "Number of batch read threads")
	updateThreads := flag.Int("updateSingle", 0, "Number of update single column threads")
	readSingleThreads := flag.Int("readSingle", 0, "Number of read single column threads")
	deleteSingleThreads := flag.Int("deleteSingle", 0, "Number of delete single column threads")
	deleteAllThreads := flag.Int("deleteAll", 0, "Number of delete all columns threads")
	flag.Parse()

	cfg, err := config.LoadDefaultConfig(context.TODO(), config.WithRegion(*region))
	if err != nil {
		log.Fatal(err)
	}
	client := dynamodb.NewFromConfig(cfg)

	data, err := os.ReadFile(*configFile)
	if err != nil {
		log.Fatal(err)
	}
	var jsonGroups []map[string]int
	if err := json.Unmarshal(data, &jsonGroups); err != nil {
		log.Fatal(err)
	}

	writeSeed := int64(1)
	readSeed := int64(1)
	if *seed != -1 {
		writeSeed = *seed
		readSeed = *seed
	} else {
		writeSeed = time.Now().UnixNano()
		readSeed = time.Now().UnixNano()
	}

	writeKeyGen := NewTestKeyGenerator(writeSeed, jsonGroups)
	readKeyGen := NewTestKeyGenerator(readSeed, jsonGroups)

	var handler DDBHandler
	if *useSortKey {
		fmt.Println("=== 测试多行模式 ===")
		handler = NewMultiRowHandler(client, *tableName)
	} else {
		fmt.Println("=== 测试多列模式 ===")
		handler = NewMultiColumnHandler(client, *tableName)
	}

	ctx, cancel := context.WithTimeout(context.Background(), time.Duration(*duration)*time.Second)
	defer cancel()

	var wg sync.WaitGroup
	stats := &TestStats{}

	for i := 0; i < *writeThreads; i++ {
		wg.Add(1)
		time.Sleep(time.Duration(i) * time.Millisecond)
		go writeAllWorker(ctx, &wg, handler, writeKeyGen, stats, *printKey, *times)
	}

	for i := 0; i < *readThreads; i++ {
		wg.Add(1)
		time.Sleep(time.Duration(i) * time.Millisecond)
		go readAllWorker(ctx, &wg, handler, readKeyGen, stats, *printKey, *times, *readConsistency)
	}

	for i := 0; i < *batchReadThreads; i++ {
		wg.Add(1)
		time.Sleep(time.Duration(i) * time.Millisecond)
		go batchReadAllWorker(ctx, &wg, handler, readKeyGen, stats, *printKey, *times, *readConsistency)
	}

	for i := 0; i < *updateThreads; i++ {
		wg.Add(1)
		time.Sleep(time.Duration(i) * time.Millisecond)
		go updateSingleWorker(ctx, &wg, handler, writeKeyGen, stats, *printKey, *times)
	}

	for i := 0; i < *readSingleThreads; i++ {
		wg.Add(1)
		time.Sleep(time.Duration(i) * time.Millisecond)
		go readSingleWorker(ctx, &wg, handler, readKeyGen, stats, *printKey, *times, *readConsistency)
	}

	for i := 0; i < *deleteSingleThreads; i++ {
		wg.Add(1)
		time.Sleep(time.Duration(i) * time.Millisecond)
		go deleteSingleWorker(ctx, &wg, handler, writeKeyGen, stats, *printKey, *times)
	}

	for i := 0; i < *deleteAllThreads; i++ {
		wg.Add(1)
		time.Sleep(time.Duration(i) * time.Millisecond)
		go deleteAllWorker(ctx, &wg, handler, writeKeyGen, stats, *printKey, *times)
	}

	go printTestStats(ctx, stats)

	wg.Wait()
	printFinalTestStats(stats, *duration)
}

type TestStats struct {
	writeAllCount      int64
	writeAllErrors     int64
	readAllCount       int64
	readAllErrors      int64
	batchReadAllCount  int64
	batchReadAllErrors int64
	updateSingleCount  int64
	updateSingleErrors int64
	readSingleCount    int64
	readSingleErrors   int64
	deleteSingleCount  int64
	deleteSingleErrors int64
	deleteAllCount     int64
	deleteAllErrors    int64
}

func writeAllWorker(ctx context.Context, wg *sync.WaitGroup, handler DDBHandler, keyGen *TestKeyGenerator, stats *TestStats, printKey bool, times int) {
	defer wg.Done()
	iter := 0
	for {
		if times > 0 && iter >= times {
			return
		}
		select {
		case <-ctx.Done():
			return
		default:
			id, data := keyGen.Next()
			if printKey {
				fmt.Println(id)
			}
			err := handler.WriteAllColumns(ctx, id, data)
			if err == nil {
				atomic.AddInt64(&stats.writeAllCount, 1)
			} else if !errors.Is(err, context.Canceled) && !errors.Is(err, context.DeadlineExceeded) {
				fmt.Printf("WriteAll error: %+v\n", err)
				atomic.AddInt64(&stats.writeAllErrors, 1)
			}
			iter++
		}
	}
}

func readAllWorker(ctx context.Context, wg *sync.WaitGroup, handler DDBHandler, keyGen *TestKeyGenerator, stats *TestStats, printKey bool, times int, consistentRead bool) {
	defer wg.Done()
	iter := 0
	for {
		if times > 0 && iter >= times {
			return
		}
		select {
		case <-ctx.Done():
			return
		default:
			id, _ := keyGen.Next()
			if printKey {
				fmt.Println(id)
			}
			_, err := handler.ReadAllColumns(ctx, id)
			if err == nil {
				atomic.AddInt64(&stats.readAllCount, 1)
			} else if !errors.Is(err, context.Canceled) && !errors.Is(err, context.DeadlineExceeded) {
				fmt.Printf("ReadAll error: %+v\n", err)
				atomic.AddInt64(&stats.readAllErrors, 1)
			}
			iter++
		}
	}
}

func batchReadAllWorker(ctx context.Context, wg *sync.WaitGroup, handler DDBHandler, keyGen *TestKeyGenerator, stats *TestStats, printKey bool, times int, consistentRead bool) {
	defer wg.Done()
	iter := 0
	for {
		if times > 0 && iter >= times {
			return
		}
		select {
		case <-ctx.Done():
			return
		default:
			ids := make([]string, 10)
			for i := 0; i < 10; i++ {
				id, _ := keyGen.Next()
				ids[i] = id
				if printKey {
					fmt.Println(id)
				}
			}
			_, err := handler.BatchReadAllColumns(ctx, ids)
			if err == nil {
				atomic.AddInt64(&stats.batchReadAllCount, int64(len(ids)))
			} else if !errors.Is(err, context.Canceled) && !errors.Is(err, context.DeadlineExceeded) {
				fmt.Printf("BatchReadAll error: %+v\n", err)
				atomic.AddInt64(&stats.batchReadAllErrors, 1)
			}
			iter++
		}
	}
}

func updateSingleWorker(ctx context.Context, wg *sync.WaitGroup, handler DDBHandler, keyGen *TestKeyGenerator, stats *TestStats, printKey bool, times int) {
	defer wg.Done()
	iter := 0
	for {
		if times > 0 && iter >= times {
			return
		}
		select {
		case <-ctx.Done():
			return
		default:
			id, data := keyGen.Next()
			if printKey {
				fmt.Println(id)
			}
			for colName, colData := range data {
				err := handler.UpdateSingleColumn(ctx, id, colName, colData)
				if err == nil {
					atomic.AddInt64(&stats.updateSingleCount, 1)
				} else if !errors.Is(err, context.Canceled) && !errors.Is(err, context.DeadlineExceeded) {
					fmt.Printf("UpdateSingle error: %+v\n", err)
					atomic.AddInt64(&stats.updateSingleErrors, 1)
				}
				break
			}
			iter++
		}
	}
}

func readSingleWorker(ctx context.Context, wg *sync.WaitGroup, handler DDBHandler, keyGen *TestKeyGenerator, stats *TestStats, printKey bool, times int, consistentRead bool) {
	defer wg.Done()
	iter := 0
	for {
		if times > 0 && iter >= times {
			return
		}
		select {
		case <-ctx.Done():
			return
		default:
			id, data := keyGen.Next()
			if printKey {
				fmt.Println(id)
			}
			for colName := range data {
				_, err := handler.ReadSingleColumn(ctx, id, colName)
				if err == nil {
					atomic.AddInt64(&stats.readSingleCount, 1)
				} else if !errors.Is(err, context.Canceled) && !errors.Is(err, context.DeadlineExceeded) {
					fmt.Printf("ReadSingle error: %+v\n", err)
					atomic.AddInt64(&stats.readSingleErrors, 1)
				}
				break
			}
			iter++
		}
	}
}

func deleteSingleWorker(ctx context.Context, wg *sync.WaitGroup, handler DDBHandler, keyGen *TestKeyGenerator, stats *TestStats, printKey bool, times int) {
	defer wg.Done()
	iter := 0
	for {
		if times > 0 && iter >= times {
			return
		}
		select {
		case <-ctx.Done():
			return
		default:
			id, data := keyGen.Next()
			if printKey {
				fmt.Println(id)
			}
			for colName := range data {
				err := handler.DeleteSingleColumn(ctx, id, colName)
				if err == nil {
					atomic.AddInt64(&stats.deleteSingleCount, 1)
				} else if !errors.Is(err, context.Canceled) && !errors.Is(err, context.DeadlineExceeded) {
					fmt.Printf("DeleteSingle error: %+v\n", err)
					atomic.AddInt64(&stats.deleteSingleErrors, 1)
				}
				break
			}
			iter++
		}
	}
}

func deleteAllWorker(ctx context.Context, wg *sync.WaitGroup, handler DDBHandler, keyGen *TestKeyGenerator, stats *TestStats, printKey bool, times int) {
	defer wg.Done()
	iter := 0
	for {
		if times > 0 && iter >= times {
			return
		}
		select {
		case <-ctx.Done():
			return
		default:
			id, _ := keyGen.Next()
			if printKey {
				fmt.Println(id)
			}
			err := handler.DeleteAllColumns(ctx, id)
			if err == nil {
				atomic.AddInt64(&stats.deleteAllCount, 1)
			} else if !errors.Is(err, context.Canceled) && !errors.Is(err, context.DeadlineExceeded) {
				fmt.Printf("DeleteAll error: %+v\n", err)
				atomic.AddInt64(&stats.deleteAllErrors, 1)
			}
			iter++
		}
	}
}

func printTestStats(ctx context.Context, stats *TestStats) {
	ticker := time.NewTicker(5 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			var output []string
			if c := atomic.LoadInt64(&stats.writeAllCount); c > 0 || atomic.LoadInt64(&stats.writeAllErrors) > 0 {
				output = append(output, fmt.Sprintf("WriteAll: %d (errs:%d)", c, atomic.LoadInt64(&stats.writeAllErrors)))
			}
			if c := atomic.LoadInt64(&stats.readAllCount); c > 0 || atomic.LoadInt64(&stats.readAllErrors) > 0 {
				output = append(output, fmt.Sprintf("ReadAll: %d (errs:%d)", c, atomic.LoadInt64(&stats.readAllErrors)))
			}
			if c := atomic.LoadInt64(&stats.batchReadAllCount); c > 0 || atomic.LoadInt64(&stats.batchReadAllErrors) > 0 {
				output = append(output, fmt.Sprintf("BatchReadAll: %d (errs:%d)", c, atomic.LoadInt64(&stats.batchReadAllErrors)))
			}
			if c := atomic.LoadInt64(&stats.updateSingleCount); c > 0 || atomic.LoadInt64(&stats.updateSingleErrors) > 0 {
				output = append(output, fmt.Sprintf("UpdateSingle: %d (errs:%d)", c, atomic.LoadInt64(&stats.updateSingleErrors)))
			}
			if c := atomic.LoadInt64(&stats.readSingleCount); c > 0 || atomic.LoadInt64(&stats.readSingleErrors) > 0 {
				output = append(output, fmt.Sprintf("ReadSingle: %d (errs:%d)", c, atomic.LoadInt64(&stats.readSingleErrors)))
			}
			if c := atomic.LoadInt64(&stats.deleteSingleCount); c > 0 || atomic.LoadInt64(&stats.deleteSingleErrors) > 0 {
				output = append(output, fmt.Sprintf("DeleteSingle: %d (errs:%d)", c, atomic.LoadInt64(&stats.deleteSingleErrors)))
			}
			if c := atomic.LoadInt64(&stats.deleteAllCount); c > 0 || atomic.LoadInt64(&stats.deleteAllErrors) > 0 {
				output = append(output, fmt.Sprintf("DeleteAll: %d (errs:%d)", c, atomic.LoadInt64(&stats.deleteAllErrors)))
			}
			if len(output) > 0 {
				fmt.Printf("[%s] %s\n", time.Now().Format("15:04:05"), output[0])
				for i := 1; i < len(output); i++ {
					fmt.Printf("          %s\n", output[i])
				}
			}
		}
	}
}

func printFinalTestStats(stats *TestStats, duration int) {
	fmt.Println("\n=== Final Statistics ===")
	if c := atomic.LoadInt64(&stats.writeAllCount); c > 0 || atomic.LoadInt64(&stats.writeAllErrors) > 0 {
		qps := float64(c) / float64(duration)
		latency := 1000.0 / qps
		fmt.Printf("WriteAll: %d / %d, QPS: %.2f, Latency: %.2fms\n", c, atomic.LoadInt64(&stats.writeAllErrors), qps, latency)
	}
	if c := atomic.LoadInt64(&stats.readAllCount); c > 0 || atomic.LoadInt64(&stats.readAllErrors) > 0 {
		qps := float64(c) / float64(duration)
		latency := 1000.0 / qps
		fmt.Printf("ReadAll: %d / %d, QPS: %.2f, Latency: %.2fms\n", c, atomic.LoadInt64(&stats.readAllErrors), qps, latency)
	}
	if c := atomic.LoadInt64(&stats.batchReadAllCount); c > 0 || atomic.LoadInt64(&stats.batchReadAllErrors) > 0 {
		qps := float64(c) / float64(duration)
		latency := 1000.0 / qps
		fmt.Printf("BatchReadAll: %d / %d, QPS: %.2f, Latency: %.2fms\n", c, atomic.LoadInt64(&stats.batchReadAllErrors), qps, latency)
	}
	if c := atomic.LoadInt64(&stats.updateSingleCount); c > 0 || atomic.LoadInt64(&stats.updateSingleErrors) > 0 {
		qps := float64(c) / float64(duration)
		latency := 1000.0 / qps
		fmt.Printf("UpdateSingle: %d / %d, QPS: %.2f, Latency: %.2fms\n", c, atomic.LoadInt64(&stats.updateSingleErrors), qps, latency)
	}
	if c := atomic.LoadInt64(&stats.readSingleCount); c > 0 || atomic.LoadInt64(&stats.readSingleErrors) > 0 {
		qps := float64(c) / float64(duration)
		latency := 1000.0 / qps
		fmt.Printf("ReadSingle: %d / %d, QPS: %.2f, Latency: %.2fms\n", c, atomic.LoadInt64(&stats.readSingleErrors), qps, latency)
	}
	if c := atomic.LoadInt64(&stats.deleteSingleCount); c > 0 || atomic.LoadInt64(&stats.deleteSingleErrors) > 0 {
		qps := float64(c) / float64(duration)
		latency := 1000.0 / qps
		fmt.Printf("DeleteSingle: %d / %d, QPS: %.2f, Latency: %.2fms\n", c, atomic.LoadInt64(&stats.deleteSingleErrors), qps, latency)
	}
	if c := atomic.LoadInt64(&stats.deleteAllCount); c > 0 || atomic.LoadInt64(&stats.deleteAllErrors) > 0 {
		qps := float64(c) / float64(duration)
		latency := 1000.0 / qps
		fmt.Printf("DeleteAll: %d / %d, QPS: %.2f, Latency: %.2fms\n", c, atomic.LoadInt64(&stats.deleteAllErrors), qps, latency)
	}
}
