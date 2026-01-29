---
name: git-release
description: |
  Git 项目版本发布自动化工具。执行完整的发布流程：提交所有修改、更新版本号（若有）、
  生成 CHANGELOG、创建 git tag 并推送到远程仓库。基于语义化版本 (major/minor/patch)。
  支持有 package.json 的项目，也支持无 package.json 的项目（版本从最新 git tag 或 VERSION 等文件获取）。

  **核心理解（极其重要）**：
  当用户说"更新一下版本"、"更新版本"或任何类似表达时，**默认意味着执行完整的发布流程**：
  1. ✅ 提交所有当前的修改（包括未追踪的新文件）
  2. ✅ 若有版本文件则更新（package.json / VERSION 等）；若无则仅用 tag 表示版本
  3. ✅ 创建 git tag（vX.Y.Z）
  4. ✅ 推送所有内容到远程仓库（commit + tags）
  5. 📝 可选：生成/更新 CHANGELOG

  **不要**只改版本号而不提交、不打 tag、不推送！
  **必须**执行完整的发布流程，包括提交和推送！

  触发关键词（任何一个都触发完整流程）：
  - 通用发布词："更新一下版本"、"更新版本"、"升级版本"、"发布版本"、"版本发布"、"发新版"
  - 英文表达："bump version"、"release"、"new release"
  - Git操作："打tag"、"创建发布"、"创建tag"
  - 版本类型（隐含发布）："大版本更新"、"小版本更新"、"补丁版本"、"major release"、"minor release"、"patch release"
---

# Git Release Skill

自动化 Git 项目版本发布流程，完成从代码提交到版本发布的所有步骤。

## 核心理解

**当用户说"更新版本"时，不是仅更新版本号，而是执行完整的版本发布流程**：
1. ✅ 提交所有当前修改（`git add -A && git commit`）
2. ✅ 若有版本文件则更新（package.json、VERSION 等）；无则从最新 tag 推算新版本
3. ✅ 生成/更新 CHANGELOG（可选）
4. ✅ 创建版本 tag（`git tag vX.Y.Z`）
5. ✅ 推送到远程仓库（`git push && git push --tags`）

**不要**只改版本号而不提交、不打 tag、不推送！

### 无 package.json 的项目

若项目**没有** `package.json`：
- **当前版本**：从最新 git tag 解析（如 `v1.0.0` → `1.0.0`）；若无任何 tag，视为首次发布，可用 `0.1.0` 或询问用户。
- **版本号更新**：不修改 package.json。若存在 `VERSION`、`version.txt`、`pyproject.toml` 的 version、`Cargo.toml` 的 version 等，可选择性更新以保持与 tag 一致。
- **流程不变**：提交所有修改 → 创建 tag vX.Y.Z → 推送（commit + tags）。

## 重要：必须询问版本类型

在执行发布前，**必须使用 AskUserQuestion 工具询问用户版本升级类型**：

```
问题：本次发布是什么类型的版本升级？

选项：
- patch (补丁版本) - Bug 修复、小改动 (例: 1.0.0 → 1.0.1)
- minor (小版本) - 新功能、向后兼容 (例: 1.0.0 → 1.1.0)
- major (大版本) - 破坏性变更、重大更新 (例: 1.0.0 → 2.0.0)
```

除非用户在请求中已明确指定版本类型（如"大版本更新"、"patch release"），否则必须询问。

## 完整发布流程（按顺序执行）

### 1. 检查前置条件

```bash
# 确认工作区状态（查看是否有未提交的修改）
git status --porcelain

# 确认当前分支
git branch --show-current

# 获取当前版本号（按优先级尝试）
# 有 package.json 时：
grep '"version"' package.json 2>/dev/null || true
# 无 package.json 时，从最新 tag 获取（去掉 v 前缀）：
git describe --tags --abbrev=0 2>/dev/null || echo "无现有 tag"
# 或有 VERSION / version.txt 等：
cat VERSION 2>/dev/null || true

# 查看最近的 commit 历史（用于编写 commit 消息）
git log --oneline -5
```

### 2. 询问版本类型

**必须询问用户**，提供以下选项：

