
# DynamoDB 回档用时测试

由于目前DynamoDB还没有上线table改名功能，因此如果遇到table需要回档时，则需要进行复杂的几步操作配合才能完成。

## 场景

在固定维护期间，需要在维护前/维护后分别对表数据进行备份，以便万一出现问题时进行回滚。操作步骤如下：

* 手工创建备份
* 进行维护操作
* 手工创建备份
* 如果需要回档，先把原表进行删除
* 然后通过手工备份，进行同名Table还原

## 注意点

* 恢复表时是根据备份时Table的设置进行还原的，所以可以在备份前，先设置足够的预置RCU和WCU，再进行备份，备份还原时就可以直接设置到对应的RCU和WCU阈值了，便于Table预热。
* 恢复表时，也可以通过命令行参数指定修改表为按需还是预置模式，并直接设置RCU/WCU，但是需要一并设置相关全局索引的读写模式等。详细参考：https://docs.aws.amazon.com/cli/latest/reference/dynamodb/restore-table-from-backup.html

## 测试代码

源码详见 https://github.com/tansoft/aws-useful-code/raw/main/dynamodb-rollback-test/ddb.sh

代码中有 DynamoDB 几个对应 API 的调用函数，方便创建表，创建备份，还原备份等，注释中有调用例子。

## 测试过程

由于我的账号里没有海量数据，需要用程序生成少量数据进行测试。这里我用了两组少量数据进行测试。如果已经有比较大的表备份，可以很方便的直接进行测试。

在上面的测试代码最后，加入以下代码生成两份数据：

* 9万个key，每个value 1K长度，占用91MB空间
* 90万个key，每个value 1K长度，占用910MB空间

```bash
# add your test code here

create_table table-val1k-1w od
generate_data table-val1k-1w 100M

create_table table-val1k-10w od
generate_data table-val1k-10w 1G
```

在控制台上，能看到这两个Table，分别创建以下备份文件，得到6个备份用于测试：

* 按需模式下，创建备份一。
* 设置预置1000RCU/WCU后，创建备份二
* 设置预置2000RCU/WCU后，创建备份三。

记录备份对应的 arn 值，在上面的测试代码最后，添加以下代码进行测试：

```bash
# add your test code here

performance_test "100M-OD" "arn:aws:dynamodb:ap-northeast-1:xxx:table/table-val1k-1w/backup/01719386594009-1af2e264"

performance_test "100M-1000CU" "arn:aws:dynamodb:ap-northeast-1:xxx:table/table-val1k-1w/backup/01719386652899-26ebca93"

performance_test "100M-2000CU" "arn:aws:dynamodb:ap-northeast-1:xxx:table/table-val1k-1w/backup/01719394567060-7e8e88cc"

performance_test "1G-OD" "arn:aws:dynamodb:ap-northeast-1:xxx:table/table-val1k/backup/01719385350986-bd8577fd"

performance_test "1G-1000CU" "arn:aws:dynamodb:ap-northeast-1:xxx:table/table-val1k/backup/01719385439370-ae89aa10"

performance_test "1G-2000CU" "arn:aws:dynamodb:ap-northeast-1:xxx:table/table-val1k/backup/01719394582359-e8b3d38d"

```

程序运行效果如下：

```bash
restore table 1G-2000CU with arn:aws:dynamodb:ap-northeast-1:xxxxx:table/table-val1k/backup/01719394582359-e8b3d38d
waiting for restore ready .....................................................................................................................................ok
backup arn for table 1G-2000CU is arn:aws:dynamodb:ap-northeast-1:xxxxx:table/1G-2000CU/backup/01719396883789-24016977
waiting for backup ready ...ok
waiting for table deleted ....ok
restore table 1G-2000CU with arn:aws:dynamodb:ap-northeast-1:xxxxx:table/1G-2000CU/backup/01719396883789-24016977
waiting for restore ready ..................................................................................................................................ok
waiting for backup deleted ...ok
任务：1G-2000CU
 创建备份使用时间：2 秒
 回滚总用时：758 秒
  其中删除表：5 秒
  其中还原表：753 秒
```

## 测试结果

|数据量	|模式	|创建备份	|回滚总用时	|其中删除表	|其中还原表	|
|---	|---	|---	|---	|---	|---	|
|100M	|OD	|2	|599	|6	|593	|
|100M	|1000R/WCU	|2	|734	|4	|730	|
|100M	|2000R/WCU	|2	|590	|134	|456	|
|1G	|OD	|3	|564	|3	|561	|
|1G	|1000R/WCU	|2	|1381	|4	|1377	|
|1G	|2000R/WCU	|2	|758	|5	|753	|

* 创建备份是非常快速的。
* 主要耗时是在还原表的过程中。
* 预置模式一般时间会更长，可以理解是还原后，再进行阈值设置进行表预热。但是和设置的RCU/WCU大小关系不大。
* 和数据量的多少关系不明显。
* 受多种环境因素影响，整个恢复过程时间不是很稳定的。