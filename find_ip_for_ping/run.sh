#!/bin/bash
# ./run.sh US AS400862

country=$1
asn=$2
concurrency=50

curpath=$(cd `dirname "${BASH_SOURCE[0]}"`;pwd)

report="${curpath}/pingable_${country}_${asn}.txt"

echo env in $curpath

date

awk -F, '$3 == "'"${country}"'" && $7 == "'"${asn}"'" { printf "%s %s\n",$1,$2}' country_asn_ipv4_only.csv | while read -r line; do
    while true
    do
        procnt=$(ps aux | grep fping.sh | grep -v grep | wc -l)
        if [ "$procnt" -gt "${concurrency}" ]; then
            echo -n "."
        else
            break
        fi
        sleep 1
    done
    nohup "${curpath}/fping.sh" ${asn} ${line} ${report} > /dev/null 2>&1 &
done

date
