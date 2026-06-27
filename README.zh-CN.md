# BHV 文件编辑器 — 适用于装甲核心6 (Armored Core 6)

基于 Python 的 **装甲核心6 (AC6) 行为 BHV 文件编辑器**。BHV 文件是控制游戏中敌人行为、Boss 阶段和动作序列的二进制动画/状态机文件。

本工具提供 **Web 界面**、**REST API** 和 **MCP（模型上下文协议）服务器**三种操作方式，完全兼容 C# BHVEditor 格式。

---

## 目录

- [什么是 BHV 文件？](#什么是-bhv-文件)
- [快速开始](#快速开始)
- [Web 界面（浏览器）](#web-界面浏览器)
- [REST API（curl/Python/任意 HTTP 客户端）](#rest-apicurlpython任意-http-客户端)
- [MCP 服务器（AI 代理集成）](#mcp-服务器ai-代理集成)
- [项目结构](#项目结构)
- [架构说明](#架构说明)
- [API 参考](#api-参考)
- [技术栈](#技术栈)

---

## 什么是 BHV 文件？

BHV 文件是 **装甲核心6 (Armored Core 6)** 的二进制行为文件，通常位于游戏 `chr/` 目录下（如 `c0001-behbnd-dcx/chr/c0001.bhv` 或 `basenormal.bhv`）。它们定义了：

- **状态机** — 每个状态代表一种行为（待机、攻击、硬直、死亡等）
- **过渡** — 基于条件在状态之间切换的规则
- **条件** — 触发条件：HP 阈值、与玩家距离、计时器、随机等
- **StructB / StructC / StructD** — 额外的二进制配置数据

三种文件类型：
| 类型 | 枚举值 | 文件名 | 说明 |
|------|--------|--------|------|
| `basenormal.bhv` | `BASENORMAL` | `basenormal.bhv` | 基础敌人/士兵行为状态机 |
| `weapon.bhv` | `WEAPON` | `weapon.bhv` | 武器行为 — 定义武器如何调用动画 |
| `w.bhv` | `W` | `w.bhv` | 通用行为文件（结构与 weapon 相同）|

**武器 BHV 文件**（`weapon.bhv` / `w.bhv`）用于武器**调用和控制动画**。每个 State 对应一个动画 ID（`Unk04` 字段），Transitions 定义动画之间的切换条件（如：射击 → 换弹 → 待机）。

### 关键字段说明

| 字段 | 含义 |
|------|------|
| `State.Unk04` | 动画 ID — 该状态调用的动画编号 |
| `Transition.StateIndex` | 目标状态索引 — 跳转到哪个状态 |
| `Transition.StructAbb.BehaviorMatrixParam_f/i` | 行为矩阵参数（AI 决策权重）|
| `Condition.Id` | 条件类型（HP 阈值、距离、计时器、随机等）|
| `Condition.Data` | 条件参数（十六进制字节）|

---

## 快速开始

```bash
# 1. 安装依赖
pip install fastapi uvicorn python-multipart

# 2. 启动服务
python run.py

# 3. 浏览器打开
#    http://localhost:8000
```

### 关闭服务

在运行服务的终端中按 `Ctrl+C` 即可停止。

---

## Web 界面（浏览器）

打开 **http://localhost:8000** 即可进入可视化编辑器。

### 工作流程

```
1. 点击 "Open BHV"  →  选择本地的 .bhv 文件
2. 在可视化界面中编辑状态、过渡、条件
3. 点击 "Save BHV"  →  下载修改后的 .bhv 文件
```

### Web 界面功能

编辑器是一个**基于 Canvas 的状态机可视化编辑器**，包含多个面板。

#### 工具栏

| 按钮 | 快捷键 | 说明 |
|------|--------|------|
| 📂 打开 BHV | — | 选择并打开本地的 `.bhv` 文件 |
| 📥 导入 JSON | — | 从之前导出的 JSON 文件导入 |
| 📤 导出 JSON | — | 导出当前文件为 JSON（用于备份/检查）|
| 🐛 载入调试 JSON | — | 加载带状态名称的调试 JSON（来自游戏数据）|
| 💾 保存 BHV | — | 保存并下载修改后的 `.bhv` 文件 |
| ➕ 新建状态 | — | 在列表末尾添加一个新的空状态 |
| ↩ 撤销 / ↪ 重做 | `Ctrl+Z` / `Ctrl+Y` | 撤销/重做编辑操作 |
| 🌐 中/EN | — | 切换中英文界面 |

#### 面板（标签页切换）

**画布面板** — 可视化状态机编辑器
```
┌──────────────────────────────────────────────┐
│  [Anim1 过滤] [Anim2 过滤] [搜索状态名/ID]      │
│  [100%] [+] [−] [⊞ 适应] [节点: 0] [2跳] [0,0]   │
│                                              │
│         ┌─────┐     ┌─────┐                  │
│         │ S0  │────→│ S1  │                  │
│         │ idle│     │atk1 │                  │
│         └─────┘     └─────┘                  │
│            │                                  │
│            ↓                                  │
│         ┌─────┐                               │
│         │ S2  │                               │
│         │atk2 │                               │
│         └─────┘                               │
│  [小地图]                                      │
└──────────────────────────────────────────────┘
```

- **节点** 代表状态 — 拖拽可调整位置
- **箭头** 代表过渡 — 点击可编辑
- **Anim1/Anim2 过滤** — 高亮显示匹配动画 ID 的状态
- **搜索** — 按状态名称或索引查找
- **缩放** — `+`/`−`/`⊞ 适应`（自适应）
- **节点数** — 显示状态总数
- **焦点层级** — 限制显示的过渡跳数
- **小地图** — 整个状态图的缩略概览（点击可导航）

**StructB 面板** — 编辑 StructB 条目（二进制配置数组）

**StructC 面板** — 编辑 StructC 条目（整数数组数据）

**Strings 面板** — 编辑字符串列表

**Mystery 面板** — 编辑 MysteryBlock（十六进制原始数据）

**JSON 面板** — 查看当前文件的完整原始 JSON 数据


### 快速操作指南

| 操作 | 方法 |
|------|------|
| 打开 BHV 文件 | 点击 "Open BHV" 按钮，选择 `.bhv` 文件 |
| 保存为 BHV | 点击 "Save BHV" — 下载修改后的文件 |
| 导出为 JSON | 点击 "Export JSON" — 用于检查或备份 |
| 从 JSON 导入 | 点击 "Import JSON" — 从备份恢复 |
| 添加状态 | 点击 "Add State" |
| 删除状态 | 点击状态卡片上的删除图标 |
| 复制状态 | 点击复制图标 |
| 添加过渡 | 在状态上点击 "Add Transition" |
| 删除过渡 | 点击过渡卡片上的 X |

---

## REST API（curl/Python/任意 HTTP 客户端）

后端运行在 `http://127.0.0.1:8000`，可通过程序化方式调用。

### 文件操作

```bash
# 打开 BHV 文件
curl -X POST http://127.0.0.1:8000/api/file/open \
  -F "file=@basenormal.bhv"

# 导出为 JSON
curl -X POST http://127.0.0.1:8000/api/file/export-json \
  -o output.json

# 从 JSON 导入
curl -X POST http://127.0.0.1:8000/api/file/import-json \
  -F "file=@output.json"

# 保存为 BHV（下载）
curl -X POST http://127.0.0.1:8000/api/file/save \
  -o modified.bhv
```

### 数据操作

```bash
# 获取当前文件数据（JSON 格式）
curl http://127.0.0.1:8000/api/data

# 更新全部数据
curl -X PUT http://127.0.0.1:8000/api/data \
  -H "Content-Type: application/json" \
  -d @your_data.json
```

### 状态管理

```bash
# 添加新状态
curl -X POST http://127.0.0.1:8000/api/state

# 更新索引 2 的状态
curl -X PUT http://127.0.0.1:8000/api/state/2 \
  -H "Content-Type: application/json" \
  -d '{"Index":2,"Unk04":0,...}'

# 删除索引 2 的状态
curl -X DELETE http://127.0.0.1:8000/api/state/2

# 复制索引 2 的状态
curl -X POST http://127.0.0.1:8000/api/state/duplicate/2
```

### 过渡管理

```bash
# 给状态 2 添加一个过渡（目标状态 5）
curl -X POST http://127.0.0.1:8000/api/state/2/transition \
  -H "Content-Type: application/json" \
  -d '{"StateIndex":5}'

# 更新状态 2 的过渡 0
curl -X PUT http://127.0.0.1:8000/api/state/2/transition/0 \
  -H "Content-Type: application/json" \
  -d '{"StateIndex":3,"StructAbb":{"Unk01":1}}'

# 删除状态 2 的过渡 0
curl -X DELETE http://127.0.0.1:8000/api/state/2/transition/0

# 批量粘贴过渡
curl -X POST http://127.0.0.1:8000/api/state/2/transitions/paste \
  -H "Content-Type: application/json" \
  -d '{"transitions":[{"StateIndex":3},{"StateIndex":5}]}'
```

### 二进制数据结构操作

```bash
# 更新 StructB 列表
curl -X PUT http://127.0.0.1:8000/api/structb \
  -H "Content-Type: application/json" \
  -d '[{"Unk04":0,"Unk08":0,"Unk0C":0,"Unk10":0}]'

# 更新 StructC 列表
curl -X PUT http://127.0.0.1:8000/api/structc \
  -H "Content-Type: application/json" \
  -d '[[0,0,0,0]]'

# 更新字符串列表
curl -X PUT http://127.0.0.1:8000/api/strings \
  -H "Content-Type: application/json" \
  -d '["idle","attack","stagger"]'

# 更新 MysteryBlock（十六进制）
curl -X PUT http://127.0.0.1:8000/api/mystery \
  -H "Content-Type: application/json" \
  -d '{"hex":"00 01 02 FF"}'
```

### 调试

```bash
# 加载调试 JSON（状态名称信息）
curl -X POST http://127.0.0.1:8000/api/file/load-debug-json \
  -F "file=@debug_states.json"

# 获取调试信息
curl http://127.0.0.1:8000/api/debug

# 获取状态索引→名称映射
curl http://127.0.0.1:8000/api/debug/state-names

# 获取状态 2 的调试过渡信息
curl http://127.0.0.1:8000/api/debug/transitions/2
```

### API 文档

服务运行时访问：
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## MCP 服务器（AI 代理集成）

项目提供两种 MCP 模式，供 AI 代理通过模型上下文协议集成。

### stdio 模式（本地 AI 代理使用）

```bash
python backend/mcp_server.py
```

在 MCP 客户端配置（如 `~/.hermes/config.yaml`）：
```yaml
mcp_servers:
  bhv-editor:
    command: "python"
    args: ["D:/Materials/bhvfile-py/backend/mcp_server.py"]
    timeout: 120
```

### HTTP 模式（远程 AI 代理使用）

```bash
python mcp_run_http.py
# 运行在 http://127.0.0.1:8001/mcp
```

配置：
```yaml
mcp_servers:
  bhv-editor:
    url: "http://127.0.0.1:8001/mcp"
    timeout: 120
```

### MCP 可用工具

| 工具 | 说明 |
|------|------|
| `open_bhv` | 打开 BHV 文件进行编辑 |
| `save_bhv` | 保存当前文件为 BHV |
| `export_json` | 导出为 JSON |
| `import_json` | 从 JSON 导入 |
| `get_data` | 获取当前文件数据 |
| `update_data` | 更新全部数据 |
| `add_state` | 添加新状态 |
| `update_state` | 按索引更新状态 |
| `delete_state` | 按索引删除状态 |
| `duplicate_state` | 复制状态 |
| `add_transition` | 给状态添加过渡 |
| `update_transition` | 更新过渡 |
| `delete_transition` | 删除过渡 |
| `paste_transitions` | 批量粘贴过渡 |
| `update_structb` | 更新 StructB 列表 |
| `update_structc` | 更新 StructC 列表 |
| `update_strings` | 更新字符串列表 |
| `update_mystery` | 更新 MysteryBlock |

---

## 项目结构

```
bhvfile-py/
├── run.py                     # 一键启动脚本（启动 FastAPI，端口 8000）
├── mcp_run_http.py            # 独立 MCP HTTP 服务器（端口 8001）
├── test_read.py               # BHV 文件读取诊断脚本
├── output.bhv                 # 示例输出文件
├── .gitignore
├── README.md                  # 英文说明
├── README.zh-CN.md            # 中文说明（本文件）
├── backend/
│   ├── app.py                 # FastAPI 后端 — 所有 REST API 端点
│   ├── mcp_server.py          # MCP 服务器 — stdio 传输模式
│   ├── mcp_http_server.py     # MCP 服务器 — HTTP/StreamableHTTP 传输
│   ├── requirements.txt       # Python 依赖
│   └── model/
│       ├── __init__.py
│       ├── bhv_file.py        # 数据模型: BHVFile, Header, State, Transition, Condition 等
│       ├── binary_reader.py   # 二进制解析器: 从偏移 0x20 开始读取 .bhv
│       └── binary_writer.py   # 二进制写入器: 两阶段偏移计算 + C# 兼容输出
├── frontend/
│   └── index.html             # 单页 Web 界面
```

---

## 架构说明

### 数据模型 (`backend/model/bhv_file.py`)
完全对应 AC6 模组社区使用的 C# BHVEditor 数据结构：
- `BHVFile` — 根容器: Header + States + StructBs/Cs/Ds + Strings + MysteryBlock
- `Header` — 32 字节文件头（版本、标志、偏移、计数）
- `State` — 动画行为状态，包含过渡和条件
- `Transition` — 状态之间的链接，附带条件
- `Condition` — 触发规则（HP、距离、计时器、随机等）
- `StructABB` / `StructB` / `StructD` / `StructDA` — 额外二进制结构

### 二进制解析器 (`backend/model/binary_reader.py`)
- 从偏移 `0x20` 开始读取 BHV 文件
- 自动检测文件类型: `basenormal`、`weapon` 或通用 `w`
- 解析所有状态、过渡、条件和二进制子结构
- 在内存中生成 `BHVFile` 对象

### 二进制写入器 (`backend/model/binary_writer.py`)
- **第一阶段**: 从状态表结束位置开始计算所有偏移
- **第二阶段**: 按 C# 兼容顺序写入（顺序写入，不 seek 到旧偏移）
- 输出与原始 C# BHVEditor 逐字节一致

---

## API 参考

### 文件端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/file/open` | 上传并打开 `.bhv` 二进制文件 |
| POST | `/api/file/save` | 保存当前文件为 `.bhv`（下载）|
| POST | `/api/file/export-json` | 导出当前模型为 JSON |
| POST | `/api/file/import-json` | 从 JSON 文件导入 |
| POST | `/api/file/load-debug-json` | 加载带状态名称的调试 JSON |

### 数据端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/data` | 获取完整的当前模型数据 |
| PUT | `/api/data` | 替换完整的模型数据 |

### 状态端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/state` | 添加新的空状态 |
| PUT | `/api/state/{index}` | 更新指定索引的状态 |
| DELETE | `/api/state/{index}` | 删除指定索引的状态 |
| POST | `/api/state/duplicate/{index}` | 复制指定索引的状态 |

### 过渡端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/state/{si}/transition` | 给状态 `si` 添加过渡 |
| PUT | `/api/state/{si}/transition/{ti}` | 更新状态 `si` 的过渡 `ti` |
| DELETE | `/api/state/{si}/transition/{ti}` | 删除状态 `si` 的过渡 `ti` |
| POST | `/api/state/{si}/transitions/paste` | 从剪贴板批量粘贴过渡 |

### 二进制数据端点

| 方法 | 路径 | 说明 |
|------|------|------|
| PUT | `/api/structb` | 更新 StructB 列表 |
| PUT | `/api/structc` | 更新 StructC 列表 |
| PUT | `/api/strings` | 更新字符串列表 |
| PUT | `/api/mystery` | 更新 MysteryBlock（十六进制字符串）|

### 调试端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/debug` | 获取已加载的调试信息 |
| GET | `/api/debug/state-names` | 获取状态索引→名称映射 |
| GET | `/api/debug/transitions/{index}` | 获取指定状态的调试过渡信息 |

---

## 技术栈

- **后端**: Python 3.11+, [FastAPI](https://fastapi.tiangolo.com/), [Uvicorn](https://www.uvicorn.org/)
- **前端**: 原生 HTML/CSS/JS（深色主题，单页应用）
- **MCP**: [FastMCP](https://github.com/jlowin/fastmcp) — 模型上下文协议
- **二进制格式**: 自定义 BHV — 装甲核心6 行为状态机格式

---

## 许可证

MIT
