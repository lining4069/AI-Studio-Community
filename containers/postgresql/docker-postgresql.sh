#!/usr/bin/env bash
set -e  # 遇到错误就退出
set -u  # 未定义变量退出

# ========================
# 配置项（可修改）
# ========================
IMAGE_NAME="my-pgvector"
CONTAINER_NAME="pgvector-db"
POSTGRES_DB="ai_studio"
POSTGRES_USER="ai_studio_app"
POSTGRES_PASSWORD="Aistudio12345679"
HOST_PORT=5432
DATA_DIR="$(pwd)/data"

# ========================
# 1. 创建数据目录（如果不存在）
# ========================
mkdir -p "${DATA_DIR}"

# ========================
# 2. 构建镜像
# ========================
echo "🛠️  Building Docker image: ${IMAGE_NAME} ..."
docker build -t "${IMAGE_NAME}" .

# ========================
# 3. 删除旧容器（如果存在）
# ========================
if [ "$(docker ps -aq -f name=${CONTAINER_NAME})" ]; then
    echo "⚠️  Removing existing container: ${CONTAINER_NAME} ..."
    docker rm -f "${CONTAINER_NAME}"
fi

# ========================
# 4. 启动新容器
# ========================
echo "🚀  Running container: ${CONTAINER_NAME} ..."
docker run -d \
  --name "${CONTAINER_NAME}" \
  -e POSTGRES_USER="${POSTGRES_USER}" \
  -e POSTGRES_PASSWORD="${POSTGRES_PASSWORD}" \
  -e POSTGRES_DB="${POSTGRES_DB}" \
  -p "${HOST_PORT}:5432" \
  -v "${DATA_DIR}:/var/lib/postgresql/data" \
  "${IMAGE_NAME}"

echo "✅  PostgreSQL + pgvector deployed successfully!"
echo "   Host port: ${HOST_PORT}, DB: ${POSTGRES_DB}, User: ${POSTGRES_USER}"