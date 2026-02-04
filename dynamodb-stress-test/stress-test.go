package main

import (
        "context"
        "errors"
        "flag"
        "fmt"
        "log"
        "math/rand"
        "sync"
        "sync/atomic"
        "time"

        "github.com/aws/aws-sdk-go-v2/config"
        "github.com/aws/aws-sdk-go-v2/service/dynamodb"
        "github.com/aws/aws-sdk-go-v2/service/dynamodb/types"
)

var (
        tableName         = flag.String("table", "xuf", "DynamoDB table name")
        region            = flag.String("region", "ap-northeast-1", "AWS region")
        writeThreads      = flag.Int("w", 10, "Number of write threads")
        readThreads       = flag.Int("r", 10, "Number of read threads")
        batchWriteThreads = flag.Int("bw", 10, "Number of batch write threads")
        batchReadThreads  = flag.Int("br", 10, "Number of batch read threads")
        duration          = flag.Int("t", 3600, "Test duration in seconds")
)

type Stats struct {
        writeCount      int64
        readCount       int64
        writeErrors     int64
        readErrors      int64
        batchWriteCount int64
        batchReadCount  int64
        batchWriteErrors int64
        batchReadErrors  int64
}

var values map[string][]byte

func main() {
        flag.Parse()

        cfg, err := config.LoadDefaultConfig(context.TODO(), config.WithRegion(*region))
        if err != nil {
                log.Fatal(err)
        }

        client := dynamodb.NewFromConfig(cfg)
        stats := &Stats{}
        values = map[string][]byte{
                        "package1": make([]byte, 1120),
                        "package2": make([]byte, 1400),
                        "package3": make([]byte, 2100),
                        "package4": make([]byte, 1980),
                        "package5": make([]byte, 1460),
                        "package6": make([]byte, 320),
        }

        ctx, cancel := context.WithTimeout(context.Background(), time.Duration(*duration)*time.Second)
        defer cancel()

        var wg sync.WaitGroup

        // 启动写入线程
        for i := 0; i < *writeThreads; i++ {
                wg.Add(1)
                // 打散请求
                time.Sleep(i * time.Millisecond)
                go writeWorker(ctx, &wg, client, stats, i)
        }

        // 启动读取线程
        for i := 0; i < *readThreads; i++ {
                wg.Add(1)
                time.Sleep(i * time.Millisecond)
                go readWorker(ctx, &wg, client, stats, i)
        }

        // 启动批量写入线程
        for i := 0; i < *batchWriteThreads; i++ {
                wg.Add(1)
                time.Sleep(i * time.Millisecond)
                go batchWriteWorker(ctx, &wg, client, stats, i)
        }

        // 启动批量读取线程
        for i := 0; i < *batchReadThreads; i++ {
                wg.Add(1)
                time.Sleep(i * time.Millisecond)
                go batchReadWorker(ctx, &wg, client, stats, i)
        }

        // 统计输出
        go printStats(ctx, stats)

        wg.Wait()
        printFinalStats(stats)
}

func writeWorker(ctx context.Context, wg *sync.WaitGroup, client *dynamodb.Client, stats *Stats, id int) {
        defer wg.Done()
        r := rand.New(rand.NewSource(time.Now().UnixNano() + int64(id)))

        item := map[string]types.AttributeValue{
                "id": &types.AttributeValueMemberS{Value: "aaa"},
        }
        for k, v := range values {
                item[k] = &types.AttributeValueMemberB{Value: v}
        }

        for {
                select {
                case <-ctx.Done():
                        return
                default:
                        key := fmt.Sprintf("%016x%016x", r.Uint64(), r.Uint64())
                        item["id"] = &types.AttributeValueMemberS{Value: key}
                        _, err := client.PutItem(ctx, &dynamodb.PutItemInput{
                                TableName: tableName,
                                Item:      item,
                        })
                        if err == nil {
                                atomic.AddInt64(&stats.writeCount, 1)
                        } else if !errors.Is(err, context.Canceled) && !errors.Is(err, context.DeadlineExceeded) {
                                atomic.AddInt64(&stats.writeErrors, 1)
                        }
                }
        }
}

func readWorker(ctx context.Context, wg *sync.WaitGroup, client *dynamodb.Client, stats *Stats, id int) {
        defer wg.Done()
        r := rand.New(rand.NewSource(time.Now().UnixNano() + int64(id)*1000))

        for {
                select {
                case <-ctx.Done():
                        return
                default:
                        key := fmt.Sprintf("%016x%016x", r.Uint64(), r.Uint64())
                        _, err := client.GetItem(ctx, &dynamodb.GetItemInput{
                                TableName: tableName,
                                Key: map[string]types.AttributeValue{
                                        "id": &types.AttributeValueMemberS{Value: key},
                                },
                        })
                        if err == nil {
                                atomic.AddInt64(&stats.readCount, 1)
                        } else if !errors.Is(err, context.Canceled) && !errors.Is(err, context.DeadlineExceeded) {
                                atomic.AddInt64(&stats.readErrors, 1)
                        }
                }
        }
}

