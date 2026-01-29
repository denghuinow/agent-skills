# Git Release Skill

> Version: 0.1.0

Git 项目版本发布自动化工具。执行完整的发布流程：提交所有修改、更新版本号、生成 CHANGELOG、创建 git tag 并推送到远程仓库。

## 🎯 核心功能

当用户说"**更新版本**"或"**发布版本**"时，自动执行完整的版本发布流程：

1. ✅ **提交所有修改** - 包括所有当前工作区的修改和新文件
2. ✅ **更新版本号** - 根据语义化版本规则更新 package.json
3. ✅ **创建版本 tag** - 使用 `vX.Y.Z` 格式
4. ✅ **推送到远程** - 自动推送 commit 和 tag
5. ✅ **生成 CHANGELOG** - 可选，基于 Angular commit 规范

## 🚀 使用方式

### 触发关键词

中文：
- "发布版本"、"升级版本"、"更新版本"
- "版本发布"、"发新版"
- "大版本更新"、"小版本更新"、"补丁版本"

英文：
- "bump version"、"release"、"new release"
- "major release"、"minor release"、"patch release"
- "create tag"、"make a release"

### 版本类型

| 类型 | 描述 | 版本变化示例 |
|------|------|-------------|
| **patch** | 补丁版本：Bug 修复、文档更新、小改动 | 1.2.3 → 1.2.4 |
| **minor** | 小版本：新功能、向后兼容的改进 | 1.2.3 → 1.3.0 |
| **major** | 大版本：破坏性变更、API 重构 | 1.2.3 → 2.0.0 |

## 📋 完整流程

1. **检查前置条件** - 查看 git 状态、当前版本、分支信息
2. **询问版本类型** - 让用户选择 patch/minor/major
3. **更新版本号** - 修改 package.json（如有多个则同步更新）
4. **提交所有修改** - `git add -A && git commit`
5. **创建版本 tag** - `git tag -a vX.Y.Z`
6. **推送到远程** - `git push && git push --tags`
7. **生成 CHANGELOG** - （可选）按 Angular 规范分组

## 📁 包含文件

```
git-release/
├── SKILL.md                      # Skill 定义文件
├── README.md                     # 本文件
├── assets/
│   └── CHANGELOG.template.md    # CHANGELOG 模板
├── references/
│   ├── angular-commit.md        # Angular commit 规范
│   └── semver-guide.md          # 语义化版本指南
└── scripts/
    └── bump-version.sh          # 版本升级脚本
```

## 💡 使用示例

### 示例 1：补丁版本更新

```
用户：更新版本
Claude：本次发布是什么类型的版本升级？
用户：补丁版本
Claude：
  ✅ 已更新版本号：0.1.0 → 0.1.1
  ✅ 已提交所有修改
  ✅ 已创建 tag: v0.1.1
  ✅ 已推送到远程仓库
```

### 示例 2：小版本更新（带新功能）

```
用户：发布新版本，我加了几个新功能
Claude：本次发布是什么类型的版本升级？
用户：小版本
Claude：
  ✅ 已更新版本号：1.2.3 → 1.3.0
  ✅ 已提交所有修改（包括新功能）
  ✅ 已创建 tag: v1.3.0
  ✅ 已推送到远程仓库
```

## ⚙️ 配置要求

- 项目根目录需要有 `package.json` 文件
- Git 已配置远程仓库
- 有推送权限

## 🔍 注意事项

- **完整流程**：版本发布是一个完整流程，不要只执行部分步骤
- **提交优先**：始终先提交所有当前工作区的修改
- **默认推送**：完成后自动推送到远程（除非网络问题）
- **版本号同步**：如果有多个 package.json，确保版本号保持一致
- **Tag 格式**：统一使用 `vX.Y.Z` 格式

## 📚 参考文档

- [语义化版本规范](https://semver.org/lang/zh-CN/)
- [Angular Commit 规范](./references/angular-commit.md)
- [CHANGELOG 最佳实践](https://keepachangelog.com/zh-CN/)

## 📝 版本历史

### v0.1.0 (2025-12-19)
- 初始发布
- 支持完整的版本发布流程
- 包含 Angular commit 和 semver 参考文档
- 提供版本升级脚本

---

**License**: MIT
