# Agent Skills

个人维护的 Agent Skills 集合，用于把常用的自动化流程、运维操作和工程任务封装成可复用的 Skill。

每个 Skill 使用独立目录维护，核心入口为 `SKILL.md`，并可附带脚本、配置示例、依赖说明和 README。

## Skills

| Skill | 说明 |
|---|---|
| [`git-release`](./git-release/) | 自动化 Git 项目版本发布流程，包括提交修改、版本号处理、生成/更新 CHANGELOG、创建 tag 和推送远程仓库。 |
| [`oci-cloudflare-ip-rotate`](./oci-cloudflare-ip-rotate/) | 更换 OCI 临时公网 IP，并同步更新对应的 Cloudflare DNS A 记录。 |
| [`network-free-ip`](./network-free-ip/) | 根据目标网段自动选择 SSH Probe，通过远端 ARP 探测、DHCP 租约和静态保留信息查找候选空闲 IPv4 地址。 |

## 仓库结构

```text
agent-skills/
├── README.md
├── git-release/
│   └── SKILL.md
├── oci-cloudflare-ip-rotate/
│   ├── SKILL.md
│   ├── README.md
│   ├── requirements.txt
│   └── scripts/
└── network-free-ip/
    ├── SKILL.md
    ├── README.md
    ├── examples/
    └── scripts/
```

具体目录内容以各 Skill 实际实现为准。

## 使用方式

### 克隆整个仓库

```bash
git clone https://github.com/denghuinow/agent-skills.git
cd agent-skills
```

然后将需要的 Skill 目录复制或链接到 Agent 支持的 Skills 目录中。

例如：

```bash
cp -a network-free-ip /path/to/agent/skills/
```

不同 Agent 的 Skill 安装目录和加载方式可能不同，请以对应 Agent 的文档为准。

### 让 Agent 直接读取

支持本地文件或 GitHub Skill 导入的 Agent，可以直接指向对应目录中的 `SKILL.md`。

例如：

```text
network-free-ip/SKILL.md
```

## Skill 目录约定

推荐每个 Skill 使用如下结构：

```text
skill-name/
├── SKILL.md              # 必需：Agent 的核心指令、触发条件和工作流
├── README.md             # 可选：面向人的使用说明
├── requirements.txt      # 可选：Python 依赖
├── scripts/              # 可选：确定性执行脚本
├── examples/             # 可选：配置或调用示例
└── references/           # 可选：补充文档
```

### `SKILL.md`

至少包含 front matter：

```yaml
---
name: skill-name
description: Describe what the skill does and when the agent should use it.
---
```

正文建议明确：

- Skill 的用途和适用场景
- 触发条件
- 标准执行流程
- 前置依赖
- 安全约束
- 失败处理
- 示例调用

## 设计原则

本仓库中的 Skill 尽量遵循以下原则：

1. **可重复执行**：关键操作优先封装成确定性脚本，减少 Agent 临场拼接命令造成的差异。
2. **先验证后修改**：具有破坏性或外部副作用的操作，应先检查状态和前置条件。
3. **最小权限**：API Token、SSH、云平台凭据等仅授予任务所需权限。
4. **不提交密钥**：密码、Token、私钥、Cookie 和其他敏感凭据不得写入仓库。
5. **失败可诊断**：脚本和 Skill 应输出足够的信息区分配置错误、权限错误、网络问题和业务条件不满足。
6. **默认保守**：无法确认状态时返回失败或 `UNKNOWN`，不要把“不确定”当作“成功”。

## 新增 Skill

新增一个 Skill 时，建议：

```bash
mkdir -p my-skill/scripts my-skill/examples
```

然后至少创建：

```text
my-skill/SKILL.md
```

如果 Skill 包含较复杂的外部操作，建议把实际执行逻辑放入 `scripts/`，让 `SKILL.md` 负责告诉 Agent **什么时候调用、调用前检查什么、怎样解释结果**。

## License

除非某个 Skill 目录中另有说明，本仓库当前未单独声明开源许可证。需要复制、分发或集成到其他项目时，请先确认仓库后续的 License 设置。
