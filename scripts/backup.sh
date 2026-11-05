#!/usr/bin/env bash
# 一键备份 MySQL + Milvus 三件套数据卷。用法:./scripts/backup.sh
set -euo pipefail
cd "$(dirname "$0")/.."

OUT="${BACKUP_DIR:-./backup}"
mkdir -p "$OUT"
STAMP="$(date +%Y%m%d-%H%M%S)"

echo "备份 MySQL -> $OUT/mysql-$STAMP.sql"
docker exec mewhelp-mysql sh -c 'exec mysqldump --all-databases -uroot -proot --single-transaction' > "$OUT/mysql-$STAMP.sql"

for vol in mewhelp_mewhelp-milvus-data mewhelp_mewhelp-milvus-etcd mewhelp_mewhelp-milvus-minio; do
  name="${vol##*_}"
  echo "备份 $vol -> $OUT/$name-$STAMP.tgz"
  docker run --rm -v "$vol":/mnt -v "$(pwd)/$OUT":/backup alpine \
    tar czf "/backup/$name-$STAMP.tgz" -C /mnt .
done

echo "完成:$OUT"

