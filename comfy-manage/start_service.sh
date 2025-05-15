source /home/ubuntu/comfy/env

echo "Starting ComfyUI with ${ENV} ${S3_BUCKET}"

mount-s3 ${S3_BUCKET} /home/ubuntu/comfy/s3

nohup /home/ubuntu/venv/bin/python3 parse_job.py &

/home/ubuntu/venv/bin/python3 main.py --listen 0.0.0.0 --port 8080
