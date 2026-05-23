#!/usr/bin/env bash
# install.sh — Set up claude-skills on a new machine.
#
# Run once after cloning:
#   git clone git@github.com:bamorgans/claude-skills.git && cd claude-skills && ./install.sh
#
# Updates: cd claude-skills && git pull   (symlinks pick up changes automatically)

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

green()  { printf '\033[0;32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[0;33m%s\033[0m\n' "$*"; }
bold()   { printf '\033[1m%s\033[0m\n'    "$*"; }

bold "Installing claude-skills..."

# ── Scripts ───────────────────────────────────────────────────────────────────
mkdir -p ~/.claude/scripts/lib ~/.claude/scripts/platform

ln -sf "$REPO_DIR/scripts/rn-device-install"          ~/.claude/scripts/rn-device-install
ln -sf "$REPO_DIR/scripts/lib/rn-common.sh"           ~/.claude/scripts/lib/rn-common.sh
ln -sf "$REPO_DIR/scripts/platform/rn-ios.sh"         ~/.claude/scripts/platform/rn-ios.sh
ln -sf "$REPO_DIR/scripts/platform/rn-android.sh"     ~/.claude/scripts/platform/rn-android.sh
ln -sf "$REPO_DIR/scripts/platform/rn-web.sh"         ~/.claude/scripts/platform/rn-web.sh

chmod +x "$REPO_DIR/scripts/rn-device-install" \
         "$REPO_DIR/scripts/platform/rn-ios.sh" \
         "$REPO_DIR/scripts/platform/rn-android.sh" \
         "$REPO_DIR/scripts/platform/rn-web.sh"

green "  ✓ Scripts → ~/.claude/scripts/"

# ── Skills ────────────────────────────────────────────────────────────────────
for skill_dir in "$REPO_DIR/skills/"/*/; do
  skill_name=$(basename "$skill_dir")
  mkdir -p ~/.claude/skills/"$skill_name"
  ln -sf "$REPO_DIR/skills/$skill_name/SKILL.md" ~/.claude/skills/"$skill_name/SKILL.md"
done

green "  ✓ Skills   → ~/.claude/skills/"

# ── Verify ────────────────────────────────────────────────────────────────────
echo ""
bold "Installed skills:"
for skill_dir in "$REPO_DIR/skills/"/*/; do
  echo "  • $(basename "$skill_dir")"
done

echo ""
bold "Quick-start:"
echo "  ~/.claude/scripts/rn-device-install ios                # local Xcode build"
echo "  ~/.claude/scripts/rn-device-install ios --eas          # EAS cloud build"
echo "  ~/.claude/scripts/rn-device-install android            # local Gradle build"
echo "  ~/.claude/scripts/rn-device-install android --eas      # EAS cloud build"
echo "  ~/.claude/scripts/rn-device-install web                # Expo web export"
echo ""
yellow "  To update: git pull   (symlinks pick up changes automatically)"
