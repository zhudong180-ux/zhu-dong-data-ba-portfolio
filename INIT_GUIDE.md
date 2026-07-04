# 🚀 Git 初始化与上传指南

> 本文档说明如何把这个 monorepo 上传到 GitHub 的完整步骤

---

## 1. 在 GitHub 创建仓库

1. 登录 https://github.com/
2. 点击右上角 + → New repository
3. **Repository name**: `zhu-dong-data-ba-portfolio`(或你喜欢的名字,如 `data-ba-portfolio`)
4. **Description**: 算法工程师作品集 - 数据宝 ChinaDataPay 工作成果 (2024.10-2026.01)
5. 选择 **Public**(推荐,便于作品集展示)或 **Private**
6. ⚠️ **不要**勾选 "Initialize this repository with a README" / "Add .gitignore" / "Choose a license"(本仓库已包含)
7. 点击 **Create repository**

---

## 2. 本地初始化

打开 `Git Bash` 或在 `E:\数据宝工作经验\github-portfolio\` 下执行:

```bash
cd "/e/数据宝工作经验/github-portfolio/"

# 1. 初始化本地仓库
git init

# 2. 配置个人信息(全局,只需一次)
git config --global user.name "Zhu Dong"
git config --global user.email "2667286040@qq.com"

# 3. 添加所有文件(注意 .gitignore 已保护敏感文件)
git add .

# 4. 查看待提交的文件清单(确认无敏感信息)
git status

# 5. 首次提交
git commit -m "Initial commit: 数据宝工作期间完整作品集

包含 5 大项目:
- 01-vehicle-data-cleaning: 车型数据清洗工具集(7 版本演进)
- 02-vin-decrypt-etl: VIN/高速运力加密数据 ETL 流水线
- 03-face-recognition-production: 人脸识别 + 活体检测生产服务
- 04-freight-scheduling-solutions: 货运调度与风控 5 份完整方案
- 05-aigc-principles: 15 大主题算法原理详解

所有代码已脱敏处理,移除生产密钥与内部路径。
"
```

---

## 3. 关联远程仓库并推送

把下面的 `YOUR_USERNAME` 改成你的 GitHub 用户名,把 `zhu-dong-data-ba-portfolio` 改成实际仓库名:

```bash
# 1. 添加远程仓库地址
git remote add origin https://github.com/YOUR_USERNAME/zhu-dong-data-ba-portfolio.git

# 2. 验证远程仓库
git remote -v

# 3. 推送主分支
git branch -M main
git push -u origin main
```

---

## 4. 推送时常见问题

### 4.1 大文件超过 100MB

如果推送时报错 "file exceeds 100MB",需要用 Git LFS:

```bash
# 安装 Git LFS
git lfs install

# 跟踪大文件
git lfs track "*.xlsx"
git lfs track "*.pt"
git lfs track "*.zip"
git lfs track "*.log"

# 把 .gitattributes 加入提交
git add .gitattributes
```

⚠️ **建议**: 本仓库已通过 `.gitignore` 排除大文件,通常不需要 LFS。
若仍需上传示例数据(脱敏后),单独提交并写明"示例数据,可下载"。

### 4.2 敏感信息扫描

上传前务必扫描一遍:

```bash
# 检查硬编码的密钥/路径
grep -rn "h8mlhE538fmao8Np\|18621826\|2667286040" .

# 检查本地绝对路径
grep -rn "C:\\\\Users\\\\\|/root/\|autodl-tmp\|Desktop\|xwechat" .

# 检查真实 VIN 码
grep -rn "LRDS6PGC5RT069137" .
```

如果发现,立即用 `Edit` 工具替换或删除。

### 4.3 推送时认证失败

**方案 A: GitHub 个人访问令牌(PAT)**

1. GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Generate new token: 勾选 `repo` 权限
3. 复制 token,推送时用它当密码

**方案 B: SSH Key**

```bash
# 1. 生成 SSH key
ssh-keygen -t ed25519 -C "2667286040@qq.com"

# 2. 复制公钥
cat ~/.ssh/id_ed25519.pub

# 3. GitHub Settings → SSH and GPG keys → New SSH key

