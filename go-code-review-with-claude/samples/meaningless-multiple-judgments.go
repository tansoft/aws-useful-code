package main

import (
    "fmt"
    "github.com/go-redis/redis"
)

var (
    redisClient *redis.Client
    ctx         = context.Background()
)

func getSomeThingInRedis(_key []byte) []byte {
    str, err := redisClient.Get(ctx, _key).Result()
    if err != goSdkRedis.ErrNotFound {
        if err != redis.Nil && err != nil {
            err = json.Unmarshal([]byte(str), &gameHistory)
            if err != nil && err != goSdkRedis.ErrNotFound {
                if err != nil && err != redis.Nil {
                    return err
                }
            }
        }
    }
    return ''
}

func main() {
    // Initialize the Redis client
    redisClient = redis.NewClient(&redis.Options{
        Addr:     "localhost:6379",
        Password: "aaa", // Set the password if required
        DB:       0,  // Set the desired database
    })

    message, err := getSomeThingInRedis("key")
    if err != nil {
        fmt.Println("Error:", err)
        return
    }

    fmt.Println(string(message))
}