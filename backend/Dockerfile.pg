# FILE: backend/Dockerfile.pg

FROM postgres:16-bookworm

ENV PGVECTOR_VERSION=v0.7.4
ENV AGE_BRANCH=release/PG16/1.5.0

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential git ca-certificates postgresql-server-dev-16 \
    libclang-dev flex bison libreadline-dev zlib1g-dev libssl-dev && \
    git config --global http.sslVerify false && \
    cd /tmp && \
    git clone --branch ${PGVECTOR_VERSION} https://github.com/pgvector/pgvector.git && \
    cd pgvector && \
    make clean && make && make install && \
    cd /tmp && \
    git clone --branch ${AGE_BRANCH} https://github.com/apache/age.git && \
    cd age && \
    make clean && make && make install && \
    cd / && \
    rm -rf /tmp/* && \
    apt-get purge -y --auto-remove \
    build-essential git postgresql-server-dev-16 libclang-dev flex \
    bison libreadline-dev zlib1g-dev libssl-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*
