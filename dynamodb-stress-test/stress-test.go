package main

import (
        "context"
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
        "github.com/aws/aws-sdk-go-v2/service/dynamodb/types"
        "gopkg.in/yaml.v3"
)

var (
        tableName         = flag.String("table", "stress-test", "DynamoDB table name")
        region            = flag.String("region", "us-east-1", "AWS region")
        configFile        = flag.String("config", "package.yaml", "Configuration file path")
        writeThreads      = flag.Int("putItem", 0, "Number of write threads")
        readThreads       = flag.Int("getItem", 0, "Number of read threads")
        batchWriteThreads = flag.Int("batchWriteItem", 0, "Number of batch write threads")
        batchReadThreads  = flag.Int("batchGetItem", 0, "Number of batch read threads")
        batchDeleteThreads = flag.Int("batchDeleteItem", 0, "Number of batch delete threads")
        queryThreads      = flag.Int("query", 0, "Number of query threads")
        scanThreads       = flag.Int("scan", 0, "Number of scan threads")
        updateThreads     = flag.Int("updateItem", 0, "Number of update threads")
        deleteThreads     = flag.Int("deleteItem", 0, "Number of delete threads")
        duration          = flag.Int("t", 3600, "Test duration in seconds")
        times             = flag.Int("times", 0, "Number of iterations (0 for unlimited)")
        useSortKey        = flag.Bool("sortkey", false, "Use sort key in table schema")
        printKey          = flag.Bool("printkey", false, "Print the generated key")
)

type Stats struct {
        writeCount       int64
        readCount        int64
        writeErrors      int64
        readErrors       int64
        batchWriteCount  int64
        batchReadCount   int64
        batchWriteErrors int64
        batchReadErrors  int64
        batchDeleteCount int64
        batchDeleteErrors int64
        queryCount       int64
        queryErrors      int64
        scanCount        int64
        scanErrors       int64
        updateCount      int64
        updateErrors     int64
        deleteCount      int64
        deleteErrors     int64
}

type KeyGenerator struct {
        mu           sync.Mutex
        r            *rand.Rand
        packageNames []string
}

func NewKeyGenerator(seed int64, packageNames []string) *KeyGenerator {
        return &KeyGenerator{
                r:            rand.New(rand.NewSource(seed)),
                packageNames: packageNames,
        }
}

func (kg *KeyGenerator) Next() string {
        kg.mu.Lock()
        defer kg.mu.Unlock()
        return fmt.Sprintf("%016x%016x", kg.r.Uint64(), kg.r.Uint64())
}

func (kg *KeyGenerator) NextSortKey() (string, string) {
        kg.mu.Lock()
        defer kg.mu.Unlock()
        key := fmt.Sprintf("%016x%016x", kg.r.Uint64(), kg.r.Uint64())
        sk := kg.packageNames[kg.r.Intn(len(kg.packageNames))]
        return key, sk
}

func (kg *KeyGenerator) packageLength() int {
        kg.mu.Lock()
        defer kg.mu.Unlock()
        return len(kg.packageNames)
}

var (
        values       map[string][]byte
        packageNames []string
        writeKeyGen  *KeyGenerator
        readKeyGen   *KeyGenerator
)

type PackageConfig struct {
        Packages map[string]int `yaml:"packages"`
}

func loadPackages(filename string) (map[string][]byte, []string, error) {
        data, err := os.ReadFile(filename)
        if err != nil {
                return nil, nil, err
        }

        var cfg PackageConfig
        if err := yaml.Unmarshal(data, &cfg); err != nil {
                return nil, nil, err
        }

        values := make(map[string][]byte)
        names := make([]string, 0, len(cfg.Packages))
        for name, size := range cfg.Packages {
                values[name] = make([]byte, size)
                names = append(names, name)
        }
        return values, names, nil
}

