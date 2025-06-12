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

    # 是否需要进行初始化复制
    if [ -v COPY_MODEL_TO_LOCAL ]; then
        # 创建挂载目录
        MOUNT_POINT="/home/ubuntu/comfy/localcache/models"
        if [ ! -d "${MOUNT_POINT}" ]; then
            mkdir -p "${MOUNT_POINT}"
        fi
        # 是否存在本地存储
        INSTANCE_STORE_DEVICES=("/dev/nvme0n1" "/dev/nvme1n1" "/dev/nvme2n1")
        for DEVICE in "${INSTANCE_STORE_DEVICES[@]}"; do
            # 判断设备存在
            echo "check if it is a instance stroage: ${DEVICE} ..."
            if [ -b "${DEVICE}" ]; then
                # 如果设备还没有挂载，判断为实例存储
                if ! mount | grep -q "${DEVICE}"; then
                    echo "${DEVICE} is not mount, try to mount and use it ..."
                    sudo mkfs.ext4 -m 0 "${DEVICE}"
                    sudo mount "${DEVICE}" "${MOUNT_POINT}"
                    sudo chown -R ubuntu:ubuntu "${MOUNT_POINT}"
                    sudo chmod -R 755 "${MOUNT_POINT}"
                    break
                fi
            fi
        done
        if [ "${COPY_MODEL_TO_LOCAL}" == "awscli" ]; then
            aws s3 sync s3://${S3_BUCKET}/models ${MOUNT_POINT}
        elif [ "${COPY_MODEL_TO_LOCAL}" == "s5cmd" ]; then
            s5cmd sync s3://${S3_BUCKET}/models ${MOUNT_POINT}
        else
            echo "unknown option COPY_MODEL_TO_LOCAL = ${COPY_MODEL_TO_LOCAL}"
            exit 1
        fi
        if [ ! -L "/home/ubuntu/comfy/ComfyUI/models" ] || [ "$(readlink -f "/home/ubuntu/comfy/ComfyUI/models")" != "${MOUNT_POINT}" ]; then
            echo "replace models path to ${MOUNT_POINT} ..."
            rm /home/ubuntu/comfy/ComfyUI/models
            ln -s ${MOUNT_POINT} /home/ubuntu/comfy/ComfyUI/
        fi
        echo "use COPY_MODEL_TO_LOCAL mode, make sure sync models to s3 when modified. use command: aws s3 sync ${MOUNT_POINT} s3://${S3_BUCKET}/models"
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
