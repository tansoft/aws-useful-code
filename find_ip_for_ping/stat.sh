#!/bin/bash

#./stat.sh file
datafile=$1

output=$(
    awk -F: '{print $2}' ${datafile} | while read -r line; do
        ret=`echo ${line} | tr ' ' "\n" | sort -n`
        cnt=`echo ${ret} | wc -w`
        mid=$((${cnt} / 2))
        result=`echo ${ret} | cut -d' ' -f${mid}`
        if [ "${result}" != "-" ]; then
            echo "${result}"
        fi
    done
)

ret=`echo ${output} | tr ' ' "\n" | sort -n`
arr=(`echo -n ${ret}`)
cnt=${#arr[@]}

p50=${arr[$(((${cnt}-1)*5/10))]}
p70=${arr[$(((${cnt}-1)*7/10))]}
p90=${arr[$(((${cnt}-1)*9/10))]}
p95=${arr[$(((${cnt}-1)*95/100))]}
min=${arr[0]}
max=${arr[$((${cnt}-1))]}

avg=`echo -n ${ret} | tr ' ' '+'`
avg=`echo "scale=2;(${avg})/${cnt}" | bc`

echo "file,min,p50,p70,p90,p95,max,avg"
echo "${datafile},${min},${p50},${p70},${p90},${p95},${max},${avg}"
