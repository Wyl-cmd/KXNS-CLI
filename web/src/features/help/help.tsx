import { memo, type ReactElement } from "react";
import {
  Terminal,
  MessageSquare,
  FolderOpen,
  Settings,
  Keyboard,
  HelpCircle,
  ExternalLink,
  FileText,
  Lightbulb,
  Brain,
  Zap,
  Rocket,
  Upload,
  History,
  Eye,
} from "lucide-react";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Kbd, KbdGroup } from "@/components/ui/kbd";
import { Separator } from "@/components/ui/separator";

type CliCommand = {
  command: string;
  description: string;
};

type WebFeature = {
  icon: ReactElement;
  title: string;
  description: string;
};

type Shortcut = {
  keys: string[];
  description: string;
};

type Faq = {
  question: string;
  answer: string;
};

const cliCommands: CliCommand[] = [
  {
    command: "kxns",
    description: "启动 AI 对话，进入交互式命令行界面，开始与 AI 助手进行对话",
  },
  {
    command: "kxns api <url> <key> <model>",
    description: "配置 API 连接，指定 API 地址、密钥和模型名称。例如：kxns api https://api.example.com sk-xxx gpt-4",
  },
  {
    command: "kxns web",
    description: "启动 Web UI，在浏览器中使用图形界面，支持更丰富的交互功能",
  },
  {
    command: "kxns config",
    description: "查看当前配置信息，包括 API 地址、当前模型、工作目录等设置",
  },
  {
    command: "kxns model",
    description: "查看可用模型列表，显示所有支持的 AI 模型及其详细信息",
  },
  {
    command: "kxns clear",
    description: "清除当前会话的对话历史，开始全新的对话上下文",
  },
  {
    command: "kxns export [format]",
    description: "导出对话记录，支持 JSON、Markdown 等格式。默认导出为 JSON 格式",
  },
  {
    command: "kxns --help",
    description: "显示帮助信息，查看所有可用命令及其用法说明",
  },
  {
    command: "kxns --version",
    description: "显示当前安装的 Kxns Hunter 版本号",
  },
];

const webFeatures: WebFeature[] = [
  {
    icon: <MessageSquare className="size-5" />,
    title: "AI 对话功能",
    description: "与 AI 助手进行实时对话，支持代码生成、问题解答、文件操作等多种任务，智能理解上下文",
  },
  {
    icon: <FolderOpen className="size-5" />,
    title: "会话管理",
    description: "创建、切换、重命名、归档和删除会话，支持按工作目录分组查看，轻松管理多个项目",
  },
  {
    icon: <Settings className="size-5" />,
    title: "配置管理",
    description: "管理 API 配置、模型选择和工作目录设置，支持多环境配置和配置导入导出",
  },
  {
    icon: <Upload className="size-5" />,
    title: "文件操作功能",
    description: "上传文件、查看文件内容、编辑代码文件。支持图片、代码、文档等多种格式，AI 可直接分析文件内容",
  },
  {
    icon: <Eye className="size-5" />,
    title: "Plan Mode 计划模式",
    description: "只读分析和规划模式，AI 会先分析问题并制定详细计划，适合复杂任务的规划和设计阶段",
  },
  {
    icon: <Brain className="size-5" />,
    title: "Thinking Mode 思考模式",
    description: "深度推理模式，AI 会进行更深入的思考和推理，适合解决复杂问题和需要深度分析的任务",
  },
  {
    icon: <Zap className="size-5" />,
    title: "快捷命令",
    description: "使用斜杠命令快速操作，如 /clear 清除对话、/export 导出记录、/model 切换模型等",
  },
  {
    icon: <History className="size-5" />,
    title: "对话历史",
    description: "自动保存所有对话记录，支持搜索、筛选和导出，随时回顾历史对话内容",
  },
];

