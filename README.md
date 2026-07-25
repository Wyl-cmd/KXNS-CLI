# KXNS Hunter CLI

[![Version](https://img.shields.io/badge/version-1.0.0-green)](https://github.com/Wyl-cmd/kxns-cli)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-ASL--2.0-yellow)](LICENSE)

**KXNS Hunter CLI** 是一款专注于渗透测试的 AI 智能体命令行工具，帮助你完成安全评估、漏洞分析和渗透测试任务。它能够读取和编辑代码、执行 Shell 命令、搜索和抓取网页内容，并在执行过程中自主规划和调整行动。

## 功能特性

- 🛡️ **安全导向**：专为渗透测试和安全评估设计
- 🔧 **Shell 集成**：内置 Shell 命令模式，使用 Ctrl-X 切换
- 🌐 **Web 界面**：内置 Web 用户界面，提供更好的交互体验
- 🔌 **MCP 支持**：支持模型上下文协议（Model Context Protocol），可扩展工具集成
- 📦 **便捷部署**：提供 Windows 和 Linux 的简易安装脚本
- 🔄 **跨平台构建**：支持 Nix Flakes 和 uv 锁定，确保环境一致性

## 安装

### 前置要求

- Python 3.12 或更高版本
- pip（Python 包管理器）

### 快速安装

**Windows（PowerShell）：**
```powershell
.\install.ps1
```

**Linux/macOS：**
```bash
chmod +x install.sh
./install.sh
```

### 手动安装

```bash
# 创建虚拟环境（推荐）
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# 或
.\.venv\Scripts\Activate.ps1  # Windows

# 安装依赖
pip install -r requirements.txt

# 开发模式安装
pip install -e .
```

### 使用 uv 安装（推荐）

```bash
# 安装 uv
pip install uv

# 根据 uv.lock 精确安装所有依赖
uv sync
```

### 使用 Nix 安装（Linux/macOS）

```bash
# 进入开发环境
nix develop

# 直接构建
nix build

# 运行
nix run
```

## 配置

### API 配置

使用 `api` 命令配置 LLM API 设置：

```bash
kxns api <url> <api_key> <model> [选项]
```

#### 参数

| 参数 | 说明 | 必填 |
|------|------|------|
| `url` | LLM API 基础 URL | 是 |
| `api_key` | LLM API 密钥 | 是 |
| `model` | LLM 模型名称 | 是 |

#### 选项

| 选项 | 简写 | 说明 | 默认值 |
|------|------|------|--------|
| `--max-context` | `-x` | 最大上下文大小（token 数） | 128000 |
| `--image-input` | `-i` | 启用图片输入能力 | False |
| `--thinking` | `-t` | 启用思考模式 | False |

#### 示例

```bash
# 基本配置
kxns api https://api.openai.com/v1 sk-your-api-key gpt-4

# 自定义上下文大小
kxns api https://api.openai.com/v1 sk-your-api-key gpt-4 -x 200000

# 启用图片输入能力
kxns api https://api.openai.com/v1 sk-your-api-key gpt-4-vision -i

# 启用思考模式
kxns api https://api.anthropic.com/v1 sk-your-api-key claude-3-5-sonnet -t

# 启用所有能力
kxns api https://api.openai.com/v1 sk-your-api-key gpt-4-vision -x 200000 -i -t

# 自定义 API 提供商
kxns api https://api.example.com/v1 sk-your-api-key your-model -x 128000
```

### 配置文件

配置文件存储在 `~/.kxns/config.toml`：

```toml
# KXNS Hunter CLI 配置
# 由 kxns api 命令生成

default_model = "your-model"

[models.your-model]
provider = "custom"
model = "your-model"
max_context_size = 128000
capabilities = ["image_in", "thinking"]

[providers.custom]
type = "openai_legacy"
base_url = "https://api.example.com/v1"
api_key = "sk-your-api-key"
```

#### 配置字段说明

| 字段 | 说明 |
|------|------|
| `default_model` | 默认使用的模型 |
| `default_thinking` | 默认启用思考模式 |
| `models.<name>.provider` | 该模型的提供商名称 |
| `models.<name>.model` | 模型标识符 |
| `models.<name>.max_context_size` | 最大上下文大小（token 数） |
| `models.<name>.capabilities` | 模型能力：`image_in`、`thinking`、`video_in`、`always_thinking` |
| `providers.<name>.type` | 提供商类型：`openai_legacy`、`anthropic` 等 |
| `providers.<name>.base_url` | API 基础 URL |
| `providers.<name>.api_key` | API 密钥 |

## 使用

### 基本用法

```bash
# 启动交互式会话
kxns

# 使用提示词运行
kxns -p "分析此代码库的安全漏洞"

# 继续上一次会话
kxns --continue

# 使用指定会话
kxns --session <session_id>
```

### Shell 模式

按 `Ctrl-X` 在智能体模式和 Shell 模式之间切换。在 Shell 模式下，可以直接运行 Shell 命令。

### MCP 支持

管理 MCP 服务器：

```bash
# 添加 MCP 服务器
kxns mcp add --transport http server-name https://mcp.example.com/mcp

# 列出 MCP 服务器
kxns mcp list

# 移除 MCP 服务器
kxns mcp remove server-name
```

### Web 界面

启动 Web 界面：

```bash
kxns web
```

### 扫描编排（Scan）

```bash
# 环境检查
kxns doctor

# 全自动扫描（Wildcard 侦察 → Guaranteed 验证 → 报告）
kxns scan run https://target.example --wildcard --guaranteed --print --yolo

# 交互里也可用：/hunt <url> 或 /scan <url>
```

无 PostgreSQL 时可在 `~/.kxns/config.toml` 使用内存黑板：

```toml
[blackboard]
backend = "memory"
require_postgres = false
```

## 构建

### 构建二进制文件

**Windows（PowerShell）：**
```powershell
.\build.ps1
```

**Linux/macOS：**
```bash
chmod +x build.sh
./build.sh
```

构建产物将输出到 `dist/` 目录。

### 使用 Nix 构建

```bash
nix build
```

## 开发

### 搭建开发环境

```bash
# 克隆仓库
git clone https://github.com/Wyl-cmd/kxns-cli.git
cd kxns-cli

# 安装开发依赖
pip install -r requirements-dev.txt
pip install -e .

# 或使用 uv
uv sync

# 或使用 Nix
nix develop
```

### 运行测试

```bash
pytest tests/
```

### 代码格式化

```bash
ruff format .
ruff check .
```

## 免责声明

本工具仅用于授权的安全测试。在对任何系统执行渗透测试之前，请务必获取合法授权。开发者不对本工具的任何滥用行为承担责任。
