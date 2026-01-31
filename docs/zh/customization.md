# KXNS CLI 定制指南

KXNS CLI 是一个基于 Kimi Code CLI 的定制版本，本指南将帮助你根据自己的需求对项目进行定制。

## 项目概述

KXNS CLI 是一个功能强大的 AI 命令行工具，可以帮助你完成各种软件开发任务和终端操作。

### 主要特性

- ✅ AI API 管理功能（新增）
- ✅ Shell 命令模式
- ✅ ACP（Agent Client Protocol）集成
- ✅ MCP（Model Context Protocol）支持
- ✅ 多会话管理
- ✅ 代码编辑和调试
- ✅ 网络搜索和获取
- ✅ 可扩展的技能系统

## 项目重命名

### 修改项目名称

如果你想要修改项目名称（例如从 `kxns-cli` 改为其他名称），需要修改以下文件：

1. **pyproject.toml**
   ```toml
   [project]
   name = "your-new-name"
   ```

2. **包导入**
   在代码中将所有 `from kimi_cli` 改为 `from kxns_cli`

3. **配置文件路径**
   - 默认配置文件：`~/.kimi/config.toml` → `~/.kxns/config.toml`
   - 可以通过 `--config-file` 参数指定

### 修改欢迎信息

欢迎信息在 `src/kimi_cli/ui/shell/__init__.py` 文件中定义。

**当前代码：**
```python
head = Text.from_markup("Welcome to KXNS CLI!")
```

**修改为中文：**
```python
head = Text.from_markup("KXNS CLI 已就绪！")
```

**或者添加配置选项：**
在 `__init__` 方法中添加参数：
```python
def __init__(self, session_id: str | None = None, show_welcome: bool = True):
    super().__init__("reload")
    self.session_id = session_id
    self.show_welcome = show_welcome
    
    # 在创建 head 时检查
    if self.show_welcome:
        head = Text.from_markup("KXNS CLI 已就绪！")
    else:
        head = Text.from_markup("KXNS CLI is your next CLI agent.")
```

### 修改帮助信息

帮助信息在 `src/kimi_cli/ui/shell/slash.py` 文件中定义。

**修改英文帮助为中文：**
```python
# 修改前
Text.from_markup("[grey50]Help! I need somebody. Help! Not just anybody.[/grey50]")
Text.from_markup("[grey50]Help! You know I need someone. Help![/grey50]")

# 修改后
Text.from_markup("[grey50]需要帮助吗？我可以帮你！[/grey50]")
Text.from_markup("[grey50]KXNS CLI 随时准备为您提供帮助！[/grey50]")
Text.from_markup("[grey50]发送消息给我，我会尽力协助您完成任务！[/grey50]")
```

### 添加新功能

KXNS CLI 支持通过技能系统扩展功能。

**创建新技能：**

1. 在 `src/kimi_cli/skills/` 目录下创建新的技能目录
2. 创建技能配置文件（SKILL.md）
3. 实现技能逻辑

**技能示例：**
```python
# src/kimi_cli/skills/my-skill/SKILL.md
---
name: my-skill
description: 我的自定义技能
---

# src/kimi_cli/skills/my-skill/__init__.py
from kimi_cli.skills.skill import Skill

class MySkill(Skill):
    async def execute(self, args: str) -> None:
        """执行我的自定义技能"""
        console.print(f"执行自定义技能: {args}")
        return None
```

### 修改配置文件

KXNS CLI 使用 TOML 格式的配置文件。

**配置文件位置：**
- 默认：`~/.kxns/config.toml`
- 可通过 `--config-file` 参数指定

**配置文件结构：**
```toml
[default_model = "gpt-4o"]
default_thinking = false

[providers]
openai.type = "openai_legacy"
openai.base_url = "https://api.openai.com/v1"
openai.api_key = "sk-xxx"

[models]
gpt-4o.provider = "openai"
gpt-4o.model = "gpt-4o"
gpt-4o.max_context_size = 128000
gpt-4o.capabilities = ["thinking", "image_in"]
```

### 自定义命令

KXNS CLI 支持添加自定义斜杠命令。

**添加自定义命令：**

1. 在 `src/kimi_cli/cli/` 目录下创建新命令文件
2. 实现命令逻辑
3. 在 `src/kimi_cli/cli/__init__.py` 中注册命令

**命令示例：**
```python
# src/kimi_cli/cli/my_command.py
from kimi_cli.cli import cli

@cli.command("my-command")
def my_command():
    """我的自定义命令"""
    console.print("这是我的自定义命令")
```

### 修改主题和样式

KXNS CLI 使用 Rich 库进行美化输出。

**修改颜色方案：**
在 `src/kimi_cli/ui/shell/` 目录下修改样式配置

**修改欢迎横幅：**
在 `src/kimi_cli/ui/shell/__init__.py` 中修改欢迎横幅的样式和内容

### 常见定制场景

#### 1. 修改项目名称和品牌

如果你想将 KXNS CLI 重命名为自己的品牌名称：

1. 修改 `pyproject.toml` 中的 `name` 字段
2. 修改所有文档中的项目名称引用
3. 重新安装项目

#### 2. 修改欢迎信息

将欢迎信息改为更友好的中文提示，例如：
- "欢迎使用 KXNS CLI！"
- "KXNS CLI 已就绪，准备为您提供帮助！"

#### 3. 添加自定义功能

通过技能系统和命令系统，你可以：
- 添加行业特定的功能
- 集成第三方 API
- 自定义工作流程

#### 4. 修改配置文件路径

如果需要修改配置文件路径：
1. 修改 `src/kimi_cli/share.py` 中的默认路径
2. 修改 `src/kimi_cli/config.py` 中的配置文件名

### 注意事项

1. **保持兼容性**
   - 修改代码时，尽量保持与原项目的兼容性
   - 如果需要破坏性修改，请在文档中说明

2. **测试修改**
   - 每次修改后，都要测试功能是否正常
   - 建议使用虚拟环境进行测试

3. **版本管理**
   - 修改 `src/kimi_cli/constant.py` 中的版本号
   - 确保版本号的一致性

4. **提交更改**
   - 每次修改后，都要提交到 Git
   - 写清晰的提交信息

## 获取帮助

如果你在定制过程中遇到问题：

1. 查看源代码：`src/kimi_cli/` 目录
2. 参考文档：`docs/en/` 和 `docs/zh/` 目录
3. 查看测试文件：`tests/` 目录
4. 提交 Issue：在 GitHub 上提交问题

## 总结

KXNS CLI 是一个灵活且强大的 AI 命令行工具，支持多种定制方式。通过本指南，你可以根据自己的需求对项目进行定制，打造适合自己使用场景的 CLI 工具。

**记住：** 定制是一个持续的过程，建议从小处开始，逐步测试和完善你的修改。
