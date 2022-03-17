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
#下载主程序
wget https://raw.githubusercontent.com/tansoft/aws-poc/main/graviton-cpu-test/cputest.c
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

![测试结论](benchmark.png)

## 测试原始数据

```
X86单核
threads: 1 times: 100 speed: 624761.58us cpu:  4.91%
threads: 2 times: 100 speed: 627123.01us cpu:  9.81%
threads: 3 times: 100 speed: 630345.77us cpu: 14.00%
threads: 4 times: 100 speed: 633263.45us cpu: 17.27%
threads: 5 times: 100 speed: 638362.48us cpu: 22.49%
threads: 10 times: 100 speed: 649798.63us cpu: 41.50%
threads: 15 times: 100 speed: 684190.72us cpu: 65.17%
threads: 20 times: 100 speed: 747998.47us cpu: 71.83%
threads: 25 times: 100 speed: 807786.48us cpu: 77.91%
threads: 30 times: 100 speed: 843757.01us cpu: 83.98%
threads: 40 times: 100 speed: 691593.26us cpu: 94.71%
threads: 50 times: 100 speed: 819268.53us cpu:100.00%

Arm单核
threads: 1 times: 100 speed: 536893.36us cpu:  0.00%
threads: 2 times: 100 speed: 539370.50us cpu:  3.21%
threads: 3 times: 100 speed: 542534.81us cpu:  4.07%
threads: 4 times: 100 speed: 544354.71us cpu:  7.17%
threads: 5 times: 100 speed: 546318.92us cpu: 26.56%
threads: 10 times: 100 speed: 557717.22us cpu:  8.41%
threads: 15 times: 100 speed: 568626.73us cpu: 53.35%
threads: 20 times: 100 speed: 580741.39us cpu: 30.52%
threads: 25 times: 100 speed: 591742.77us cpu: 58.36%
threads: 30 times: 100 speed: 605976.66us cpu: 15.05%
threads: 40 times: 100 speed: 627843.99us cpu: 71.27%
threads: 50 times: 100 speed: 653795.19us cpu: 80.67%
threads: 60 times: 100 speed: 679623.51us cpu: 89.45%
threads: 70 times: 100 speed: 751872.26us cpu:100.00%

X86双核
threads: 1 times: 100 speed: 623670.49us cpu:  2.86% 1.66%
threads: 2 times: 100 speed: 621585.36us cpu:  6.03% 5.41%
threads: 3 times: 100 speed: 568100.30us cpu: 10.23% 10.18%
threads: 4 times: 100 speed: 581546.33us cpu: 13.40% 13.26%
threads: 5 times: 100 speed: 597531.01us cpu: 14.41% 14.63%
threads: 10 times: 100 speed: 640466.46us cpu: 25.80% 25.72%
threads: 15 times: 100 speed: 662986.73us cpu: 32.98% 33.05%
threads: 20 times: 100 speed: 662842.52us cpu: 42.12% 42.63%
threads: 25 times: 100 speed: 669482.97us cpu: 47.13% 48.39%
threads: 30 times: 100 speed: 696170.24us cpu: 57.14% 57.39%
threads: 40 times: 100 speed: 717344.41us cpu: 65.35% 64.55%
threads: 50 times: 100 speed: 703805.05us cpu: 67.99% 67.17%
threads: 60 times: 100 speed: 708720.72us cpu: 77.34% 77.11%
threads: 70 times: 100 speed: 717961.68us cpu: 87.82% 86.81%
threads: 80 times: 100 speed: 735604.02us cpu: 97.90% 97.66%
threads: 90 times: 100 speed: 794597.01us cpu:100.00% 100.00%

Arm双核
threads: 1 times: 100 speed: 537352.32us cpu:  0.00% 0.04%
threads: 2 times: 100 speed: 537919.01us cpu:  0.04% 0.00%
threads: 3 times: 100 speed: 515252.45us cpu:  7.11% 6.17%
threads: 4 times: 100 speed: 534361.41us cpu: 10.45% 5.89%
threads: 5 times: 100 speed: 490022.65us cpu:  7.49% 6.75%
threads: 10 times: 100 speed: 537174.75us cpu: 10.07% 10.47%
threads: 15 times: 100 speed: 551570.03us cpu: 16.29% 17.83%
threads: 20 times: 100 speed: 580135.39us cpu: 19.24% 17.80%
threads: 25 times: 100 speed: 599092.90us cpu: 30.30% 28.74%
threads: 30 times: 100 speed: 619146.60us cpu: 33.97% 31.17%
threads: 40 times: 100 speed: 663676.99us cpu: 41.66% 41.42%
threads: 50 times: 100 speed: 708508.84us cpu: 52.84% 49.90%
threads: 60 times: 100 speed: 747945.37us cpu: 59.38% 58.24%
threads: 70 times: 100 speed: 784230.54us cpu: 62.00% 61.46%
threads: 80 times: 100 speed: 819690.60us cpu: 73.02% 72.73%
threads: 90 times: 100 speed: 852340.79us cpu: 77.61% 76.52%
threads: 100 times: 100 speed: 880725.79us cpu: 86.26% 85.55%
threads: 110 times: 100 speed: 905287.99us cpu: 92.18% 91.03%
threads: 120 times: 100 speed: 940188.23us cpu: 98.52% 98.18%
threads: 130 times: 100 speed: 994518.29us cpu:100.00% 100.00%
```