func batchWriteWorker(ctx context.Context, wg *sync.WaitGroup, client *dynamodb.Client, stats *Stats, id int) {
        defer wg.Done()
        r := rand.New(rand.NewSource(time.Now().UnixNano() + int64(id)*10000))
        batchCount := 25

        for {
                select {
                case <-ctx.Done():
                        return
                default:
                        var requests []types.WriteRequest
                        for i := 0; i < batchCount; i++ {
                                key := fmt.Sprintf("%016x%016x", r.Uint64(), r.Uint64())
                                item := map[string]types.AttributeValue{
                                        "id": &types.AttributeValueMemberS{Value: key},
                                }
                                for k, v := range values {
                                        item[k] = &types.AttributeValueMemberB{Value: v}
                                }
                                requests = append(requests, types.WriteRequest{
                                        PutRequest: &types.PutRequest{Item: item},
                                })
                        }

                        _, err := client.BatchWriteItem(ctx, &dynamodb.BatchWriteItemInput{
                                RequestItems: map[string][]types.WriteRequest{
                                        *tableName: requests,
                                },
                        })
                        if err == nil {
                                atomic.AddInt64(&stats.batchWriteCount, int64(batchCount))
                        } else if !errors.Is(err, context.Canceled) && !errors.Is(err, context.DeadlineExceeded) {
                                atomic.AddInt64(&stats.batchWriteErrors, 1)
                        }
                }
        }
}

func batchReadWorker(ctx context.Context, wg *sync.WaitGroup, client *dynamodb.Client, stats *Stats, id int) {
        defer wg.Done()
        r := rand.New(rand.NewSource(time.Now().UnixNano() + int64(id)*100000))
        batchCount := 100

        for {
                select {
                case <-ctx.Done():
                        return
                default:
                        var keys []map[string]types.AttributeValue
                        for i := 0; i < batchCount; i++ {
                                key := fmt.Sprintf("%016x%016x", r.Uint64(), r.Uint64())
                                keys = append(keys, map[string]types.AttributeValue{
                                        "id": &types.AttributeValueMemberS{Value: key},
                                })
                        }

                        _, err := client.BatchGetItem(ctx, &dynamodb.BatchGetItemInput{
                                RequestItems: map[string]types.KeysAndAttributes{
                                        *tableName: {Keys: keys},
                                },
                        })
                        if err == nil {
                                atomic.AddInt64(&stats.batchReadCount, int64(batchCount))
                        } else if !errors.Is(err, context.Canceled) && !errors.Is(err, context.DeadlineExceeded) {
                                atomic.AddInt64(&stats.batchReadErrors, 1)
                        }
                }
        }
}

func printStats(ctx context.Context, stats *Stats) {
        ticker := time.NewTicker(5 * time.Second)
        defer ticker.Stop()

        for {
                select {
                case <-ctx.Done():
                        return
                case <-ticker.C:
                        fmt.Printf("[%s] Writes: %d (errs:%d) | Reads: %d (errs:%d) | BatchWrites: %d (errs:%d) | BatchReads: %d (errs:%d)\n",
                                time.Now().Format("15:04:05"),
                                atomic.LoadInt64(&stats.writeCount),
                                atomic.LoadInt64(&stats.writeErrors),
                                atomic.LoadInt64(&stats.readCount),
                                atomic.LoadInt64(&stats.readErrors),
                                atomic.LoadInt64(&stats.batchWriteCount),
                                atomic.LoadInt64(&stats.batchWriteErrors),
                                atomic.LoadInt64(&stats.batchReadCount),
                                atomic.LoadInt64(&stats.batchReadErrors))
                }
        }
}

func printFinalStats(stats *Stats) {
        fmt.Println("\n=== Final Statistics ===")
        fmt.Printf("Total Writes: %d / %d\n", atomic.LoadInt64(&stats.writeCount), atomic.LoadInt64(&stats.writeErrors))
        fmt.Printf("Total Reads: %d / %d\n", atomic.LoadInt64(&stats.readCount), atomic.LoadInt64(&stats.readErrors))
        fmt.Printf("Total Batch Writes: %d / %d\n", atomic.LoadInt64(&stats.batchWriteCount), atomic.LoadInt64(&stats.batchWriteErrors))
        fmt.Printf("Total Batch Reads: %d / %d\n", atomic.LoadInt64(&stats.batchReadCount), atomic.LoadInt64(&stats.batchReadErrors))
        fmt.Printf("Write QPS: %.2f\n", float64(atomic.LoadInt64(&stats.writeCount))/float64(*duration))
        fmt.Printf("Read QPS: %.2f\n", float64(atomic.LoadInt64(&stats.readCount))/float64(*duration))
        fmt.Printf("Batch Write QPS: %.2f\n", float64(atomic.LoadInt64(&stats.batchWriteCount))/float64(*duration))
        fmt.Printf("Batch Read QPS: %.2f\n", float64(atomic.LoadInt64(&stats.batchReadCount))/float64(*duration))
}