func main() {
        flag.Parse()

        var err error
        values, packageNames, err = loadPackages(*configFile)
        if err != nil {
                log.Fatal(err)
        }

        cfg, err := config.LoadDefaultConfig(context.TODO(), config.WithRegion(*region))
        if err != nil {
                log.Fatal(err)
        }

        client := dynamodb.NewFromConfig(cfg)
        stats := &Stats{}
        writeKeyGen = NewKeyGenerator(1, packageNames)
        readKeyGen = NewKeyGenerator(1, packageNames)

        ctx, cancel := context.WithTimeout(context.Background(), time.Duration(*duration)*time.Second)
        defer cancel()

        var wg sync.WaitGroup

        // 启动写入线程
        for i := 0; i < *writeThreads; i++ {
                wg.Add(1)
                // 打散请求
                time.Sleep(time.Duration(i) * time.Millisecond)
                go writeWorker(ctx, &wg, client, stats, i)
        }

        // 启动读取线程
        for i := 0; i < *readThreads; i++ {
                wg.Add(1)
                time.Sleep(time.Duration(i) * time.Millisecond)
                go readWorker(ctx, &wg, client, stats, i)
        }

        // 启动批量写入线程
        for i := 0; i < *batchWriteThreads; i++ {
                wg.Add(1)
                time.Sleep(time.Duration(i) * time.Millisecond)
                go batchWriteWorker(ctx, &wg, client, stats, i)
        }

        // 启动批量读取线程
        for i := 0; i < *batchReadThreads; i++ {
                wg.Add(1)
                time.Sleep(time.Duration(i) * time.Millisecond)
                go batchReadWorker(ctx, &wg, client, stats, i)
        }

        // 启动批量删除线程
        for i := 0; i < *batchDeleteThreads; i++ {
                wg.Add(1)
                time.Sleep(time.Duration(i) * time.Millisecond)
                go batchDeleteWorker(ctx, &wg, client, stats, i)
        }

        // 启动Query线程
        for i := 0; i < *queryThreads; i++ {
                wg.Add(1)
                time.Sleep(time.Duration(i) * time.Millisecond)
                go queryWorker(ctx, &wg, client, stats, i)
        }

        // 启动Scan线程
        for i := 0; i < *scanThreads; i++ {
                wg.Add(1)
                time.Sleep(time.Duration(i) * time.Millisecond)
                go scanWorker(ctx, &wg, client, stats, i)
        }

        // 启动Update线程
        for i := 0; i < *updateThreads; i++ {
                wg.Add(1)
                time.Sleep(time.Duration(i) * time.Millisecond)
                go updateWorker(ctx, &wg, client, stats, i)
        }

        // 启动Delete线程
        for i := 0; i < *deleteThreads; i++ {
                wg.Add(1)
                time.Sleep(time.Duration(i) * time.Millisecond)
                go deleteWorker(ctx, &wg, client, stats, i)
        }

        // 统计输出
        go printStats(ctx, stats)

        wg.Wait()
        printFinalStats(stats)
}

func writeWorker(ctx context.Context, wg *sync.WaitGroup, client *dynamodb.Client, stats *Stats, id int) {
        defer wg.Done()

        item := map[string]types.AttributeValue{
                "id": &types.AttributeValueMemberS{Value: "aaa"},
        }
        if ! *useSortKey {
                for k, v := range values {
                        item[k] = &types.AttributeValueMemberB{Value: v}
                }
        }

        iter := 0
        for {
                if *times > 0 && iter >= *times {
                        return
                }
                select {
                case <-ctx.Done():
                        return
                default:
                        var key, sk string
                        if *useSortKey {
                                key, sk = writeKeyGen.NextSortKey()
                                if *printKey {
                                        fmt.Println(key, sk)
                                }
                                item["id"] = &types.AttributeValueMemberS{Value: key}
                                item["sk"] = &types.AttributeValueMemberS{Value: sk}
                                item["val"] = &types.AttributeValueMemberB{Value: values[sk]}
                        } else {
                                key = writeKeyGen.Next()
                                if *printKey {
                                        fmt.Println(key)
                                }
                                item["id"] = &types.AttributeValueMemberS{Value: key}
                        }
                        _, err := client.PutItem(ctx, &dynamodb.PutItemInput{
                                TableName: tableName,
                                Item:      item,
                        })
                        if err == nil {
                                atomic.AddInt64(&stats.writeCount, 1)
                        } else if !errors.Is(err, context.Canceled) && !errors.Is(err, context.DeadlineExceeded) {
                                // fmt.Printf("PutItem error: %+v\n", err)
                                atomic.AddInt64(&stats.writeErrors, 1)
                        }
                        iter++
                }
        }
}

