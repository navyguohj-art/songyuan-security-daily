# 松原安全每日信息看板

这是一个用于跟踪松原安全（300893，浙江松原汽车安全系统股份有限公司）公开信息的本地项目。

项目会优先抓取公司公告、交易所/巨潮/东方财富公告信息，其次抓取东方财富等正规财经媒体聚合新闻，并生成一个可交互的静态 HTML 看板。

## 当前产物

- `outputs/index.html`：Netlify 站点首页。
- `outputs/songyuan_security_daily.html`：每日信息汇总看板，可直接用浏览器打开。
- `data/sources.json`：股票代码、公司名称和公开数据源配置。
- `scripts/generate_daily_report.py`：每日看板生成脚本。公告原文关键点提取会使用 `pypdf`；在 Codex bundled Python 中已可用。

## 信息排序原则

1. 公司公告、交易所披露、申报文件优先于普通新闻。
2. 对投资价值影响更大的事件优先展示，例如再融资、财报、现金流、股权激励、重大风险提示。
3. 普通概念行情、行业资金流、筹码榜单等信息保留，但权重较低。

## 更新方式

GitHub Actions 会在每天北京时间 08:30 自动运行生成脚本。对应 UTC cron 为：

```text
30 0 * * *
```

如果 Netlify 已连接该 GitHub 仓库，每次 GitHub Actions 提交更新后，Netlify 会自动重新部署。

也可以手动运行：

```bash
python3 scripts/generate_daily_report.py
```

如需完整读取新公告 PDF 原文，建议使用 Codex bundled Python：

```bash
/Users/navy_mac_mini_2024_1/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/generate_daily_report.py
```

生成结果会写入：

```text
outputs/index.html
outputs/songyuan_security_daily.html
```

## Netlify 部署

本项目已包含 `netlify.toml`：

- Publish directory: `outputs`
- Build command: `python3 scripts/generate_daily_report.py`

推荐流程：

1. 将项目推送到 GitHub 仓库。
2. 在 Netlify 中选择 `Add new site` -> `Import an existing project`。
3. 连接该 GitHub 仓库。
4. Netlify 会读取 `netlify.toml`，部署 `outputs/index.html`。
5. 每天 08:30 北京时间，GitHub Actions 更新 HTML 并提交；Netlify 因 GitHub 推送自动重新部署。

## 免责声明

本项目仅基于公开信息进行整理和规则化分析，不构成投资建议。股票投资存在风险，请结合公告原文、财报、估值、行业景气度和个人风险承受能力独立判断。
