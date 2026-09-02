# 云端定时触发器（Cloudflare Workers）配置指南

这个目录里的 Worker 用来替代 GitHub Actions 自带的 `schedule:` 定时器。
GitHub 的定时器已多次延迟或整天不触发，因此改为：

```
Cloudflare Cron（工作日 UTC 06:45 / 08:45 / 10:45，即北京时间 14:45 / 16:45 / 18:45）
    → 调用 GitHub workflow_dispatch API
    → GitHub Actions 执行抓取、DeepSeek 分类、网站生成和 PushPlus 推送
```

流水线本身是幂等的：已分类的论文不会重复调用模型，已推送的论文不会重复发送，
所以一天三次触发是安全的冗余，不是重复推送。

全部配置都在网页上完成，不需要在电脑上安装任何工具，也不需要电脑开机。

---

## 第一步：创建 GitHub 访问令牌（Fine-grained PAT）

1. 打开：https://github.com/settings/personal-access-tokens/new
2. Token name 填：`holo-arxiv-scheduler`
3. Expiration 选一个较长的时间（例如 1 年，到期前 GitHub 会邮件提醒你换）
4. **Repository access** 选 `Only select repositories`，只勾选
   `LiXin-tf/holography-arxiv-digest`
5. **Permissions → Repository permissions** 里找到 `Actions`，选 `Read and write`
6. 其他权限全部保持 `No access`
7. 点 `Generate token`，**复制生成的令牌**（页面关闭后无法再查看）

这个令牌只授权这一个仓库的 Actions 触发权限，权限范围已经最小化。

## 第二步：创建 Cloudflare 账号和 Worker

1. 打开 https://dash.cloudflare.com 注册免费账号（不需要信用卡）
2. 左侧菜单选 **Workers 和 Pages → 创建 Worker**
3. 名称填 `holo-arxiv-scheduler`，点 **部署**
4. 部署后点 **编辑代码**，把 `worker.js` 的全部内容粘贴进去，替换默认代码，点 **部署**

## 第三步：配置加密变量（放 GitHub 令牌）

1. 在 Worker 页面进入 **设置 → 变量和机密**
2. 添加 **机密（Secret）**：
   - 名称：`GITHUB_TOKEN`
   - 值：第一步复制的 GitHub 令牌
3. （可选）再加一个 `MANUAL_KEY`，值随便设一个密码，用于手动测试时防止别人乱按

## 第四步：添加定时触发

1. 在 Worker 页面进入 **设置 → 触发器 → Cron 触发器**（Settings → Triggers → Cron Triggers）
2. 添加三条（Cloudflare 使用 UTC，且星期字段 1=周日，所以工作日写 `mon-fri` 或 `2-6`）：

   | Cron 表达式 | 含义 |
   |---|---|
   | `45 6 * * mon-fri` | 工作日北京时间 14:45 |
   | `45 8 * * mon-fri` | 工作日北京时间 16:45（冗余） |
   | `45 10 * * mon-fri` | 工作日北京时间 18:45（冗余） |

## 第五步：验证（两分钟）

1. 复制 Worker 的 URL（形如 `https://holo-arxiv-scheduler.<你的子域>.workers.dev`）
2. 如果设置了 `MANUAL_KEY`，浏览器访问 `该URL?key=你的密码`；否则直接访问该 URL
3. 页面显示 `GitHub dispatch -> HTTP 204 OK` 即成功
4. 打开 https://github.com/LiXin-tf/holography-arxiv-digest/actions 应看到一个新的
   `workflow_dispatch` 运行开始执行

验证后，以后每个工作日 Cloudflare 会自动触发，与你的电脑是否开机无关。

## 运维说明

- **查看触发日志**：Worker 页面 → 日志，能看到每次 cron 是否调用成功。
- **GitHub 令牌到期**：到期前 GitHub 会发邮件，重新生成后更新第三步的 Secret 即可。
- **费用**：Cloudflare Workers 免费版每天 10 万次请求，本项目每天最多 4 次，永远够用。
- **GitHub 自带 schedule**：仓库里 `daily.yml` 的 `schedule:` 保留作兜底；即使它偶尔
  触发，流水线幂等也不会造成重复推送。
