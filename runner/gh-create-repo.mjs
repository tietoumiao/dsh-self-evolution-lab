#!/usr/bin/env node
// gh-create-repo.mjs —— 用 GH_TOKEN 校验身份并可创建仓库（只建 public 仓库，只走 REST 出站请求）。
// 用法:
//   node gh-create-repo.mjs check
//   node gh-create-repo.mjs create <owner> <repo> "<description>" [topic1,topic2]
// 输出只包含 login / 仓库 URL / scopes，绝不打印 token。

const API = "https://api.github.com";
const token = process.env.GH_TOKEN;
if (!token) {
  console.error("GH_TOKEN missing");
  process.exit(2);
}
const headers = {
  Authorization: `Bearer ${token}`,
  Accept: "application/vnd.github+json",
  "X-GitHub-Api-Version": "2022-11-28",
  "User-Agent": "dsh-agi-publish",
};

async function call(method, path, body) {
  const res = await fetch(API + path, {
    method,
    headers: { ...headers, ...(body ? { "Content-Type": "application/json" } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await res.text();
  let json = null;
  try { json = text ? JSON.parse(text) : null; } catch { /* 非 JSON */ }
  return { status: res.status, json, text };
}

const cmd = process.argv[2];
if (cmd === "check") {
  const me = await call("GET", "/user");
  const rate = await call("GET", "/rate_limit");
  console.log(JSON.stringify({
    status: me.status,
    login: me.json?.login ?? null,
    name: me.json?.name ?? null,
    scopes: (me.status === 200 ? "token-ok" : me.text.slice(0, 200)),
    rate_remaining: rate.json?.resources?.core?.remaining ?? null,
  }, null, 2));
  process.exit(me.status === 200 ? 0 : 1);
}

if (cmd === "create") {
  const [, , , owner, repo, description, topics] = process.argv;
  if (!owner || !repo || !description) {
    console.error("usage: create <owner> <repo> <description> [topics]");
    process.exit(2);
  }
  const existing = await call("GET", `/repos/${owner}/${repo}`);
  if (existing.status === 200) {
    console.log(JSON.stringify({ created: false, reason: "already-exists", url: existing.json.html_url, private: existing.json.private, default_branch: existing.json.default_branch }, null, 2));
    process.exit(0);
  }
  const created = await call("POST", "/user/repos", {
    name: repo,
    description,
    private: false,
    has_issues: false,
    has_projects: false,
    has_wiki: false,
    auto_init: false,
  });
  if (created.status !== 201) {
    console.error(JSON.stringify({ status: created.status, error: created.text.slice(0, 500) }));
    process.exit(1);
  }
  if (topics) {
    const t = await call("PUT", `/repos/${owner}/${repo}/topics`, { names: topics.split(",").map((s) => s.trim()).filter(Boolean) });
    if (t.status !== 200) console.error(`topics: ${t.status} ${t.text.slice(0, 200)}`);
  }
  console.log(JSON.stringify({
    created: true,
    url: created.json.html_url,
    ssh_url: created.json.ssh_url,
    https_url: created.json.clone_url,
    default_branch: created.json.default_branch,
    private: created.json.private,
    has_issues: created.json.has_issues,
  }, null, 2));
  process.exit(0);
}

console.error("usage: gh-create-repo.mjs check | create <owner> <repo> <description> [topics]");
process.exit(2);
