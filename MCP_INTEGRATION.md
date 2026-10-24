# MCP 集成说明

## 1. 实际使用的 Server 与 Tool

| 项目 | 值 |
|---|---|
| Server | 麦当劳中国 MCP `mcd-mcp` |
| Endpoint | `https://mcp.mcd.cn` |
| Transport | Streamable HTTP |
| 认证 | `Authorization: Bearer $MCD_MCP_TOKEN` |
| 真实运行链使用的 Tool | `order-list` |
| 权限边界 | 只读历史订单；不执行任何写操作 |

`order-list` 用于查询近期到店或外送历史订单。项目不会把活动快照或合成预设描述为实时 MCP 调用结果。

## 2. 调用流程

用户主流程由浏览器完成：

1. 用户展开真实订单导入，在密码框中输入自己的 Token。
2. 页面发送 `initialize`，协商协议版本 `2025-06-18` 并保存服务端返回的 Session ID。
3. 页面发送 `notifications/initialized`。
4. 页面发送 `tools/call`，Tool 为 `order-list`，参数为空对象。
5. 解析 JSON 或 SSE 响应，再从 `result.content[].text` 中提取业务内容。
6. 若内容含 `## Original Response`，解析该标记之后的 JSON。
7. 前端规范化订单、拆分套餐单品并映射为餐品，用户选择一条订单导入。
8. 用户选择心情与星级后，`compileSongScore()` 生成音符事件，用于动画、实时播放和 WAV 渲染。

浏览器直连可能受到 CORS、网络或服务端策略影响；失败时页面会明确提示，不会用模拟订单冒充真实返回。

`scripts/mcp_engine.py --live-order-list` 提供相同的只读调用顺序，供开发者从本机导出并核验原始响应；导出的文件不再用于页面导入。

## 3. 关键数据结构

为兼容已记录的返回形式，解析器支持外层为 Markdown、业务 JSON 位于以下标记之后的情况：

```text
## Original Response
```

之后。常见订单字段：

```text
data.orderList[]
  ├── orderId
  ├── shopName / storeCode / createTime
  └── orderProductList[]
        ├── productName / quantity
        └── comboItemList[]       套餐中的具体单品
```

前端对应函数：

| 函数 | 职责 |
|---|---|
| `extractMcpJson()` | 从 Markdown 或混合文本中提取 JSON |
| `findOrders()` | 支持原始订单、查询详情及本地预设包结构 |
| `normalizeOrder()` | 统一订单号、门店、时间和餐品字段 |
| `classifyItems()` | 将真实名称映射为汉堡、小食、饮品或未识别项 |

## 4. 业务价值

- **真实输入**：历史订单中的餐品名称映射为可见餐盘；汉堡映射结果与心情、星级共同决定音乐动机。未识别项保留原名，近似映射会明确标注。
- **低理解成本**：用户只需选餐、选心情、播放三步，不需要理解 MCP 或音频编程。
- **可带走的结果**：实时播放与 WAV 下载共享音符事件；二维码只恢复短 ID、汉堡、心情和星级，不恢复完整订单或小票文案。
- **可复验接入**：在线调用、原始响应解析、前端导入各自可独立检查，失败时不会把演示数据冒充真实返回。

## 5. 只读红线

Python 客户端在调用前显式拒绝以下写工具：

- `create-order`
- `cancel-order`
- `draw-lottery`
- `mall-create-order`
- `auto-bind-coupons`
- `party-order-create`
- `delivery-create-address`

当前真实运行链只调用 `order-list`，不调用其他读写工具。

## 6. Token、订单与分享安全

- `mcp-config.example.json` 只保存 `${MCD_MCP_TOKEN}` 环境变量占位符。
- 真实订单建议导出至系统临时目录，不进入 Git。
- 页面不将 Token 写入 localStorage；日志不得输出 Token。
- 公开二维码仅包含短 ID、汉堡、心情和星级，不包含原始订单号与门店信息。
- 真实订单文件和电子小票在公开分享前仍需人工检查。

## 7. 验证说明

已完成本地无凭证验证：

- MCP JSON / `Original Response` 解包测试。
- 原始 `order-list` 结构提取测试。
- 5 组本地预设全部可被前端识别，首组 4 个餐品完整导入。
- Python 客户端包含写工具拒绝逻辑。

真实在线 `order-list` 结果由参赛者使用自己的 Token 在本机验收；本文件不伪造在线调用证据。
