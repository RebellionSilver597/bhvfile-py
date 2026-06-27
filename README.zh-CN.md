# BHV 文件编辑器

基于 Python 的 BHV 文件编辑器，集成 FastAPI 后端、Web 界面和 MCP（模型上下文协议）服务器。

## 概述

BHV 文件是游戏模组中使用的二进制动画/数据文件。本工具提供：

- **二进制解析器** — 读取并解析 `.bhv` 文件，完整支持所有数据结构
- **二进制写入器** — 将修改后的 BHV 文件写回磁盘
- **Web 界面** — 基于浏览器的可视化编辑器
- **REST API** — FastAPI 后端，提供 20+ 个 API 端点
- **MCP 服务器** — 通过模型上下文协议集成 AI 代理（支持 stdio 和 HTTP 两种模式）

## 快速开始

```bash
# 安装依赖
pip install fastapi uvicorn python-multipart

# 启动服务
python run.py

# 浏览器打开
# http://localhost:8000
```

## 项目结构

```
bhvfile-py/
├── run.py                     # 一键启动脚本 (uvicorn + FastAPI)
├── mcp_run_http.py            # 独立 MCP HTTP 服务器
├── test_read.py               # 诊断读取脚本
├── output.bhv                 # 示例输出文件
├── backend/
│   ├── app.py                 # FastAPI 后端 (REST API)
│   ├── mcp_server.py          # MCP 服务器 (stdio 模式)
│   ├── mcp_http_server.py     # MCP 服务器 (HTTP/StreamableHTTP 模式)
│   └── model/
│       ├── bhv_file.py        # 数据模型 (BHVFile, Header, State 等)
│       ├── binary_reader.py   # BHV 二进制文件读取/解析器
│       └── binary_writer.py   # BHV 二进制文件写入器
├── frontend/                  # Web 前端
└── backend/requirements.txt   # Python 依赖
```

## 架构说明

### 数据模型 (`backend/model/bhv_file.py`)
完全对应 C# BHVEditor 的数据结构，包括：
- `BHVFile` — 根容器，包含 Header、States、StructBs/Cs/Ds
- `Header` — 0x20 字节文件头
- `State` — 动画状态，包含 Transitions 和 Conditions
- `Transition`, `Condition`, `StructABB`, `StructB`, `StructD`, `StructDA`

### 二进制解析器 (`backend/model/binary_reader.py`)
- 从偏移 0x20 开始读取 BHV 文件
- 自动检测文件类型（basenormal、weapon、通用）
- 解析状态、转换、条件及所有二进制结构

### 二进制写入器 (`backend/model/binary_writer.py`)
- 两阶段写入：先计算所有偏移，再按 C# 兼容顺序写入
- 输出与原始 C# 实现字节一致

### API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/file/open` | 打开 BHV 文件 |
| POST | `/api/file/save` | 保存当前文件 |
| POST | `/api/file/export-json` | 导出为 JSON |
| POST | `/api/file/import-json` | 从 JSON 导入 |
| GET | `/api/data` | 获取当前文件数据 |
| PUT | `/api/data` | 更新文件数据 |
| POST | `/api/state` | 添加新状态 |
| PUT/DELETE | `/api/state/{index}` | 更新/删除状态 |
| POST | `/api/state/duplicate/{index}` | 复制状态 |
| POST/DELETE | `/api/state/{index}/transition` | 管理过渡 |
| PUT | `/api/structb`, `/api/structc` | 更新二进制结构 |
| GET | `/api/debug` | 调试信息 |

### MCP 集成

支持通过模型上下文协议集成 AI 代理：

- **stdio 模式**: `backend/mcp_server.py` — 供本地 AI 代理使用
- **HTTP 模式**: `mcp_run_http.py` — StreamableHTTP 传输，端口 8001

## 技术栈

- **后端**: Python 3.11+, FastAPI, Uvicorn
- **前端**: HTML/CSS/JS（内置）
- **MCP**: FastMCP 库
- **文件格式**: 自定义 BHV 二进制格式

## 许可证

MIT
