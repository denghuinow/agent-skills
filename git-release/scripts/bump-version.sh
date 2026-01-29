#!/bin/bash
# bump-version.sh - 语义化版本号升级脚本
# 用法: bash bump-version.sh [major|minor|patch] [--dry-run]

set -e

VERSION_TYPE=${1:-patch}
DRY_RUN=false

if [[ "$2" == "--dry-run" ]]; then
    DRY_RUN=true
fi

# 检查 package.json 是否存在
if [[ ! -f "package.json" ]]; then
    echo "Error: package.json not found in current directory"
    exit 1
fi

# 获取当前版本
CURRENT_VERSION=$(grep -o '"version": *"[^"]*"' package.json | grep -o '[0-9]*\.[0-9]*\.[0-9]*')

if [[ -z "$CURRENT_VERSION" ]]; then
    echo "Error: Could not parse version from package.json"
    exit 1
fi

# 解析版本号
IFS='.' read -r MAJOR MINOR PATCH <<< "$CURRENT_VERSION"

# 计算新版本
case "$VERSION_TYPE" in
    major)
        MAJOR=$((MAJOR + 1))
        MINOR=0
        PATCH=0
        ;;
    minor)
        MINOR=$((MINOR + 1))
        PATCH=0
        ;;
    patch)
        PATCH=$((PATCH + 1))
        ;;
    *)
        echo "Error: Invalid version type. Use: major, minor, or patch"
        exit 1
        ;;
esac

NEW_VERSION="${MAJOR}.${MINOR}.${PATCH}"

echo "Current version: $CURRENT_VERSION"
echo "New version:     $NEW_VERSION"
echo "Version type:    $VERSION_TYPE"

if [[ "$DRY_RUN" == true ]]; then
    echo ""
    echo "[Dry run] No changes made."
    exit 0
fi

# 更新 package.json
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    sed -i '' "s/\"version\": \"$CURRENT_VERSION\"/\"version\": \"$NEW_VERSION\"/" package.json
else
    # Linux/Windows Git Bash
    sed -i "s/\"version\": \"$CURRENT_VERSION\"/\"version\": \"$NEW_VERSION\"/" package.json
fi

echo ""
echo "Version updated to $NEW_VERSION in package.json"
echo ""
echo "Next steps:"
echo "  1. Update CHANGELOG.md"
echo "  2. git add package.json CHANGELOG.md"
echo "  3. git commit -m \"chore(release): v$NEW_VERSION\""
echo "  4. git tag -a v$NEW_VERSION -m \"Release v$NEW_VERSION\""
echo "  5. git push origin <branch> && git push origin v$NEW_VERSION"