# 4. 修改远程仓库 URL
git remote set-url origin git@github.com:YOUR_USERNAME/zhu-dong-data-ba-portfolio.git
```

---

## 5. 推荐仓库设置

在 GitHub 仓库页面 → Settings:

### 5.1 About 部分(必填)

- **Description**: `算法工程师作品集 - 数据宝 ChinaDataPay (2024.10-2026.01) | 13+ 项目覆盖 AIGC/CV/调度/风控`
- **Website**: 留空或你的个人网站
- **Topics**:`aigc`, `stable-diffusion`, `face-recognition`, `vrm`, `data-cleaning`, `china-data-pay`, `algorithm`, `python`, `pytorch`, `logistics`

### 5.2 Features(推荐)

- ✅ Wikis(可选,放技术笔记)
- ✅ Issues(可选,接受反馈)
- ❌ Projects(可以不开)
- ✅ Discussions(可选)

### 5.3 Pages(可选)

如果想做作品集展示页:Settings → Pages → 选择 `main` 分支 `/docs` 或根目录 → Save

---

## 6. 进一步优化

### 6.1 添加 GitHub Profile README

在 GitHub 上创建一个与你用户名同名的新仓库,如 `YOUR_USERNAME/YOUR_USERNAME`,在 `README.md` 中写个人简介:

```markdown
# Hi there 👋 I'm Zhu Dong (朱东)

## 算法工程师 | 智能体 / 生成式 AI 应用工程化

🎯 关注:把模型能力做成能上线交付的产品能力  
📦 当前最佳作品: [zhu-dong-data-ba-portfolio](https://github.com/YOUR_USERNAME/zhu-dong-data-ba-portfolio)

🔭 技术栈:Python | PyTorch | Stable Diffusion | RL/VRP | Tweedie GLM  
🌱 在学:Agent 工程化 / MLOps / Lakehouse
```

### 6.2 添加 LICENSE 标识(已经做了)

- 仓库根目录的 `LICENSE` 文件已存在
- GitHub 会自动识别并显示 MIT License 标签

### 6.3 启用 Releases

对于重大版本(如 V1 完整作品集)可打 tag:

```bash
git tag -a v1.0 -m "Initial portfolio release (data-ba period)"
git push origin v1.0
```

### 6.4 维护更新

发现新内容时:

```bash
git add .
git commit -m "Update <什么改了>"
git push
```

---

## 7. ⚠️ 上传前必检清单

- [ ] ✅ 主 `README.md` 完整且有徽章
- [ ] ✅ `LICENSE` 文件存在
- [ ] ✅ `.gitignore` 已包含大文件、敏感信息
- [ ] ✅ 所有代码已脱敏(AES 密钥、内部路径、手机号、QQ 邮箱 替换或删除)
- [ ] ✅ 大型 zip/Excel/log 已排除
- [ ] ✅ 模型权重文件已排除(用 LFS 单独管理)
- [ ] ✅ 5 个子项目都有 README.md
- [ ] ✅ docs/ 中有面试 Q&A
- [ ] ✅ 仓库描述、Topics 已设置
- [ ] ✅ 没有 `localhost:6379`、`password=`、真实手机号

---

## 8. 后续维护建议

### 短期(1-2 周)
- [ ] 把原简历中的 `1简历算法与技术原理详解_朱东.pdf` 完整转写为 Markdown(目前已转写大部分,少数章节还有)
- [ ] 给每个文件加代码注释
- [ ] 补充单元测试

### 中期(1-2 月)
- [ ] 增加 GH Actions CI(Ruff + pytest)
- [ ] 用 `pyproject.toml` 统一依赖管理
- [ ] 建立 release 流程

### 长期(3-6 月)
- [ ] 把代码上传到 PyPI(主要包)
- [ ] 给项目加上 Docker 部署演示
- [ ] 在博客写系列文章

---

## 📌 联系作者

如有问题或建议,欢迎通过 GitHub Issues 反馈。

**作者**: 朱东 (Zhu Dong)
**邮箱**: 2667286040@qq.com
**原公司**: 贵州数据宝网络科技有限公司上海分公司(2024.10 - 2026.01)
**当前公司**: 上海畅停信息科技有限公司(2026.03 - 至今)
