# 全息 arXiv 每日推送

一个可在 GitHub Actions 上自动运行的 Python 项目：工作日抓取 arXiv 官方 Atom 源，用在线 OpenAI-compatible 模型筛选理论物理全息论文，生成中文静态网站，并通过 PushPlus 推送精简目录。

> GitHub Actions 在云端执行，所以即使个人电脑关机，定时任务仍会运行。定时触发设置为 **UTC 05:45–11:45 每小时一次**（北京时间 13:45–19:45），并在程序层限制只有北京时间 13:00–20:00 才允许处理和推送；若 GitHub 把任务延迟到夜间，会安全跳过而不会凌晨发送。也可在 Actions 页面手动运行。

## 功能概览

- 完整检查 `hep-th`；同时检查 `gr-qc`、`hep-ph`、`hep-lat`、`nucl-th`、`math-ph`、`quant-ph`、`cond-mat.str-el`、`cond-mat.supr-con`、`cond-mat.quant-gas`、`cond-mat.stat-mech`。
- `hep-th` 全量进入在线模型分类；其他分类先用宽泛全息词表高召回，并排除光学/数字全息等同名主题。
- 按无版本 arXiv ID 去重；v1 新论文可以推送，v2+ 修订保留在网站和状态中但不重复推送。PushPlus 短暂失败或关闭时，未发送 v1 会在下次运行自动补发。
- 主模型默认 `deepseek-v4-flash`；仅在低置信度、无效 JSON 或重点论文时使用 `deepseek-v4-pro` 复核。没有本地模型。
- 完整论文按 `YYYY-MM` 写入月度归档；`data/state.json` 只保留轻量去重索引和有限推送日志，不再嵌入论文全文。
- 首页只加载最近 30 天；更早论文通过年份/月度归档页按需加载，避免手机浏览器和单个 JSON/HTML 文件随时间变慢。
- 生成浅色响应式网站、`docs/data/latest.json` 与月度数据；所有论文和模型文本写入 HTML 前均转义。
- 每次运行自动检查 `data/` 与 `docs/` 文件大小：20 MB 提醒，90 MB 直接阻止提交，早于 GitHub 100 MB 单文件硬限制。
- PushPlus 默认只包含统计、主题目录和重点推荐，避免消息过长。同步 `code=200` 仅记为 `accepted_pending_verification`，同时保存 `shortCode`。可设置官方支持的回调地址获取异步结果。

## 目录

```text
holo_arxiv/                 生产代码
├── state.py                轻量索引、旧格式迁移、月度原始归档
├── site.py                 最近30天首页与年份/月度归档页面
└── size_guard.py           GitHub单文件大小预警与硬保护
tests/                      pytest 测试与离线 Atom fixture
data/state.json             轻量去重索引和最近推送记录
data/archive/YYYY-MM.json   按月保存的完整论文历史
docs/index.html             最近30天首页
docs/data/latest.json       最近30天机器可读数据
docs/data/YYYY-MM.json      网站月度数据
docs/archive/               年份/月度历史页面
.github/workflows/daily.yml 定时、测试、迁移、大小监控、提交与部署
```

## 先做完全离线演练（推荐）

要求 Python 3.11+。在项目目录执行：

```bash
python -m pip install -r requirements.txt
python -m pytest -q
python -m holo_arxiv --dry-run --state .dry-run/state.json --docs .dry-run/docs --preview .dry-run/pushplus-preview.json
```

也可以使用最短命令 `python -m holo_arxiv --dry-run`，但它会把 fixture 记录写入默认 `data/` 和 `docs/`，因此日常建议使用上面的 `.dry-run` 独立路径。

离线模式严格走完“fixture → 规则候选 → 假分类器 → 状态 → 网页 → PushPlus payload 预览”，不会访问网络、不会读取 API 密钥、不会发送消息。预览在 `.dry-run/pushplus-preview.json`。

## GitHub 配置（无需一直开电脑）

