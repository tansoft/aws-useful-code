# ARM高负载性能测试

## 测试目的

在x86服务器的认识上，大部分延迟敏感的业务，因为x86使用了超线程技术来扩展并发能力，在cpu大于50%时，容易引起性能下降，因此实际工作负载场景，cpu不能打得太满，一般以控制在40%为宜。而Arm架构因为每个核都是独立核心，因此在高负载场景下，性能应该不会有太大损失，因此进行测试观察是否可以把cpu消耗增加，从而提升性价比。

## 环境准备

* 对比机型：c5.4x c6g.4x
* 系统版本：Amazon Linux 2
* 测试方法：

```bash
#gcc用于编译，htop用于观察cpu情况
yum install -y gcc htop
#编译程序，-O0 确保没有进行代码上的优化，确保代码执行的正确性
gcc -lpthread cputest.c -O0 -o cputest
```

## 测试方法

```bash
#测试单核10线程
./cputest 10

#测试双核10线程
./cputest 10 2

#批量运行单核测试
bash -c "./cputest 1 && ./cputest 2 && ./cputest 3 && ./cputest 4 && ./cputest 5 && ./cputest 10 && ./cputest 15 && ./cputest 20 && ./cputest 25 && ./cputest 30 && ./cputest 40 && ./cputest 50" | grep "times: 100"

#批量运行双核测试
bash -c "./cputest 1 2 && ./cputest 2 2 && ./cputest 3 2 && ./cputest 4 2 && ./cputest 5 2 && ./cputest 10 2 && ./cputest 15 2 && ./cputest 20 2 && ./cputest 25 2 && ./cputest 30 2 && ./cputest 40 2 && ./cputest 50 2 && ./cputest 60 2 && ./cputest 70 2 && ./cputest 80 2 && ./cputest 90 2" | grep "times: 100"

```

## 测试结论
