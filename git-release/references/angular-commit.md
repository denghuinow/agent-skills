# Angular Commit 规范

## 格式

```
<type>(<scope>): <subject>

<body>

<footer>
```

## Type 类型

| Type | 描述 | 版本影响 |
|------|------|---------|
| `feat` | 新功能 | minor |
| `fix` | Bug 修复 | patch |
| `docs` | 文档变更 | - |
| `style` | 代码格式（不影响逻辑） | - |
| `refactor` | 重构（非 feat/fix） | patch |
| `perf` | 性能优化 | patch |
| `test` | 测试相关 | - |
| `build` | 构建系统或依赖 | patch |
| `ci` | CI 配置 | - |
| `chore` | 其他杂项 | - |
| `revert` | 回滚提交 | patch |

## Scope 范围

可选，表示影响范围：
- `feat(auth)`: 认证模块
- `fix(api)`: API 相关
- `docs(readme)`: README 文档

## Subject 主题

- 使用祈使句（动词原形开头）
- 首字母小写
- 不加句号
- 50 字符以内

## Body 正文

- 可选
- 解释 what 和 why（而非 how）
- 每行 72 字符以内

## Footer 页脚

- `BREAKING CHANGE: <description>` 破坏性变更
- `Closes #123` 关闭 issue
- `Refs #456` 引用 issue

## 破坏性变更

两种标记方式：

```bash
# 方式1: 在 type 后加 !
feat!: remove deprecated API

# 方式2: 在 footer 中说明
feat: redesign user API

BREAKING CHANGE: user API response format changed
```

## 示例

```bash
# 新功能
feat(auth): add OAuth2 login support

# Bug 修复
fix(api): handle null response from server

# 破坏性变更
feat(api)!: change response format

The API now returns { data, meta } instead of raw data.

BREAKING CHANGE: All API responses now wrapped in { data, meta } object.

# 文档
docs(readme): update installation instructions

# 性能优化
perf(query): add database index for faster lookups

# 关联 issue
fix(ui): button alignment on mobile

Closes #42
```

## CHANGELOG 分组

生成 CHANGELOG 时按以下顺序分组：

1. **Breaking Changes** - 所有破坏性变更
2. **Features** - feat 类型
3. **Bug Fixes** - fix 类型
4. **Performance** - perf 类型
5. **Other Changes** - 其他类型（可选）
