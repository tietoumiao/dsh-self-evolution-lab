-- ingest-api 部署参数基准表
-- 本文件每个字段的 DEFAULT 就是基准值；线上配置必须以这里的值为准。

CREATE TABLE deployment_params (
    service          TEXT     NOT NULL,
    max_connections  INTEGER  NOT NULL DEFAULT 100,
    retry_timeout_ms INTEGER  NOT NULL DEFAULT 2500,
    queue_capacity   INTEGER  NOT NULL DEFAULT 4096,
    shard_count      INTEGER  NOT NULL DEFAULT 8,
    batch_size       INTEGER  NOT NULL DEFAULT 256,
    PRIMARY KEY (service)
);
