FROM gfdavila/easyvmaf

# Define function directory
ARG FUNCTION_DIR="/app/easyVmaf"

WORKDIR ${FUNCTION_DIR}

RUN apt-get update && \
  apt-get install -y \
    unzip \
    libcurl4-openssl-dev

# Install the runtime interface client
RUN pip3 install \
        --target ${FUNCTION_DIR} \
        awslambdaric

# add debug env
RUN apt-get update && apt-get install wget && \
  wget https://github.com/aws/aws-lambda-runtime-interface-emulator/releases/latest/download/aws-lambda-rie -O /usr/local/bin/aws-lambda-rie && \
  chmod +x /usr/local/bin/aws-lambda-rie
RUN echo "#!/bin/bash\ncd ${FUNCTION_DIR}\nif [ -z \"\${AWS_LAMBDA_RUNTIME_API}\" ]; then\n  exec /usr/local/bin/aws-lambda-rie /usr/local/bin/python -m awslambdaric \$@\nelse\n  exec /usr/local/bin/python -m awslambdaric \$@\nfi\n" > /usr/local/bin/entrypoint.sh && chmod +x /usr/local/bin/entrypoint.sh

#avoid write to WORKDIR
RUN sed -i 's#stats_file_psnr.log#/tmp/stats_file_psnr.log#' /app/easyVmaf/FFmpeg.py && \
  sed -i 's#self.vmafpath = log_path#self.vmafpath = "/tmp/vmaf." + log_fmt#' /app/easyVmaf/FFmpeg.py

# Copy function code
COPY * ${FUNCTION_DIR}/

RUN pip3 install -r requirements.txt --target "${FUNCTION_DIR}"

# ENTRYPOINT [ "/usr/local/bin/python", "-m", "awslambdaric" ]
ENTRYPOINT [ "/usr/local/bin/entrypoint.sh" ]
CMD [ "app.lambda_handler" ]
