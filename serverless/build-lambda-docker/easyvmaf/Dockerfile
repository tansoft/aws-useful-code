FROM gfdavila/easyvmaf

# Define function directory
ARG FUNCTION_DIR="/app/easyVmaf-master"

WORKDIR ${FUNCTION_DIR}

RUN apt-get update && \
  apt-get install -y \
    unzip \
    libcurl4-openssl-dev

# Install the runtime interface client
RUN pip3 install \
        --target ${FUNCTION_DIR} \
        awslambdaric

# Copy function code
COPY * ${FUNCTION_DIR}

RUN pip3 install -r requirements.txt --target "${FUNCTION_DIR}"

ENTRYPOINT [ "/usr/local/bin/python", "-m", "awslambdaric" ]
CMD [ "app.handler" ]