func readWorker(ctx context.Context, wg *sync.WaitGroup, client *dynamodb.Client, stats *Stats, id int) {
        defer wg.Done()

        iter := 0
        for {
                if *times > 0 && iter >= *times {
                        return
                }
                select {
                case <-ctx.Done():
                        return
                default:
                        var key, sk string
                        keyMap := map[string]types.AttributeValue{}
                        if *useSortKey {
                                key, sk = readKeyGen.NextSortKey()
                                if *printKey {
                                        fmt.Println(key, sk)
                                }
                                keyMap["id"] = &types.AttributeValueMemberS{Value: key}
                                keyMap["sk"] = &types.AttributeValueMemberS{Value: sk}
                        } else {
                                key = readKeyGen.Next()
                                if *printKey {
                                        fmt.Println(key)
                                }
                                keyMap["id"] = &types.AttributeValueMemberS{Value: key}
                        }
                        _, err := client.GetItem(ctx, &dynamodb.GetItemInput{
                                TableName: tableName,
                                Key: keyMap,
                        })
                        if err == nil {
                                atomic.AddInt64(&stats.readCount, 1)
                        } else if !errors.Is(err, context.Canceled) && !errors.Is(err, context.DeadlineExceeded) {
                                atomic.AddInt64(&stats.readErrors, 1)
                        }
                        iter++
                }
        }
}

