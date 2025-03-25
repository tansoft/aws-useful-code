#!/bin/bash
#./fping.sh AS400862 startip endip "outfile"

asn=$1
startip=$2
endip=$3
outfile=$4

temp_file=$(mktemp)

fping -g ${startip} ${endip} -r 2 -a -q > "${temp_file}"
#fping -g ${startip} ${endip} -r 2 -a -q | while read -r line; do
#    echo "${asn},${line}" >> "${temp_file}"
#done

# 获取独占锁并写入最终文件
(
  flock -x 200
  cat ${temp_file} >> "${outfile}"
) 200> /dev/null

rm "${temp_file}"