1. 把本项目推送到你自己的 GitHub 仓库（本项目不会自动创建远程仓库）。
2. 仓库进入 **Settings → Secrets and variables → Actions**：
   - **Secrets**（敏感）：`DEEPSEEK_API_KEY`、`PUSHPLUS_TOKEN`。
   - **Variables**（普通配置）：
     - `SITE_BASE_URL`：例如 `https://用户名.github.io/仓库名/`
     - 可选 `PUSHPLUS_TOPIC`、`PUSHPLUS_CALLBACK_URL`
     - 通常不必设置：`DEEPSEEK_BASE_URL`、`DEEPSEEK_MODEL`、`DEEPSEEK_REVIEW_MODEL`，工作流已有默认值。
3. 进入 **Settings → Pages → Build and deployment**，Source 选择 **GitHub Actions**。
4. 在 **Actions** 页选择“全息 arXiv 每日推送”，先点 **Run workflow** 手动验证。

工作流先安装依赖和运行测试，再执行程序；旧版单体状态会自动迁移为月度归档，然后运行单文件大小检查。只有 `docs/` 或 `data/` 有变化时才提交，随后使用官方 Pages actions 部署。工作流不监听 `push`，因此机器人提交不会递归触发。手动运行时可勾选 `deploy_only`，仅重新部署当前网站，不抓取论文、不调用 DeepSeek、也不发送 PushPlus。

## 本地在线运行（可选）

复制 `.env.example` 只作为填写参考。本程序故意不自动读取 `.env`；需在当前终端设置环境变量。例如 Bash：

```bash
export DEEPSEEK_API_KEY='你的密钥'
export PUSHPLUS_TOKEN='你的令牌'
export SITE_BASE_URL='https://example.github.io/holo-arxiv/'
python -m holo_arxiv
```

**不要提交** `.env`、真实密钥或 token；`.gitignore` 已忽略 `.env`。日志不会打印 token。

### 环境变量

| 名称 | 默认值 | 说明 |
|---|---|---|
| `DEEPSEEK_API_KEY` | 无 | 在线分类必需 |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | 自动规范为唯一 `/v1/chat/completions`，不会重复 `/v1` |
| `DEEPSEEK_MODEL` | `deepseek-v4-flash` | 主分类模型 |
- `DEEPSEEK_REVIEW_MODEL` | `deepseek-v4-pro` | 条件复核模型 |
| `PUSHPLUS_TOKEN` | 无 | 有新 v1 且启用推送时必需 |
| `PUSHPLUS_ACCESS_KEY` | 空 | 可选；配置后查询 PushPlus 异步最终投递状态。需在 PushPlus 开发设置中配置并注意其有效期/安全 IP |
| `PUSHPLUS_ENABLED` | `false` | 安全开关；只有显式设为 `true` 才真实发送 |
| `PUSHPLUS_TOPIC` | 空 | 可选群组编码 |
| `PUSHPLUS_CALLBACK_URL` | 空 | 可选异步结果回调 |
| `SITE_BASE_URL` | 空 | 推送中的完整网站链接 |

可用 `--target-date YYYY-MM-DD` 在线重跑指定 UTC 日期。程序失败会返回非零退出码；PushPlus 请求失败时不会写入 `sent_versions`，下次仍会重试该 v1。

## 数据与安全说明

- 模型只能依据题目和摘要输出；系统提示明确禁止杜撰，并使用严格字段、主题和用户重点标签校验。
- 用户研究支线标签独立保存，不把 p 波、多分量、multi-trace、QNM、BEC、D3–D7/D3–D5 探针膜与 Floquet 驱动等方向混成自造标签。
- `data/state.json` 适合 Git 跟踪；`docs/data.json` 供网页或后续工具读取。
- `docs/data.json` 是独立 JSON 文件；静态 HTML 对题目、摘要、作者、模型文本和 URL 属性进行转义，降低 XSS 风险。
- PushPlus 官方接口为异步：HTTP 接收成功不等于最终送达。设置 `PUSHPLUS_CALLBACK_URL` 可接收最终状态；未回调前状态明确记录为 `accepted_pending_verification`。

## 测试

```bash
python -m pytest -q
```

测试覆盖 Atom 解析、ID/版本归一、跨分类去重、候选规则、模型 JSON 校验、API URL 拼接、条件复核、状态与修订、HTML XSS、PushPlus payload/失败语义，以及无网络 dry-run。

## 许可证

MIT，见 [LICENSE](LICENSE)。