func batchWriteWorker(ctx context.Context, wg *sync.WaitGroup, client *dynamodb.Client, stats *Stats, id int) {
        defer wg.Done()
        batchCount := 25
        if *useSortKey {
                batchCount = writeKeyGen.packageLength()
        }

        iter := 0
        for {
                if *times > 0 && iter >= *times {
                        return
                }
                select {
                case <-ctx.Done():
                        return
                default:
                        var requests []types.WriteRequest
                        if *useSortKey {
                                key, _ := writeKeyGen.NextSortKey()
                                if *printKey {
                                        fmt.Println(key)
                                }
                                for k, v := range values {
                                        item := map[string]types.AttributeValue{}
                                        item["id"] = &types.AttributeValueMemberS{Value: key}
                                        item["sk"] = &types.AttributeValueMemberS{Value: k}
                                        item["val"] = &types.AttributeValueMemberB{Value: v}
                                        requests = append(requests, types.WriteRequest{
                                                PutRequest: &types.PutRequest{Item: item},
                                        })
                                }
                        } else {
                                for i := 0; i < batchCount; i++ {
                                        item := map[string]types.AttributeValue{}
                                        key := writeKeyGen.Next()
                                        if *printKey {
                                                fmt.Println(key)
                                        }
                                        item["id"] = &types.AttributeValueMemberS{Value: key}
                                        for k, v := range values {
                                                item[k] = &types.AttributeValueMemberB{Value: v}
                                        }
                                        requests = append(requests, types.WriteRequest{
                                                PutRequest: &types.PutRequest{Item: item},
                                        })
                                }
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
                        iter++
                }
        }
}

func batchReadWorker(ctx context.Context, wg *sync.WaitGroup, client *dynamodb.Client, stats *Stats, id int) {
        defer wg.Done()
        batchCount := 100

        iter := 0
        for {
                if *times > 0 && iter >= *times {
                        return
                }
                select {
                case <-ctx.Done():
                        return
                default:
                        var keys []map[string]types.AttributeValue
                        for i := 0; i < batchCount; i++ {
                                var key, sk string
                                keyMap := map[string]types.AttributeValue{}
                                if *useSortKey {
                                        key, sk = readKeyGen.NextSortKey()
                                        if *printKey {
                                                fmt.Println(key, sk)
                                        }
                                        keyMap["id"] = &types.AttributeValueMemberS{Value: key}
                                        keyMap["sk"] = &types.AttributeValueMemberS{Value: sk}
                                } else {
                                        key = readKeyGen.Next()
                                        if *printKey {
                                                fmt.Println(key)
                                        }
                                        keyMap["id"] = &types.AttributeValueMemberS{Value: key}
                                }
                                keys = append(keys, keyMap)
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
                        iter++
                }
        }
}

func batchDeleteWorker(ctx context.Context, wg *sync.WaitGroup, client *dynamodb.Client, stats *Stats, id int) {
        defer wg.Done()
        batchCount := 25
        if *useSortKey {
                batchCount = writeKeyGen.packageLength()
        }

        iter := 0
        for {
                if *times > 0 && iter >= *times {
                        return
                }
                select {
                case <-ctx.Done():
                        return
                default:
                        var requests []types.WriteRequest
                        if *useSortKey {
                                key, _ := writeKeyGen.NextSortKey()
                                if *printKey {
                                        fmt.Println(key)
                                }
                                for k, _ := range values {
                                        keyMap := map[string]types.AttributeValue{}
                                        keyMap["id"] = &types.AttributeValueMemberS{Value: key}
                                        keyMap["sk"] = &types.AttributeValueMemberS{Value: k}
                                        requests = append(requests, types.WriteRequest{
                                                DeleteRequest: &types.DeleteRequest{Key: keyMap},
                                        })
                                }
                        } else {
                                for i := 0; i < batchCount; i++ {
                                        keyMap := map[string]types.AttributeValue{}
                                        key := writeKeyGen.Next()
                                        if *printKey {
                                                fmt.Println(key)
                                        }
                                        keyMap["id"] = &types.AttributeValueMemberS{Value: key}
                                        requests = append(requests, types.WriteRequest{
                                                DeleteRequest: &types.DeleteRequest{Key: keyMap},
                                        })
                                }
                        }

                        _, err := client.BatchWriteItem(ctx, &dynamodb.BatchWriteItemInput{
                                RequestItems: map[string][]types.WriteRequest{
                                        *tableName: requests,
                                },
                        })
                        if err == nil {
                                atomic.AddInt64(&stats.batchDeleteCount, int64(batchCount))
                        } else if !errors.Is(err, context.Canceled) && !errors.Is(err, context.DeadlineExceeded) {
                                atomic.AddInt64(&stats.batchDeleteErrors, 1)
                        }
                        iter++
                }
        }
}

func queryWorker(ctx context.Context, wg *sync.WaitGroup, client *dynamodb.Client, stats *Stats, id int) {
        defer wg.Done()

        iter := 0
        for {
                if *times > 0 && iter >= *times {
                        return
                }
                select {
                case <-ctx.Done():
                        return
                default:
                        key := readKeyGen.Next()
                        if *printKey {
                                fmt.Println(key)
                        }
                        _, err := client.Query(ctx, &dynamodb.QueryInput{
                                TableName: tableName,
                                KeyConditionExpression: &[]string{"id = :id"}[0],
                                ExpressionAttributeValues: map[string]types.AttributeValue{
                                        ":id": &types.AttributeValueMemberS{Value: key},
                                },
                        })
                        if err == nil {
                                atomic.AddInt64(&stats.queryCount, 1)
                        } else if !errors.Is(err, context.Canceled) && !errors.Is(err, context.DeadlineExceeded) {
                                atomic.AddInt64(&stats.queryErrors, 1)
                        }
                        iter++
                }
        }
}

func scanWorker(ctx context.Context, wg *sync.WaitGroup, client *dynamodb.Client, stats *Stats, id int) {
        defer wg.Done()

        iter := 0
        for {
                if *times > 0 && iter >= *times {
                        return
                }
                select {
                case <-ctx.Done():
                        return
                default:
                        _, err := client.Scan(ctx, &dynamodb.ScanInput{
                                TableName: tableName,
                                Limit: &[]int32{100}[0],
                        })
                        if err == nil {
                                atomic.AddInt64(&stats.scanCount, 1)
                        } else if !errors.Is(err, context.Canceled) && !errors.Is(err, context.DeadlineExceeded) {
                                atomic.AddInt64(&stats.scanErrors, 1)
                        }
                        iter++
                }
        }
}

func updateWorker(ctx context.Context, wg *sync.WaitGroup, client *dynamodb.Client, stats *Stats, id int) {
        defer wg.Done()

        iter := 0
        for {
                if *times > 0 && iter >= *times {
                        return
                }
                select {
                case <-ctx.Done():
                        return
                default:
                        key, sk := writeKeyGen.NextSortKey()
                        if *printKey {
                                fmt.Println(key, sk)
                        }
                        keyMap := map[string]types.AttributeValue{}
                        var updateExpr string
                        if *useSortKey {
                                keyMap["id"] = &types.AttributeValueMemberS{Value: key}
                                keyMap["sk"] = &types.AttributeValueMemberS{Value: sk}
                                updateExpr = "SET val = :val"
                        } else {
                                keyMap["id"] = &types.AttributeValueMemberS{Value: key}
                                updateExpr = "SET " + sk + " = :val"
                        }
                        _, err := client.UpdateItem(ctx, &dynamodb.UpdateItemInput{
                                TableName: tableName,
                                Key: keyMap,
                                UpdateExpression: &updateExpr,
                                ExpressionAttributeValues: map[string]types.AttributeValue{
                                        ":val": &types.AttributeValueMemberB{Value: values[sk]},
                                },
                        })
                        if err == nil {
                                atomic.AddInt64(&stats.updateCount, 1)
                        } else if !errors.Is(err, context.Canceled) && !errors.Is(err, context.DeadlineExceeded) {
                                atomic.AddInt64(&stats.updateErrors, 1)
                        }
                        iter++
                }
        }
}

func deleteWorker(ctx context.Context, wg *sync.WaitGroup, client *dynamodb.Client, stats *Stats, id int) {
        defer wg.Done()

        iter := 0
        for {
                if *times > 0 && iter >= *times {
                        return
                }
                select {
                case <-ctx.Done():
                        return
                default:
                        var key, sk string
                        keyMap := map[string]types.AttributeValue{}
                        if *useSortKey {
                                key, sk = writeKeyGen.NextSortKey()
                                if *printKey {
                                        fmt.Println(key, sk)
                                }
                                keyMap["id"] = &types.AttributeValueMemberS{Value: key}
                                keyMap["sk"] = &types.AttributeValueMemberS{Value: sk}
                        } else {
                                key = writeKeyGen.Next()
                                if *printKey {
                                        fmt.Println(key)
                                }
                                keyMap["id"] = &types.AttributeValueMemberS{Value: key}
                        }
                        _, err := client.DeleteItem(ctx, &dynamodb.DeleteItemInput{
                                TableName: tableName,
                                Key: keyMap,
                        })
                        if err == nil {
                                atomic.AddInt64(&stats.deleteCount, 1)
                        } else if !errors.Is(err, context.Canceled) && !errors.Is(err, context.DeadlineExceeded) {
                                atomic.AddInt64(&stats.deleteErrors, 1)
                        }
                        iter++
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
                        var output []string
                        
                        if wc := atomic.LoadInt64(&stats.writeCount); wc > 0 || atomic.LoadInt64(&stats.writeErrors) > 0 {
                                output = append(output, fmt.Sprintf("Writes: %d (errs:%d)", wc, atomic.LoadInt64(&stats.writeErrors)))
                        }
                        if rc := atomic.LoadInt64(&stats.readCount); rc > 0 || atomic.LoadInt64(&stats.readErrors) > 0 {
                                output = append(output, fmt.Sprintf("Reads: %d (errs:%d)", rc, atomic.LoadInt64(&stats.readErrors)))
                        }
                        if bwc := atomic.LoadInt64(&stats.batchWriteCount); bwc > 0 || atomic.LoadInt64(&stats.batchWriteErrors) > 0 {
                                output = append(output, fmt.Sprintf("BatchWrites: %d (errs:%d)", bwc, atomic.LoadInt64(&stats.batchWriteErrors)))
                        }
                        if brc := atomic.LoadInt64(&stats.batchReadCount); brc > 0 || atomic.LoadInt64(&stats.batchReadErrors) > 0 {
                                output = append(output, fmt.Sprintf("BatchReads: %d (errs:%d)", brc, atomic.LoadInt64(&stats.batchReadErrors)))
                        }
                        if bdc := atomic.LoadInt64(&stats.batchDeleteCount); bdc > 0 || atomic.LoadInt64(&stats.batchDeleteErrors) > 0 {
                                output = append(output, fmt.Sprintf("BatchDeletes: %d (errs:%d)", bdc, atomic.LoadInt64(&stats.batchDeleteErrors)))
                        }
                        if qc := atomic.LoadInt64(&stats.queryCount); qc > 0 || atomic.LoadInt64(&stats.queryErrors) > 0 {
                                output = append(output, fmt.Sprintf("Queries: %d (errs:%d)", qc, atomic.LoadInt64(&stats.queryErrors)))
                        }
                        if sc := atomic.LoadInt64(&stats.scanCount); sc > 0 || atomic.LoadInt64(&stats.scanErrors) > 0 {
                                output = append(output, fmt.Sprintf("Scans: %d (errs:%d)", sc, atomic.LoadInt64(&stats.scanErrors)))
                        }
                        if uc := atomic.LoadInt64(&stats.updateCount); uc > 0 || atomic.LoadInt64(&stats.updateErrors) > 0 {
                                output = append(output, fmt.Sprintf("Updates: %d (errs:%d)", uc, atomic.LoadInt64(&stats.updateErrors)))
                        }
                        if dc := atomic.LoadInt64(&stats.deleteCount); dc > 0 || atomic.LoadInt64(&stats.deleteErrors) > 0 {
                                output = append(output, fmt.Sprintf("Deletes: %d (errs:%d)", dc, atomic.LoadInt64(&stats.deleteErrors)))
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

func printFinalStats(stats *Stats) {
        fmt.Println("\n=== Final Statistics ===")
        
        if wc := atomic.LoadInt64(&stats.writeCount); wc > 0 || atomic.LoadInt64(&stats.writeErrors) > 0 {
                qps := float64(wc)/float64(*duration)
                latency := 1000.0/qps
                fmt.Printf("Total Writes: %d / %d, QPS: %.2f, Latency: %.2fms\n", wc, atomic.LoadInt64(&stats.writeErrors), qps, latency)
        }
        if rc := atomic.LoadInt64(&stats.readCount); rc > 0 || atomic.LoadInt64(&stats.readErrors) > 0 {
                qps := float64(rc)/float64(*duration)
                latency := 1000.0/qps
                fmt.Printf("Total Reads: %d / %d, QPS: %.2f, Latency: %.2fms\n", rc, atomic.LoadInt64(&stats.readErrors), qps, latency)
        }
        if bwc := atomic.LoadInt64(&stats.batchWriteCount); bwc > 0 || atomic.LoadInt64(&stats.batchWriteErrors) > 0 {
                qps := float64(bwc)/float64(*duration)
                latency := 1000.0/qps
                fmt.Printf("Total Batch Writes: %d / %d, QPS: %.2f, Latency: %.2fms\n", bwc, atomic.LoadInt64(&stats.batchWriteErrors), qps, latency)
        }
        if brc := atomic.LoadInt64(&stats.batchReadCount); brc > 0 || atomic.LoadInt64(&stats.batchReadErrors) > 0 {
                qps := float64(brc)/float64(*duration)
                latency := 1000.0/qps
                fmt.Printf("Total Batch Reads: %d / %d, QPS: %.2f, Latency: %.2fms\n", brc, atomic.LoadInt64(&stats.batchReadErrors), qps, latency)
        }
        if bdc := atomic.LoadInt64(&stats.batchDeleteCount); bdc > 0 || atomic.LoadInt64(&stats.batchDeleteErrors) > 0 {
                qps := float64(bdc)/float64(*duration)
                latency := 1000.0/qps
                fmt.Printf("Total Batch Deletes: %d / %d, QPS: %.2f, Latency: %.2fms\n", bdc, atomic.LoadInt64(&stats.batchDeleteErrors), qps, latency)
        }
        if qc := atomic.LoadInt64(&stats.queryCount); qc > 0 || atomic.LoadInt64(&stats.queryErrors) > 0 {
                qps := float64(qc)/float64(*duration)
                latency := 1000.0/qps
                fmt.Printf("Total Queries: %d / %d, QPS: %.2f, Latency: %.2fms\n", qc, atomic.LoadInt64(&stats.queryErrors), qps, latency)
        }
        if sc := atomic.LoadInt64(&stats.scanCount); sc > 0 || atomic.LoadInt64(&stats.scanErrors) > 0 {
                qps := float64(sc)/float64(*duration)
                latency := 1000.0/qps
                fmt.Printf("Total Scans: %d / %d, QPS: %.2f, Latency: %.2fms\n", sc, atomic.LoadInt64(&stats.scanErrors), qps, latency)
        }
        if uc := atomic.LoadInt64(&stats.updateCount); uc > 0 || atomic.LoadInt64(&stats.updateErrors) > 0 {
                qps := float64(uc)/float64(*duration)
                latency := 1000.0/qps
                fmt.Printf("Total Updates: %d / %d, QPS: %.2f, Latency: %.2fms\n", uc, atomic.LoadInt64(&stats.updateErrors), qps, latency)
        }
        if dc := atomic.LoadInt64(&stats.deleteCount); dc > 0 || atomic.LoadInt64(&stats.deleteErrors) > 0 {
                qps := float64(dc)/float64(*duration)
                latency := 1000.0/qps
                fmt.Printf("Total Deletes: %d / %d, QPS: %.2f, Latency: %.2fms\n", dc, atomic.LoadInt64(&stats.deleteErrors), qps, latency)
        }
}
