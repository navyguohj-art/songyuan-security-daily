# 松原安全每日信息看板

这是一个用于跟踪松原安全（300893，浙江松原汽车安全系统股份有限公司）公开信息的本地项目。

项目会优先抓取公司公告、交易所/巨潮/东方财富公告信息，其次抓取东方财富等正规财经媒体聚合新闻，并生成一个可交互的静态 HTML 看板。

## 当前产物

- `outputs/index.html`：GitHub Pages 站点首页。
- `outputs/songyuan_security_daily.html`：每日信息汇总看板，可直接用浏览器打开。
- `data/pe_history.json`：自 2020-09-24 上市以来的每日 PE(TTM) 历史记录。
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

同一工作流会在生成并提交报告后，把 `outputs` 原样发布到 GitHub Pages；
发布成功后，再通过 QQ SMTP 向发件账号本人发送最新公开链接。整条链路运行在
GitHub 云端，电脑关机或休眠不影响执行。

生成脚本会在首次运行时补齐上市以来的全部市盈率记录；后续运行从本地最新交易日开始增量拉取，更新 `data/pe_history.json`，并将完整历史嵌入网页。网页支持近 1 月、3 月、6 月、1 年、3 年、上市以来及自定义日期范围查看。

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

## GitHub Pages 与 QQ 邮件

GitHub Pages 直接发布 `outputs` 目录，不会改变看板 HTML、内容采集逻辑或
视觉样式。仓库 Settings → Pages 中的 Source 需要选择 **GitHub Actions**。

QQ 邮件通知使用两个 Repository secrets：

- `QQ_SMTP_USER`：QQ 发件邮箱账号；通知会发送给该账号本人。
- `QQ_SMTP_AUTH_CODE`：QQ 邮箱为 SMTP 生成的授权码，不是邮箱登录密码。

授权码只由 GitHub Actions 在运行时读取，不写入代码、日志或仓库。若 secrets
尚未配置，报告生成与 Pages 发布仍会正常完成，只跳过邮件通知。

## Netlify 回退部署

本项目已包含 `netlify.toml`：

- Publish directory: `outputs`
- Build command: `python3 scripts/generate_daily_report.py`

旧的 Netlify 配置暂时保留作为迁移回退，不影响 GitHub Pages 发布。

原 Netlify 流程：

1. 将项目推送到 GitHub 仓库。
2. 在 Netlify 中选择 `Add new site` -> `Import an existing project`。
3. 连接该 GitHub 仓库。
4. Netlify 会读取 `netlify.toml`，部署 `outputs/index.html`。
5. 每天 08:30 北京时间，GitHub Actions 更新 HTML 并提交；Netlify 因 GitHub 推送自动重新部署。

## 免责声明

本项目仅基于公开信息进行整理和规则化分析，不构成投资建议。股票投资存在风险，请结合公告原文、财报、估值、行业景气度和个人风险承受能力独立判断。
