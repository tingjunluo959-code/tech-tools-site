# Tech Tools Worth Watching

一个自动化的 Product Hunt 科技工具推荐站：每天读取公开 Feed，生成英文主文章和中文镜像，使用 Jinja2 构建 GitHub Pages 静态网站。默认使用本地模板，不需要 OpenAI 登录、注册或 API Key。

根路径 `/` 是英文站，中文版本位于 `/zh/`。每篇文章都有独立页面和对应 RSS。文章只引用 Feed 已提供的信息，不声称亲自体验，也不保证收入；产品事实、联盟资格、广告政策和当地披露要求仍需人工审核。

## 本地运行

要求 Python 3.10+：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python main.py
python -m http.server 8000 --directory docs
```

打开 http://localhost:8000/ 查看英文站，http://localhost:8000/zh/ 查看中文站。离线回归测试：

```powershell
python -m unittest discover -s tests -v
```

### 可选的 OpenAI 模式

默认 `CONTENT_MODE=template`，无需任何 AI 账号。若希望使用原需求中的 `gpt-3.5-turbo`：

1. 在 [OpenAI API Keys](https://platform.openai.com/api-keys) 登录并创建 API Key；
2. 将 `.env` 中的 `CONTENT_MODE` 改为 `openai`，填写 `OPENAI_API_KEY`；
3. API 使用量通常单独计费，ChatGPT 订阅不等于 API 额度。

生成失败会重试 2 次；中英文任一语言失败时不会写入 `processed_ids.txt`，下次仍会重试该产品。

## 联盟链接与广告

文章正文保留 `[了解更多]({{affiliate_link}})` 占位符。替换方式：

- 在 `.env` 或 GitHub Secret 设置统一的 `AFFILIATE_LINK`；
- 或在 `content/posts/` 中搜索替换 `{{affiliate_link}}`，为不同文章填写不同链接。

只有获得相应联盟计划授权后才使用真实联盟链接。`templates/index.html` 和 `templates/post.html` 中有注释状态的 Google AdSense 脚本，审核通过后替换 `ca-pub-xxxxxxxxxxxxxxxx` 并取消注释。

## 创建 GitHub 仓库并启用 Pages

1. 在 GitHub 新建一个空仓库，然后在本目录执行：

```powershell
git init
git add .
git commit -m "feat: initialize tech tools site"
git branch -M main
git remote add origin https://github.com/你的用户名/你的仓库.git
git push -u origin main
```

2. 仓库 **Settings → Pages**：选择 **Deploy from a branch**，分支 `main`，目录 `/docs`，保存。
3. **Settings → Actions → General → Workflow permissions** 选择允许读写（Read and write permissions），否则工作流无法提交新文章。
4. Actions 页面手动运行一次 `Generate and deploy tech recommendations`；以后每天 UTC 00:00（北京时间 08:00）自动运行。

## GitHub Secrets 与 Variables

默认模板模式不需要 OpenAI Secret。若启用 OpenAI，在 **Settings → Secrets and variables → Actions** 添加：

- Secret `OPENAI_API_KEY`：OpenAI API Key（不要写入代码或聊天）；
- 可选 Secret `AFFILIATE_LINK`：统一联盟链接。

可选 Variables：`CONTENT_MODE`、`OPENAI_MODEL`、`SITE_URL`、`SITE_NAME`、`SITE_DESCRIPTION`、`MAX_PRODUCTS_PER_RUN`、`CUSTOM_DOMAIN`。`SITE_URL` 应填写例如 `https://用户名.github.io/仓库名`。

## 绑定自定义域名

1. 添加 Actions Variable `CUSTOM_DOMAIN=tools.example.com`，并把 `SITE_URL` 改成 `https://tools.example.com`；
2. 重新运行工作流，程序会生成 `docs/CNAME`；
3. 在 DNS 添加 CNAME：`tools` 指向 `你的用户名.github.io`；
4. 回到 Pages 设置填写自定义域名，证书生效后启用 **Enforce HTTPS**。

根域名需按 GitHub Pages 官方文档配置 A/AAAA 或 ALIAS/ANAME 记录。

## 目录说明

`fetcher.py` 抓取和去重，`generator.py` 生成双语 Markdown，`build.py` 生成 `docs/`，`main.py` 串起每日流程；`content/posts/` 保存文章源文件，`templates/` 保存 Jinja2 模板，`.github/workflows/deploy.yml` 负责定时提交。

需求指定的 `https://www.producthunt.com/feed.rss` 当前可能返回 404，抓取器会自动回退到 `https://www.producthunt.com/feed` Atom Feed，也可通过 `PRODUCT_HUNT_FEED_URL` 覆盖。