const shortcuts: Shortcut[] = [
  {
    keys: ["Shift", "Ctrl", "O"],
    description: "创建新会话",
  },
  {
    keys: ["Ctrl", "/"],
    description: "打开/关闭侧边栏",
  },
  {
    keys: ["Ctrl", "F"],
    description: "搜索消息",
  },
  {
    keys: ["Escape"],
    description: "取消当前操作",
  },
  {
    keys: ["Enter"],
    description: "发送消息",
  },
  {
    keys: ["Shift", "Enter"],
    description: "换行（不发送消息）",
  },
];

const faqs: Faq[] = [
  {
    question: "如何配置 API？",
    answer: "使用命令 kxns api <url> <key> <model> 配置 API。也可以在 Web UI 中通过设置页面进行配置，支持配置多个 API 端点并快速切换。",
  },
  {
    question: "会话数据存储在哪里？",
    answer: "会话数据存储在本地工作目录下的 .kxns 文件夹中，确保数据安全和隐私。您可以在设置中修改默认存储位置。",
  },
  {
    question: "如何切换不同的模型？",
    answer: "在 Web UI 的聊天界面顶部，点击模型选择器即可切换当前使用的 AI 模型。也可以使用 /model 命令快速切换。",
  },
  {
    question: "支持哪些类型的文件？",
    answer: "支持代码文件（.js、.py、.ts 等）、文本文件（.txt、.md 等）、图片（.png、.jpg 等）等多种格式。可以通过附件按钮上传文件，或在消息中引用工作目录中的文件。",
  },
  {
    question: "如何归档不需要的会话？",
    answer: "在会话列表中右键点击会话，选择\"归档\"选项。归档的会话可以在\"已归档\"区域找到并恢复。",
  },
  {
    question: "如何启用思考模式？",
    answer: "在聊天输入框上方，点击\"思考模式\"按钮（大脑图标）即可启用。启用后 AI 会进行更深入的推理分析，适合复杂问题。也可以使用 /thinking 命令快速切换。",
  },
  {
    question: "Plan Mode 是什么？",
    answer: "Plan Mode（计划模式）是一种只读分析模式。启用后，AI 会先分析问题并制定详细计划，不会直接修改文件。适合在执行复杂任务前进行规划和设计，确保方案可行后再实施。",
  },
  {
    question: "如何上传文件？",
    answer: "在聊天输入框左侧点击附件图标（回形针），选择要上传的文件。支持拖拽上传，也可以直接粘贴图片。上传后 AI 可以直接分析文件内容。",
  },
  {
    question: "如何查看对话历史？",
    answer: "点击左侧边栏的会话列表，可以查看所有历史会话。使用 Ctrl+F 快捷键可以在当前会话中搜索消息内容。也可以使用 kxns export 命令导出对话记录。",
  },
  {
    question: "快捷命令有哪些？",
    answer: "在输入框中输入 / 可以查看所有快捷命令。常用命令包括：/clear（清除对话）、/export（导出记录）、/model（切换模型）、/thinking（切换思考模式）、/plan（切换计划模式）等。",
  },
];

type QuickStartStep = {
  step: number;
  title: string;
  description: string;
};

const quickStartSteps: QuickStartStep[] = [
  {
    step: 1,
    title: "配置 API",
    description: "首次使用需要配置 API 连接。运行 kxns api <url> <key> <model> 命令，或在 Web UI 设置页面填写 API 信息。",
  },
  {
    step: 2,
    title: "创建会话",
    description: "使用 kxns 命令启动 CLI，或运行 kxns web 启动 Web UI。在 Web UI 中点击\"新建会话\"按钮创建新的对话。",
  },
  {
    step: 3,
    title: "开始对话",
    description: "在输入框中输入您的问题或需求，按 Enter 发送。AI 会根据您的输入提供回答或执行相应操作。",
  },
  {
    step: 4,
    title: "使用高级功能",
    description: "尝试上传文件让 AI 分析、启用思考模式进行深度推理、使用 Plan Mode 规划复杂任务，或使用斜杠命令快速操作。",
  },
];

