
# 真实网络测试方法

* 通过 [ipinfo.io](https://ipinfo.io/) 等网站收集地区主流运营商

* 收集运营商主要ASN号码，放置到country_asn_ipv4_only.csv中

* 通过ASN号码和地区，过滤合适的ip网段

```bash
# ./run.sh 地区 asn 进行网段ip的ping测试
./run.sh US AS702
```

* 得到对应运营商可ping ip文件 pingable_US_AS702.txt

```bash
# 一键进行测试和生成结果
ls pingable_US_*.txt | xargs -I {} sh -c 'fping -f {} -a -q -C 11 2> result_{}'

# 每个运营商只测试最多1000条记录
ls pingable_US_*.txt | xargs -I {} sh -c 'shuf -n 1000 {} > limit1000_{}'
ls limit1000_pingable_US_*.txt | xargs -I {} sh -c 'fping -f {} -a -q -C 11 2> result_{}'
```

* 生成统计数据

```bash
# 只生成一个asn的数据
./stat.sh result_limit1000_pingable_US_AS12271.txt 
file,min,p50,p70,p90,p95,max,avg
result_limit1000_pingable_US_AS12271.txt,6.56,18.7,20.3,23.5,24.8,80.2,19.29

# 全部数据生成
ls result_limit1000_pingable_US_*.txt | xargs -I {} ./stat.sh {}
```

