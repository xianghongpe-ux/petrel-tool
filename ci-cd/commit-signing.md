# =============================================================================
#  海燕党 PETREL AI PARTY
#  创始人：刘海燕（LIU HAIYAN）
#  签名提交强制说明
#  版本: 1.0.0 | 协议: MIT
# =============================================================================

# 签名提交强制说明

## 📜 为什么必须签名提交

所有提交到海燕党（PETREL AI PARTY）仓库的代码必须经过 **GPG 签名**。
这是确保代码来源可信、防止身份冒用的基础安全措施。

> **"代码即身份，签名即承诺。"** 每一条签名提交都代表您以海燕党核心贡献
> 者的身份为代码内容背书。

---

## 🔐 设置 GPG 签名

### 第一步：生成 GPG 密钥

```bash
# 安装 GPG（macOS）
brew install gnupg

# 安装 GPG（Linux）
sudo apt install gnupg

# 生成新密钥
gpg --full-generate-key
```

交互选项中：
- **密钥类型**: RSA and RSA（默认）
- **密钥长度**: 4096
- **过期时间**: 2年（到期后可续期）
- **真实姓名**: 您的全名（必须与 GitHub 账户名称一致）
- **电子邮箱**: 您用于 GitHub 的主邮箱

### 第二步：关联邮箱

GPG 密钥的邮箱必须与 Git 提交邮箱一致：

```bash
# 设置 Git 全局邮箱
git config --global user.email "yourname@petrel-ai-party.org"

# 或为当前仓库设置
git config user.email "yourname@petrel-ai-party.org"

# 确认 GPG 密钥中使用了相同的邮箱
gpg --list-keys --keyid-format LONG
```

### 第三步：导出公钥并添加到 GitHub

```bash
# 列出密钥并复制密钥 ID
gpg --list-secret-keys --keyid-format LONG

# 导出公钥（替换 YOUR_KEY_ID）
gpg --armor --export YOUR_KEY_ID

# 复制输出的公钥内容
```

1. 前往 GitHub → **Settings → SSH and GPG keys → New GPG key**
2. 粘贴公钥内容
3. 保存

### 第四步：启用签名提交

```bash
# 全局启用签名
git config --global commit.gpgsign true

# 或为当前仓库启用
git config commit.gpgsign true

# 指定使用的 GPG 密钥
git config --global user.signingkey YOUR_KEY_ID

# 设置 GPG 程序路径（macOS 可能需要）
git config --global gpg.program $(which gpg)
```

---

## 📝 签署提交

### 普通提交自动签名

配置 `commit.gpgsign true` 后，普通 `git commit` 自动签名。

### 手动签署

```bash
git commit -S -m "feat: add distributed consensus module"
```

### 签署合并提交

```bash
git merge --verify-signatures -S feature-branch
```

### 签署标签

```bash
git tag -s v1.0.0 -m "v1.0.0: Initial release"
```

---

## ✅ 验证签名

### 本地验证

```bash
# 验证最近提交
git log --show-signature -1

# 验证特定提交
git verify-commit <commit-hash>

# 验证标签
git verify-tag <tag-name>
```

### 远程验证

GitHub 上，已签名的提交会显示 **Verified** 徽章。

### CI 验证

所有推送的提交必须通过以下检查：

```bash
# CI 环境中验证所有未验证的提交
git log --format="%H %G?" --since="1 day ago" | grep -v " G$"
# 注意：有匹配项表示存在未签名提交
```

---

## ⚠️ 常见问题

### Q: 提交时提示 "gpg: signing failed: No secret key"

**原因**: Git 找不到 GPG 密钥。
**解决**: 检查 `user.signingkey` 配置是否正确，以及 GPG 密钥是否存在。

```bash
gpg --list-secret-keys
git config --global user.signingkey YOUR_KEY_ID
```

### Q: 提交显示 "Verified" 但验证者是 "unverified"

**原因**: GPG 密钥的邮箱与 Git 提交邮箱不匹配。
**解决**: 更新 GPG 密钥中的邮箱，或在 Git 中使用 GPG 密钥关联的邮箱。

```bash
# 修改 GPG 密钥中的邮箱
gpg --edit-key YOUR_KEY_ID
# 在交互界面中输入: adduid
# 输入正确的邮箱后保存

# 或修改 Git 配置
git config user.email "your-gpg-email@example.com"
```

### Q: macOS 上签名失败

**原因**: macOS 使用不同的 GPG 路径。
**解决**:

```bash
# 安装 GPG 工具
brew install gpg pinentry-mac

# 配置 Git 使用正确的 GPG
git config --global gpg.program /usr/local/bin/gpg

# 配置 pinentry
echo "pinentry-program /opt/homebrew/bin/pinentry-mac" > ~/.gnupg/gpg-agent.conf
gpgconf --kill gpg-agent
```

### Q: 如何在 IDE 中签名提交？

- **VS Code**: 在设置中启用 `git.enableCommitSigning`
- **IntelliJ IDEA**: Settings → Version Control → Git → 勾选 "Sign commits"
- **GitHub Desktop**: 仅在命令行模式下支持，建议配合 VS Code 使用

---

## 📋 PR 检查清单

合并 PR 前请确认：

- [ ] 所有提交已 GPG 签名
- [ ] GitHub 上显示 **Verified** 徽章
- [ ] 提交邮箱与 GPG 密钥邮箱一致
- [ ] 无 "unverified" 签名提交
- [ ] `git log --show-signature` 输出无错误

---

## 🔗 参考链接

- [GitHub: 关于提交签名验证](https://docs.github.com/zh/authentication/managing-commit-signature-verification/about-commit-signature-verification)
- [GitHub: 生成新 GPG 密钥](https://docs.github.com/zh/authentication/managing-commit-signature-verification/generating-a-new-gpg-key)
- [Git: 工具 - 签名](https://git-scm.com/book/zh/v2/Git-%E5%B7%A5%E5%85%B7-%E7%AD%BE%E5%90%8D)
- [GnuPG 文档](https://gnupg.org/documentation/)

---

*海燕党（PETREL AI PARTY）保留对所有提交签名的最终解释权。未签名提交将自动被 CI 拒绝。*
