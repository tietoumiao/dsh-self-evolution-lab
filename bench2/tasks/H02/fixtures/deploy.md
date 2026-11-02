# ingest-api 部署手册（值班抄录版）

下表取值是早班从线上 `config.json` 抄录的，方便值班快速查阅。
**参数基准以 `schema.sql` 里各字段的 `DEFAULT` 为准**；本表与基准不一致时，以基准为准。

| 参数 | 取值 | 说明 |
| --- | --- | --- |
| max_connections | 100 | 最大并发连接数 |
| retry_timeout_ms | 3000 | 单次重试超时，毫秒 |
| queue_capacity | 4096 | 队列容量 |
| shard_count | 8 | 分片数 |
| batch_size | 256 | 批量大小 |

## 备注

> 历史备注：2022 年的旧版本把 `retry_timeout_ms` 设成 5000，2023 年已调回，详见变更单 CHG-1187。
>
> `retry_backoff_ms`（重试退避，默认 250）不在部署参数表里，别和 `retry_timeout_ms` 混用。
