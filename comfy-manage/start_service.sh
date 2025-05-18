#!/bin/bash

# 确保 cloud-init 中设置了对应 ENV 变量
while [ ! -f /var/lib/cloud/instance/boot-finished ]; do sleep 1; done;

mode=${1:-"comfyui"}

if [ $mode == "comfyui" ]; then

    source /home/ubuntu/comfy/env

    echo "Starting ComfyUI with ${ENV} ${S3_BUCKET}"

    if mountpoint -q /home/ubuntu/comfy/s3; then
        echo "mount point /home/ubuntu/comfy/s3 is already mounted."
    else
        echo "mount /home/ubuntu/comfy/s3 ..."
        /usr/bin/mount-s3 ${S3_BUCKET} /home/ubuntu/comfy/s3 --allow-delete --allow-overwrite
    fi

    /home/ubuntu/venv/bin/python3 main.py --listen 0.0.0.0 --port 8188

elif [ $mode == "comfy-manage" ]; then

    until ps aux | grep main.py | grep -v grep; do sleep 2; echo "Waiting Comfyui start..."; done
    PID=`ps aux | grep main.py | grep -v grep | awk '{print $2}'`
    START_TIME=$(ps -p "$PID" -o lstart= | xargs -0 date +%s -d)
    CURRENT_TIME=$(date +%s)
    RUNTIME=$((CURRENT_TIME - START_TIME))
    if [ "$RUNTIME" -gt 300 ]; then
        echo "ComfyUI has been running for more than 5 minutes (${RUNTIME} seconds), not need to wait..."
    else
        echo "ComfyUI just started in ${RUNTIME} seconds."
        until journalctl -n 100 -u comfyui | grep -q "\[ComfyUI-Manager\] All startup tasks have been completed."; do sleep 2; echo "Still waiting Comfyui ready..."; done
        echo "ComfyUI is ready."
    fi

    echo "Starting Comfy Manage"

    /home/ubuntu/venv/bin/python3 /home/ubuntu/comfy/parse_job.py

else
    echo "Invalid mode: $mode"
    exit 1
fi
