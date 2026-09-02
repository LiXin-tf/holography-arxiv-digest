// 全息 arXiv 每日推送 —— 云端定时触发器
//
// 作用：每天工作日 UTC 06:45（北京时间 14:45）由 Cloudflare Cron 调用，
// 通过 GitHub workflow_dispatch API 启动 holography-arxiv-digest 仓库的
// daily.yml 工作流。GitHub Actions 仍负责执行抓取、DeepSeek 分类、
// 网站生成和 PushPlus 推送；本 Worker 只负责“按时间按门铃”。
//
// 需要在 Cloudflare 中配置一个加密变量（Secret）：
//   GITHUB_TOKEN —— GitHub fine-grained PAT，仅授权 holography-arxiv-digest
//                  仓库的 Actions: Read and write 权限。
// 可选加密变量：
//   MANUAL_KEY   —— 若设置，则浏览器手动测试时必须带 ?key=相同的值。

const OWNER = "LiXin-tf";
const REPO = "holography-arxiv-digest";
const WORKFLOW = "daily.yml";
const REF = "main";

async function dispatch(env) {
  const url = `https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/${WORKFLOW}/dispatches`;
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${env.GITHUB_TOKEN}`,
      "Accept": "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "holo-arxiv-cloud-scheduler",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      ref: REF,
      inputs: { deploy_only: "false" },
    }),
  });
  const text = await response.text();
  return { ok: response.ok, status: response.status, body: text };
}

function logResult(source, result) {
  const message = `[${source}] GitHub dispatch -> HTTP ${result.status} ${result.ok ? "OK" : "FAILED"} ${result.body}`;
  if (result.ok) {
    console.log(message);
  } else {
    console.error(message);
  }
  return message;
}

export default {
  // Cloudflare Cron Trigger 入口
  async scheduled(event, env, ctx) {
    const result = await dispatch(env);
    logResult(`cron ${event.cron}`, result);
  },

  // 手动测试入口：部署后访问 Worker 的 URL 即可触发一次
  async fetch(request, env) {
    // 诊断信息：只显示令牌的长度、前缀和是否有首尾空白，绝不输出完整令牌。
    const token = env.GITHUB_TOKEN;
    const tokenDebug = token
      ? `token: present, length=${token.length}, prefix="${token.slice(0, 8)}", hasWhitespace=${token !== token.trim()}`
      : "token: UNDEFINED";
    if (env.MANUAL_KEY) {
      const key = new URL(request.url).searchParams.get("key");
      if (key !== env.MANUAL_KEY) {
        return new Response(tokenDebug + "\nForbidden: wrong or missing ?key=\n", { status: 403 });
      }
    }
    const result = await dispatch(env);
    const message = logResult("manual", result);
    return new Response(tokenDebug + "\n" + message + "\n", { status: result.ok ? 200 : 502 });
  },
};