| 类型 | 描述 | 版本变化示例 |
|------|------|-------------|
| patch | 补丁版本：Bug 修复、文档更新、小改动 | 1.2.3 → 1.2.4 |
| minor | 小版本：新功能、向后兼容的改进 | 1.2.3 → 1.3.0 |
| major | 大版本：破坏性变更、API 重构 | 1.2.3 → 2.0.0 |

如果用户说"小更新"/"小版本" → minor
如果用户说"大更新"/"大版本" → major
如果用户说"修复"/"补丁" → patch

### 3. 计算并（可选）更新版本号

根据用户选择的版本类型，计算新版本号（语义化规则：major/minor/patch）。

- **有 package.json**：更新根目录及子目录（如 `server/package.json`）中的 `version` 字段，保持一致。
- **无 package.json**：不修改该文件。若项目有 `VERSION`、`version.txt`、`pyproject.toml` 的 `version`、`Cargo.toml` 的 `version` 等，可选择性更新为新版本，以便与 tag 一致；若无任何版本文件，仅用 git tag 表示版本即可。

### 4. 提交所有修改（包括版本更新）

**关键步骤**：提交所有当前工作区的修改，包括：
- 用户之前做的所有代码修改
- 刚才更新的版本号文件
- 任何新增的未追踪文件

```bash
# 提交所有修改（包括新文件和版本号更新）
git add -A
git commit -m "chore(release): vX.Y.Z

[简要描述本次版本包含的主要更新内容]

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

**commit 消息应该**：
- 格式：`chore(release): vX.Y.Z`
- 包含本次版本的主要更新内容说明
- 遵循项目的 commit 风格

### 5. 创建版本 tag

```bash
git tag -a vX.Y.Z -m "Release vX.Y.Z"
```

Tag 命名必须使用 `vX.Y.Z` 格式（如 v0.1.1）。

### 6. 推送到远程仓库

**默认执行推送**，将 commit 和 tag 都推送到远程：

```bash
# 推送当前分支
git push

# 推送新创建的 tag
git push --tags
```

如果推送失败（如网络问题、权限问题），报告给用户并提供解决建议。

### 7. 生成 CHANGELOG（可选）

如果项目有 CHANGELOG.md 文件，可以更新它。按 Angular 规范分组 commits：

```markdown
## [X.Y.Z] - YYYY-MM-DD

### Breaking Changes
- 破坏性变更描述

### Features
- feat(scope): description

### Bug Fixes
- fix(scope): description
```

如果生成了 CHANGELOG，需要额外提交并推送：
```bash
git add CHANGELOG.md
git commit -m "docs: update CHANGELOG for vX.Y.Z"
git push
```

## 版本类型关键词映射

用户可能使用的表达方式：

| 用户说 | 版本类型 |
|-------|---------|
| 大版本、大更新、重大更新、breaking | major |
| 小版本、小更新、新功能、feature | minor |
| 补丁、修复、bugfix、hotfix、小改动 | patch |

## 注意事项

- **完整流程**：版本发布是一个完整流程，包括提交所有修改、更新版本号（若有）、创建 tag、推送。不要只执行部分步骤！
- **提交优先**：始终先提交所有当前工作区的修改，再处理版本号与 tag
- **默认推送**：完成 commit 和 tag 后，默认推送到远程仓库（除非用户明确说不推送）
- **版本号同步**：有 package.json 时，多个 package.json 版本保持一致；无 package.json 时，若有 VERSION 等文件，可与 tag 保持一致
- **无 package.json**：当前版本从最新 git tag 解析；若无任何 tag，视为首次发布，使用 `0.1.0` 或 `1.0.0`（可询问用户）
- **破坏性变更**：必须升级 major 版本
- **Tag 格式**：统一使用 `vX.Y.Z` 格式（如 v0.1.1、v1.0.0）
- **首次发布**：建议从 `0.1.0` 或 `1.0.0` 开始
- **测试检查**：发布前建议确保测试通过（如果有自动化测试）

## 参考文档

- **Angular Commit 规范**: 见 `references/angular-commit.md`
- **语义化版本指南**: 见 `references/semver-guide.md`
- **CHANGELOG 模板**: 见 `assets/CHANGELOG.template.md`
