import { memo, useCallback, useEffect, useRef, useState, type ReactElement } from "react";
import { Settings, Eye, EyeOff, Save, Check, AlertCircle, Trash2, ImageIcon, Brain } from "lucide-react";
import { useGlobalConfig } from "@/hooks/useGlobalConfig";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Loader } from "@/components/ai-elements/loader";
import type { ConfigModel } from "@/lib/api/models";
import { ModelCapability } from "@/lib/api/models";
import { apiClient } from "@/lib/apiClient";

type SettingsPageProps = {
  onClose: () => void;
};

export const SettingsPage = memo(function SettingsPageComponent({
  onClose,
}: SettingsPageProps): ReactElement {
  const { config, isLoading, isUpdating, error, refresh, update } = useGlobalConfig();
  const [thinkingEnabled, setThinkingEnabled] = useState(false);
  const [imageInputEnabled, setImageInputEnabled] = useState(false);
  const [apiUrl, setApiUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [modelName, setModelName] = useState("");
  const [maxContextSize, setMaxContextSize] = useState(128000);
  const [reasoningKey, setReasoningKey] = useState("");
  const [showApiKey, setShowApiKey] = useState(false);
  const [configLoading, setConfigLoading] = useState(false);
  const [configError, setConfigError] = useState<string | null>(null);
  const [configSuccess, setConfigSuccess] = useState(false);
  const [modelInfoHint, setModelInfoHint] = useState<string | null>(null);
  const isMountedRef = useRef(true);
  const successTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const modelInfoTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      isMountedRef.current = false;
      if (successTimeoutRef.current) {
        clearTimeout(successTimeoutRef.current);
      }
      if (modelInfoTimeoutRef.current) {
        clearTimeout(modelInfoTimeoutRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (config) {
      const model = config.models.find((m) => m.name === config.defaultModel);
      const hasThinking = model?.capabilities?.has(ModelCapability.Thinking) ?? false;
      setThinkingEnabled(hasThinking);
      setImageInputEnabled(model?.capabilities?.has(ModelCapability.ImageIn) ?? false);
    }
  }, [config]);

  useEffect(() => {
    if (config) {
      const model = config.models.find((m) => m.name === config.defaultModel);
      if (model) {
        setApiUrl(model.baseUrl || "");
        setApiKey(model.apiKey || "");
        setReasoningKey(model.reasoningKey || "");
        setModelName(model.model || "");
        setMaxContextSize(model.maxContextSize || 128000);
      }
    }
  }, [config]);

  const loadProviderForModel = useCallback((modelKey: string) => {
    if (!config) return;
    const model = config.models.find((m) => m.name === modelKey);
    if (!model) return;
    setApiUrl(model.baseUrl || "");
    setApiKey(model.apiKey || "");
    setReasoningKey(model.reasoningKey || "");
    setModelName(model.model || "");
    setMaxContextSize(model.maxContextSize || 128000);
    setModelInfoHint(null);
  }, [config]);

  const handleModelNameChange = useCallback((name: string) => {
    setModelName(name);
    setModelInfoHint(null);

    if (modelInfoTimeoutRef.current) {
      clearTimeout(modelInfoTimeoutRef.current);
    }

    if (!name.trim()) return;

    modelInfoTimeoutRef.current = setTimeout(async () => {
      try {
        const resp = await fetch(`/api/config/model-info?model_name=${encodeURIComponent(name.trim())}`);
        if (!resp.ok) return;
        const data = await resp.json();
        if (!data.found || !isMountedRef.current) return;

        setMaxContextSize(data.max_context_size);
        setThinkingEnabled(data.supports_thinking);
        setImageInputEnabled(data.supports_image_input);
        setModelInfoHint(`已自动识别: ${data.display_name || data.name} (上下文 ${data.max_context_size.toLocaleString()} tokens${data.supports_thinking ? ", 支持思考" : ""}${data.supports_image_input ? ", 支持图片" : ""})`);
      } catch {
        // Silently ignore lookup failures
      }
    }, 600);
  }, []);

  const handleModelChange = async (modelKey: string) => {
    if (!config || modelKey === config.defaultModel) return;
    
    try {
      const resp = await update({ defaultModel: modelKey });
      if (resp.config) {
        const model = resp.config.models.find((m) => m.name === modelKey);
        if (model) {
          setApiUrl(model.baseUrl || "");
          setApiKey(model.apiKey || "");
          setReasoningKey(model.reasoningKey || "");
          setModelName(model.model || "");
          setMaxContextSize(model.maxContextSize || 128000);
        }
      }
    } catch (err) {
      console.error("Failed to update model:", err);
    }
  };

  const handleThinkingChange = async (enabled: boolean) => {
    if (!config) return;
    
    try {
      const response = await fetch("/api/config/api-settings", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          thinking: enabled,
          default_thinking: enabled,
          restart_running_sessions: false,
        }),
      });

      if (response.ok && isMountedRef.current) {
        setThinkingEnabled(enabled);
        refresh();
      }
    } catch (err) {
      console.error("Failed to update thinking:", err);
    }
  };

  const handleDeleteModel = async (modelName: string) => {
    if (!confirm(`确定要删除模型 "${modelName}" 吗？此操作不可撤销。`)) return;

    try {
      const response = await fetch(`/api/config/models/${encodeURIComponent(modelName)}`, {
        method: "DELETE",
      });

      if (response.ok) {
        refresh();
      } else {
        const errorData = await response.json().catch(() => ({}));
        alert(errorData.detail || "删除模型失败");
      }
    } catch (err) {
      alert(err instanceof Error ? err.message : "删除模型失败");
    }
  };

  const handleSaveConfig = async () => {
    setConfigLoading(true);
    setConfigError(null);
    setConfigSuccess(false);
    
    try {
      const response = await fetch("/api/config/api-settings", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          base_url: apiUrl || undefined,
          api_key: apiKey || undefined,
          model: modelName || undefined,
          max_context_size: maxContextSize || undefined,
          image_input: imageInputEnabled,
          thinking: thinkingEnabled,
          default_thinking: thinkingEnabled,
          reasoning_key: reasoningKey || undefined,
          restart_running_sessions: true,
        }),
      });

      if (!isMountedRef.current) return;

      if (response.ok) {
        setConfigSuccess(true);
        refresh();
        successTimeoutRef.current = setTimeout(() => {
          if (isMountedRef.current) {
            setConfigSuccess(false);
          }
        }, 3000);
      } else {
        const errorData = await response.json().catch(() => ({}));
        setConfigError(errorData.detail || "保存失败");
      }
    } catch (err) {
      if (!isMountedRef.current) return;
      setConfigError(err instanceof Error ? err.message : "保存失败");
    } finally {
      if (isMountedRef.current) {
        setConfigLoading(false);
      }
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex" role="dialog" aria-modal="true">
      <button
        type="button"
        className="absolute inset-0 bg-black/40"
        aria-label="Close settings"
        onClick={onClose}
      />
      <div className="relative m-auto h-[90vh] w-[90vw] max-w-2xl overflow-hidden rounded-lg border border-border bg-background shadow-2xl">
        <div className="flex h-full flex-col">
          <div className="flex items-center justify-between border-b px-4 py-3">
            <div className="flex items-center gap-2">
              <Settings className="size-5 text-muted-foreground" />
              <h2 className="text-lg font-semibold">设置</h2>
            </div>
            <button
              type="button"
              aria-label="Close"
              className="inline-flex h-8 w-8 cursor-pointer items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-secondary/50 hover:text-foreground"
              onClick={onClose}
            >
              ✕
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-4">
            {isLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader size={24} />
              </div>
            ) : error ? (
              <div className="flex flex-col items-center justify-center gap-4 py-8">
                <p className="text-sm text-muted-foreground">{error}</p>
                <Button variant="outline" size="sm" onClick={refresh}>
                  重试
                </Button>
              </div>
            ) : (
              <div className="space-y-6">
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Settings className="size-4" />
                      模型配置
                    </CardTitle>
                    <CardDescription>
                      选择默认模型和配置模型参数
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="space-y-2">
                      <Label htmlFor="model-select">默认模型</Label>
                      <Select 
                        value={config?.defaultModel || ""} 
                        onValueChange={handleModelChange}
                        disabled={isUpdating}
                      >
                        <SelectTrigger className="w-full">
                          <SelectValue placeholder="选择模型..." />
                        </SelectTrigger>
                        <SelectContent>
                          {config?.models.map((model) => (
                            <SelectItem key={model.name} value={model.name}>
                              <div className="flex items-center justify-between w-full">
                                <span>{model.name}</span>
                                <span className="text-xs text-muted-foreground ml-2">
                                  {model.provider}
                                </span>
                              </div>
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>

                    {config && config.models.length > 0 && (
                      <div className="space-y-2">
                        <Label>已配置模型</Label>
                        <div className="space-y-1">
                          {config.models.map((model) => (
                            <div
                              key={model.name}
                              className="flex items-center justify-between rounded-md border px-3 py-2"
                            >
                              <div className="flex items-center gap-2 min-w-0">
                                <span className="truncate text-sm font-medium">{model.name}</span>
                                <span className="text-xs text-muted-foreground shrink-0">
                                  ({model.providerType})
                                </span>
                              </div>
                              <button
                                type="button"
                                className="shrink-0 ml-2 inline-flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
                                onClick={() => handleDeleteModel(model.name)}
                                title="删除模型"
                              >
                                <Trash2 className="size-3.5" />
                              </button>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <ImageIcon className="size-4" />
                      多模态（图片输入）
                    </CardTitle>
                    <CardDescription>
                      启用图片输入能力，允许模型接收和分析图片
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="flex items-center justify-between">
                      <div className="space-y-0.5">
                        <Label htmlFor="image-input-mode">启用图片输入</Label>
                        <p className="text-sm text-muted-foreground">
                          {imageInputEnabled
                            ? "模型将支持接收图片输入（需要模型本身支持视觉能力）"
                            : "关闭后模型将无法接收图片输入"}
                        </p>
                      </div>
                      <Switch
                        id="image-input-mode"
                        checked={imageInputEnabled}
                        onCheckedChange={setImageInputEnabled}
                      />
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Brain className="size-4" />
                      Thinking 模式
                    </CardTitle>
                    <CardDescription>
                      声明模型是否支持深度思考，并启用 Thinking 模式
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="flex items-center justify-between">
                      <div className="space-y-0.5">
                        <Label htmlFor="thinking-mode">启用 Thinking 模式</Label>
                        <p className="text-sm text-muted-foreground">
                          {thinkingEnabled
                            ? "已启用深度思考模式（需模型本身支持推理能力）"
                            : "开启后将声明模型支持 Thinking 并启用深度思考"}
                        </p>
                      </div>
                      <Switch
                        id="thinking-mode"
                        checked={thinkingEnabled}
                        onCheckedChange={(checked) => {
                          setThinkingEnabled(checked);
                          handleThinkingChange(checked);
                        }}
                      />
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>API 配置</CardTitle>
                    <CardDescription>
                      配置 API 连接参数
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="space-y-2">
                      <Label htmlFor="api-url">API URL</Label>
                      <Input
                        id="api-url"
                        type="text"
                        placeholder="https://api.example.com/v1"
                        value={apiUrl}
                        onChange={(e) => setApiUrl(e.target.value)}
                        disabled={configLoading}
                      />
                    </div>
                    
                    <div className="space-y-2">
                      <Label htmlFor="api-key">API Key</Label>
                      <div className="relative">
                        <Input
                          id="api-key"
                          type={showApiKey ? "text" : "password"}
                          placeholder="sk-..."
                          value={apiKey}
                          onChange={(e) => setApiKey(e.target.value)}
                          disabled={configLoading}
                          className="pr-10"
                        />
                        <button
                          type="button"
                          className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                          onClick={() => setShowApiKey(!showApiKey)}
                          tabIndex={-1}
                        >
                          {showApiKey ? (
                            <EyeOff className="size-4" />
                          ) : (
                            <Eye className="size-4" />
                          )}
                        </button>
                      </div>
                    </div>
                    
                    <div className="space-y-2">
                      <Label htmlFor="model-name">模型名称</Label>
                      <Input
                        id="model-name"
                        type="text"
                        placeholder="gpt-4o, claude-3-5-sonnet, deepseek-r1..."
                        value={modelName}
                        onChange={(e) => handleModelNameChange(e.target.value)}
                        disabled={configLoading}
                      />
                      {modelInfoHint && (
                        <p className="text-xs text-green-600 dark:text-green-400">
                          {modelInfoHint}
                        </p>
                      )}
                      <p className="text-xs text-muted-foreground">
                        输入已知模型名称可自动识别上下文长度和能力。常见模型: GPT-4o, Claude 3.5 Sonnet, DeepSeek R1, Gemini 2.5 Pro, Qwen3 等
                      </p>
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="max-context-size">最大上下文长度 (tokens)</Label>
                      <Input
                        id="max-context-size"
                        type="number"
                        min={1000}
                        step={1000}
                        placeholder="128000"
                        value={maxContextSize}
                        onChange={(e) => setMaxContextSize(parseInt(e.target.value, 10) || 128000)}
                        disabled={configLoading}
                      />
                      <p className="text-xs text-muted-foreground">
                        模型支持的最大上下文 token 数。影响上下文压缩触发时机。输入模型名称后可自动识别此值。
                      </p>
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="reasoning-key">推理内容字段名 (Reasoning Key)</Label>
                      <Input
                        id="reasoning-key"
                        type="text"
                        placeholder="reasoning_content (DeepSeek) / 留空自动检测"
                        value={reasoningKey}
                        onChange={(e) => setReasoningKey(e.target.value)}
                        disabled={configLoading}
                      />
                      <p className="text-xs text-muted-foreground">
                        API 响应中思考/推理内容的字段名。DeepSeek 系列模型通常为 "reasoning_content"，留空则自动检测 DeepSeek 模型。
                      </p>
                    </div>
                    
                    {configError && (
                      <div className="flex items-center gap-2 text-sm text-destructive">
                        <AlertCircle className="size-4" />
                        <span>{configError}</span>
                      </div>
                    )}
                    
                    {configSuccess && (
                      <div className="flex items-center gap-2 text-sm text-green-600">
                        <Check className="size-4" />
                        <span>配置已保存</span>
                      </div>
                    )}
                    
                    <Button
                      onClick={handleSaveConfig}
                      disabled={configLoading}
                      className="w-full"
                    >
                      {configLoading ? (
                        <Loader size={16} />
                      ) : (
                        <>
                          <Save className="size-4 mr-2" />
                          保存配置
                        </>
                      )}
                    </Button>
                    
                    <div className="text-xs text-muted-foreground">
                      <p>配置文件路径: 使用 kxns api 命令查看</p>
                      <p className="mt-1">已配置 {config?.models.length ?? 0} 个模型</p>
                    </div>
                  </CardContent>
                </Card>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
});
