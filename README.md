# KXNS CLI

[![Commit Activity](https://img.shields.io/github/commit-activity/w/Wyl-cmd/KXNS-CLI)](https://github.com/Wyl-cmd/KXNS-CLI/graphs/commit-activity)
[![Checks](https://img.shields.io/github/check-runs/Wyl-cmd/KXNS-CLI/main)](https://github.com/Wyl-cmd/KXNS-CLI/actions)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/Wyl-cmd/KXNS-CLI)

KXNS CLI 是一个专注于网络安全和渗透测试的专用AI代理，基于Kimi Code CLI构建。它帮助安全专业人员执行漏洞评估、安全审计和渗透测试任务，具备智能自动化和分析能力。

> [!重要提示]
> KXNS CLI 目前处于技术预览阶段。

## 快速开始

访问[快速开始指南](https://moonshotai.github.io/kimi-cli/en/guides/getting-started.html)了解如何安装和使用KXNS CLI进行安全测试。

## 核心功能

### 安全增强的Shell模式

KXNS CLI 提供专为渗透测试设计的安全增强Shell环境。你可以通过按 `Ctrl-X` 切换到Shell命令模式。在此模式下，你可以直接运行安全工具、网络扫描器和漏洞利用载荷，无需离开代理环境。

> [!注意]
> 目前不支持 `cd` 等内置Shell命令。

### IDE集成（ACP协议）

KXNS CLI 原生支持[Agent Client Protocol]，能够与安全专注的IDE和代码编辑器无缝集成。非常适合编写漏洞利用、分析漏洞和记录安全发现。

[Agent Client Protocol]: https://github.com/agentclientprotocol/agent-client-protocol

要将KXNS CLI与ACP客户端一起使用，请确保已配置好API。然后，你可以配置ACP客户端使用命令 `kxns acp` 启动KXNS CLI作为ACP代理服务器。

例如，要将KXNS CLI与[Zed](https://zed.dev/)或[JetBrains](https://blog.jetbrains.com/ai/2025/12/bring-your-own-ai-agent-to-jetbrains-ides/)一起使用，请将以下配置添加到你的 `~/.config/zed/settings.json` 或 `~/.jetbrains/acp.json` 文件中：

```json
{
  "agent_servers": {
    "KXNS CLI": {
      "command": "kxns",
      "args": ["acp"],
      "env": {}
    }
  }
}
```

然后你可以在IDE的代理面板中创建KXNS CLI线程。

### Zsh集成用于安全工作流

你可以将KXNS CLI与Zsh一起使用，为你的安全研究和渗透测试工作流提供AI代理能力。

通过以下方式安装[zsh-kimi-cli](https://github.com/Wyl-cmd/KXNS-CLI)插件：

```sh
git clone https://github.com/Wyl-cmd/KXNS-CLI.git \
  ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/kimi-cli
```

> [!注意]
> 如果你使用的是Oh My Zsh以外的插件管理器，可能需要参考插件的README获取安装说明。

然后在 `~/.zshrc` 中将 `kimi-cli` 添加到你的Zsh插件列表：

```sh
plugins=(... kimi-cli)
```

重启Zsh后，你可以通过按 `Ctrl-X` 切换到代理模式，快速访问安全工具和漏洞开发辅助。

### 安全工具的MCP支持

KXNS CLI 支持MCP（Model Context Protocol）工具，能够与专业安全工具和漏洞数据库集成。

**`kxns mcp` 子命令组**

你可以使用 `kxns mcp` 子命令组管理MCP服务器。例如：

```sh
# 添加安全漏洞数据库服务器：
kxns mcp add --transport http vuln-db https://api.vulndb.com/mcp --header "API_KEY: your-key"

# 添加漏洞利用框架集成：
kxns mcp add --transport http --auth oauth metasploit https://mcp.metasploit.com/mcp

# 添加网络扫描工具：
kxns mcp add --transport stdio nmap-scanner -- npx nmap-mcp@latest

# 列出已添加的MCP服务器：
kxns mcp list

# 移除MCP服务器：
kxns mcp remove nmap-scanner

# 授权MCP服务器：
kxns mcp auth metasploit
```

**临时MCP配置**

KXNS CLI 还支持通过CLI选项进行临时MCP服务器配置。

给定一个已知MCP配置格式的MCP配置文件，如下所示：

```json
{
  "mcpServers": {
    "cve-database": {
      "url": "https://api.cvedb.com/mcp",
      "headers": {
        "API_KEY": "YOUR_API_KEY"
      }
    },
    "burp-suite": {
      "command": "burp",
      "args": ["--mcp"]
    }
  }
}
```

使用 `--mcp-config-file` 选项运行 `kxns` 以连接到指定的MCP服务器：

```sh
kxns --mcp-config-file /path/to/security-mcp.json
```

### 安全工具集成

KXNS CLI 提供统一的管理接口，用于管理安全测试工具和漏洞扫描器，无需手动编辑配置文件。

**`kxns api` 子命令组**

你可以使用 `kxns api` 子命令组管理安全工具配置。例如：

```sh
# 添加安全专注的LLM模型：
kxns api add -p openai -m gpt-4o -u https://api.openai.com/v1 -k sk-xxx -C 128000 -c thinking,image_in -d

# 列出所有配置的安全工具：
kxns api list

# 移除安全工具配置：
kxns api remove -p openai -m gpt-4o

# 设置默认安全分析模型：
kxns api set-default gpt-4o

# 测试工具连接：
kxns api test -p openai -m gpt-4o
```

查看[kxns api命令文档](./docs/en/reference/kxns-api-command.md)了解更多详情。

### 安全测试工作流

KXNS CLI 在AI辅助下自动化安全测试工作流方面表现出色：

**漏洞评估**
```sh
# 扫描目标并分析发现
kxns --prompt "扫描 192.168.1.0/24 的开放端口并识别潜在漏洞"

# 分析CVE报告
kxns --prompt "分析 CVE-2024-1234 漏洞并建议缓解策略"
```

**渗透测试**
```sh
# 生成漏洞利用载荷
kxns --prompt "为 http://target.com/login 的登录表单创建SQL注入载荷"

# 记录安全发现
kxns --prompt "基于 scan_results.txt 中的扫描结果生成渗透测试报告"
```

**安全代码审查**
```sh
# 审查代码的安全问题
kxns --prompt "审查 auth.py 的身份验证绕过漏洞"

# 建议安全改进
kxns --prompt "分析加密实现并建议改进"
```

### 更多功能

在[文档](https://moonshotai.github.io/kimi-cli/en/)中查看更多功能。

## 开发

要开发KXNS CLI的安全测试功能，请运行：

```sh
git clone https://github.com/Wyl-cmd/KXNS-CLI.git
cd KXNS-CLI

make prepare  # 准备开发环境
```

然后你可以开始开发KXNS CLI的安全功能。

进行更改后，请参考以下命令：

```sh
uv run kxns  # 运行KXNS CLI
make format  # 格式化代码
make check  # 运行linting和类型检查
make test  # 运行测试
make test-kimi-cli  # 仅运行KXNS CLI测试
make test-kosong  # 仅运行kosong测试
make test-pykaos  # 仅运行pykaos测试
make build  # 构建Python包
make build-bin  # 构建独立二进制文件
make help  # 显示所有make目标
```

## 贡献

我们欢迎对KXNS CLI的贡献！这是一个安全专注的项目，我们特别重视以下方面的贡献：

- 新的安全工具集成和MCP服务器
- 渗透测试工作流和自动化
- 漏洞分析能力
- 安全文档和示例

请参考[CONTRIBUTING.md](./CONTRIBUTING.md)了解更多信息。

## 安全免责声明

KXNS CLI 专为授权的安全测试、漏洞评估和教育目的而设计。用户有责任确保在测试任何系统之前获得适当授权。未经授权访问计算机系统是非法和不道德的。

## 许可证

本项目根据Apache License 2.0获得许可。
