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
for i in {1..10}; do eval "nohup ./logic-test test-redis-001.xxxxx.0001.apse1.cache.amazonaws.com w &"; done
for i in {1..2}; do eval "nohup ./logic-test test-redis-001.xxxxx.0001.apse1.cache.amazonaws.com &"; done
```
