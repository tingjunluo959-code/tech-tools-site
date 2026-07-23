# 科技工具推荐自动站

本项目每天读取 Product Hunt 公开 Feed，默认用本地规则模板生成 400–600 字中文推荐文，不需要任何 AI 账号或 API Key。文章保存为 Markdown，并用 Jinja2 构建 `docs/` 静态网站、文章页和 RSS。GitHub Actions 每天 UTC 00:00 自动执行并提交产物，GitHub Pages 从 `main/docs` 发布。

> 自动化不保证收入。产品事实、中文文案、联盟资格、广告政策和当地披露要求仍需定期人工审核。

## 本地运行

要求 Python 3.10+：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

`.env` 默认配置为 `CONTENT_MODE=template`，因此可以直接运行，不需要登录 OpenAI。模板只使用 Feed 已提供的信息，不会虚构亲自体验、价格或产品效果。

以后如果希望提升文案变化度，可以将 `CONTENT_MODE` 改为 `openai`，再从 [OpenAI API Keys](https://platform.openai.com/api-keys) 创建密钥并填写 `OPENAI_API_KEY`。API 使用量通常需要单独计费，ChatGPT 订阅不等同于 API 额度。默认模型按原需求设为 `gpt-3.5-turbo`，但其可用性取决于账户和 OpenAI 当时的模型供应。

首次建议保留 `MAX_PRODUCTS_PER_RUN=1` 控制费用：

```powershell
python main.py
python -m http.server 8000 --directory docs
```

打开 `http://localhost:8000/`。离线测试：

```powershell
python -m unittest discover -s tests -v
```

## 联盟链接与广告

生成稿包含 `[了解更多]({{affiliate_link}})`。可以：

- 在 `.env` 或 GitHub Secret 设置统一的 `AFFILIATE_LINK`；
- 在 `content/posts/` 搜索替换 `{{affiliate_link}}`，为每篇文章填写不同链接。

未配置时会安全回退到 Product Hunt 原始链接。只有获得相应联盟计划授权后才使用联盟链接。`templates/index.html` 和 `templates/post.html` 已预留注释状态的 AdSense 脚本，审核通过后替换发布商 ID 并取消注释。

## GitHub 与 Pages

1. 在 GitHub 注册或登录账号，新建空仓库。
2. 在本目录初始化并推送：

```powershell
git init
git add .
git commit -m "feat: initialize tech tools site"
git branch -M main
git remote add origin https://github.com/你的用户名/你的仓库.git
git push -u origin main
```

3. 仓库 **Settings → Secrets and variables → Actions**：
   - 默认模板模式不需要 OpenAI Secret
   - 可选 Secret：`OPENAI_API_KEY`（仅 `CONTENT_MODE=openai` 时需要）
   - 可选 Secret：`AFFILIATE_LINK`
   - Variable：`SITE_URL`，例如 `https://用户名.github.io/仓库名`
   - 可选 Variable：`CONTENT_MODE`、`OPENAI_MODEL`、`SITE_NAME`、`SITE_DESCRIPTION`、`MAX_PRODUCTS_PER_RUN`
4. **Settings → Pages** 选择 **Deploy from a branch**，分支 `main`，目录 `/docs`。
5. 在 Actions 页面手动运行一次工作流；以后每天北京时间 08:00 自动运行。

若工作流不能推送，在 **Settings → Actions → General → Workflow permissions** 允许 Read and write permissions，并检查分支保护规则。

## 自定义域名

1. Actions Variable 设置 `CUSTOM_DOMAIN=tools.example.com`，同时设置 `SITE_URL=https://tools.example.com`。
2. 重新运行工作流，程序会生成 `docs/CNAME`。
3. DNS 添加 CNAME：`tools` 指向 `你的用户名.github.io`。
4. Pages 设置中填写自定义域名，证书生效后启用 **Enforce HTTPS**。

根域名需按 GitHub Pages 官方说明配置 A/AAAA 或 ALIAS/ANAME 记录。

## 已知上游变化

需求给出的 `https://www.producthunt.com/feed.rss` 当前实测为 404，程序会自动回退到可用的 `https://www.producthunt.com/feed` Atom Feed。若 Product Hunt 再次调整地址，可通过 `PRODUCT_HUNT_FEED_URL` 修改。