export const HelpPage = memo(function HelpPageComponent(): ReactElement {
  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden">
      <div className="flex items-center justify-between border-b px-4 py-3">
        <div className="flex items-center gap-2">
          <HelpCircle className="size-5 text-muted-foreground" />
          <h1 className="text-lg font-semibold">帮助中心</h1>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        <div className="mx-auto max-w-4xl space-y-6">
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <Rocket className="size-5 text-primary" />
                <CardTitle>快速入门</CardTitle>
              </div>
              <CardDescription>
                几个简单步骤，快速开始使用 Kxns Hunter
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {quickStartSteps.map((step, index) => (
                  <div key={index} className="flex gap-4">
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground text-sm font-medium">
                      {step.step}
                    </div>
                    <div className="flex-1 space-y-1">
                      <h3 className="font-medium">{step.title}</h3>
                      <p className="text-sm text-muted-foreground">{step.description}</p>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <Terminal className="size-5 text-primary" />
                <CardTitle>CLI 命令说明</CardTitle>
              </div>
              <CardDescription>
                通过命令行界面快速启动和管理 Kxns Hunter
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {cliCommands.map((cmd, index) => (
                  <div key={index} className="rounded-lg border bg-muted/30 p-3">
                    <code className="text-sm font-mono text-primary">{cmd.command}</code>
                    <p className="mt-1 text-sm text-muted-foreground">{cmd.description}</p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <MessageSquare className="size-5 text-primary" />
                <CardTitle>Web UI 功能说明</CardTitle>
              </div>
              <CardDescription>
                了解 Web 界面的主要功能和特性
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 sm:grid-cols-2">
                {webFeatures.map((feature, index) => (
                  <div
                    key={index}
                    className="flex flex-col gap-2 rounded-lg border bg-muted/30 p-4"
                  >
                    <div className="flex items-center gap-2 text-primary">
                      {feature.icon}
                      <h3 className="font-medium">{feature.title}</h3>
                    </div>
                    <p className="text-sm text-muted-foreground">{feature.description}</p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <Keyboard className="size-5 text-primary" />
                <CardTitle>快捷键说明</CardTitle>
              </div>
              <CardDescription>
                使用快捷键提高操作效率
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {shortcuts.map((shortcut, index) => (
                  <div
                    key={index}
                    className="flex items-center justify-between rounded-lg border bg-muted/30 px-3 py-2"
                  >
                    <span className="text-sm">{shortcut.description}</span>
                    <KbdGroup>
                      {shortcut.keys.map((key, keyIndex) => (
                        <span key={keyIndex} className="flex items-center gap-1">
                          <Kbd>{key}</Kbd>
                          {keyIndex < shortcut.keys.length - 1 && (
                            <span className="text-muted-foreground">+</span>
                          )}
                        </span>
                      ))}
                    </KbdGroup>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <HelpCircle className="size-5 text-primary" />
                <CardTitle>常见问题解答</CardTitle>
              </div>
              <CardDescription>
                快速找到常见问题的解决方案
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {faqs.map((faq, index) => (
                  <div key={index}>
                    {index > 0 && <Separator className="my-4" />}
                    <div className="space-y-2">
                      <h3 className="font-medium text-foreground">{faq.question}</h3>
                      <p className="text-sm text-muted-foreground">{faq.answer}</p>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>更多资源</CardTitle>
              <CardDescription>
                获取更多帮助和支持
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-2">
                <Button variant="outline" size="sm" asChild>
                  <a
                    href="https://github.com/kxns-hunter/cli"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-2"
                  >
                    <ExternalLink className="size-4" />
                    官方网站
                  </a>
                </Button>
                <Button variant="outline" size="sm" asChild>
                  <a
                    href="https://github.com"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-2"
                  >
                    <ExternalLink className="size-4" />
                    GitHub
                  </a>
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
});
