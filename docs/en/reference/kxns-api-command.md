# kxns api Command

Manage AI API providers and models configuration.

## Overview

The `kxns api` command provides a unified interface for managing all AI API configurations. You can add, list, remove, and test API providers and models without manually editing configuration files.

## Commands

### `kxns api add`

Add a new API configuration (provider + model).

**Usage:**
```bash
kxns api add -p <provider> -m <model> [options]
```

**Required Arguments:**
- `-p, --provider <name>` - Provider name (e.g., openai, anthropic, gemini)
- `-m, --model <name>` - Model name

**Optional Arguments:**
- `-u, --base-url <url>` - API base URL
- `-k, --api-key <key>` - API key
- `-C, --max-context <tokens>` - Maximum context size (tokens)
- `-c, --capabilities <caps>` - Model capabilities (comma-separated: thinking, always_thinking, image_in, video_in)
- `-H, --headers <pairs>` - Custom headers in KEY:VALUE format (can be specified multiple times)
- `-d, --default` - Set as default model

**Examples:**
```bash
# Add OpenAI GPT-4o with custom settings
kxns api add -p openai -m gpt-4o -u https://api.openai.com/v1 -k sk-xxx -C 128000 -c thinking,image_in -d

# Add Anthropic Claude
kxns api add -p anthropic -m claude-3-5-sonnet -u https://api.anthropic.com -k sk-ant-xxx -C 200000

# Add Gemini
kxns api add -p gemini -m gemini-2-pro -u https://generativelanguage.googleapis.com -k xxx
```

### `kxns api list`

List all configured API providers and models.

**Usage:**
```bash
kxns api list
```

**Output Example:**
```
Config file: C:\Users\admin\.kxns\config.toml

openai:
  Base URL: https://api.openai.com/v1
  API Key: ********
    - gpt-4o (default) [image_in, thinking]
  anthropic:
    Base URL: https://api.anthropic.com
    API Key: ********
      - claude-3-5-sonnet (default)

Default model: gpt-4o
```

### `kxns api remove`

Remove an API configuration.

**Usage:**
```bash
kxns api remove [options]
```

**Optional Arguments:**
- `-p, --provider <name>` - Provider name
- `-m, --model <name>` - Model name
- `-a, --all` - Remove all configurations

**Examples:**
```bash
# Remove a specific model
kxns api remove -p openai -m gpt-4o

# Remove a specific provider
kxns api remove -p anthropic

# Remove all configurations
kxns api remove --all
```

### `kxns api set-default`

Set the default model to use.

**Usage:**
```bash
kxns api set-default <model>
```

**Example:**
```bash
kxns api set-default gpt-4o
```

### `kxns api test`

Test API connection.

**Usage:**
```bash
kxns api test [options]
```

**Optional Arguments:**
- `-p, --provider <name>` - Provider name (uses default if not specified)
- `-m, --model <name>` - Model name (uses default if not specified)

**Example:**
```bash
kxns api test -p openai -m gpt-4o
```

**Output:**
```
Testing API connection to: openai/gpt-4o
  ✓ API key is valid
  ✓ Model: gpt-4o
  ✓ Capabilities: [thinking, image_in]
```

## Configuration File

All configurations are stored in the KXNS CLI config file (`~/.kxns/config.toml`).

**Format:**
```toml
default_model = "gpt-4o"

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

## Model Capabilities

The following capabilities can be specified:

- `thinking` - Model supports thinking mode
- `always_thinking` - Model always uses thinking mode
- `image_in` - Model supports image input
- `video_in` - Model supports video input

## Notes

- API keys are stored securely and never displayed in logs
- Use `kxns api list` to view all configured providers and models
- Use `kxns api test` to verify API connections before using them
- The first model added to a provider is automatically set as the default model for that provider
- Use the `-d, --default` flag to explicitly set a model as default
