# Setup

use Amazon Linux 2003 to test.

```bash
sudo yum install -y git g++ openssl-devel
sudo dnf install -y libevent-devel
git clone https://github.com/redis/hiredis.git
cd hiredis
make USE_SSL=1
sudo make install
wget https://github.com/tansoft/aws-useful-code/raw/main/elasticache-performance-test/logic-test.cpp
g++ -o logic-test logic-test.cpp -Wl,-Bstatic -lhiredis -Wl,-Bdynamic -ldl -lpthread -I/usr/local/include -L/usr/local/lib
```

# Test

```bash
# one
REDIS_SERVER=test-redis.xxxxx.ng.0001.apse1.cache.amazonaws.com
for i in {1..10}; do eval "nohup ./logic-test ${REDIS_SERVER} w >> log-one-w.txt 2>&1 &"; done
for i in {1..2}; do eval "nohup ./logic-test ${REDIS_SERVER} r >> log-one-r.txt 2>&1 &"; done

# two
REDIS_SERVER=test-redis-2.xxxxx.ng.0001.apse1.cache.amazonaws.com
for i in {1..10}; do eval "nohup ./logic-test ${REDIS_SERVER} w >> log-two-w.txt 2>&1 &"; done
for i in {1..2}; do eval "nohup ./logic-test ${REDIS_SERVER} r >> log-two-r.txt 2>&1 &"; done
```
