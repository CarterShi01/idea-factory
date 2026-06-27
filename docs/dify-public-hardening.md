# 公网 Dify 安全硬化 + 验证清单

> **目的**:北京 Dify 已公网暴露(经 host nginx)。本清单确保**别人无法登录后台、无法接管实例、无法刷你算力、攻陷暴露区也打不回核心**。
> **先确保安全,再继续推进 Dify 集成**(建流等)。
> 配套:OC repo `docs/dify-deploy-runbook.md` Part 7(公网硬化)、`docs/core-to-beijing-connectivity-runbook.md`(连通)、memory `core-exposed-security-zoning`(分区纪律);本项目 [`dify-handoff.md`](dify-handoff.md) ⑦。
>
> ⚠️ **执行边界**:本清单的动作 = 改北京机运行栈 / nginx / 凭证(7 硬门:上线部署 + 改凭证)。**编码手不自动执行**——创始人(或 devops)照做,凡设口令/key 处由人填。

---

## 0. 威胁模型(一段)

北京 Dify = **暴露区,假设面向敌意互联网**。四个安全目标:

1. **没人能接管控制台**(抢 `/install`、爆破登录)。
2. **公网根本够不到管理后台登录页**(把攻击面缩到只剩"已发布 app / API",且都有 key)。
3. **没人能刷你算力**(公网 + 计量后端 = 开放钱包)。
4. **攻陷北京 ⇏ 打回核心**(暴露区不持核心凭证/tailnet,无回攻链路)。

---

## 1. 🔴 起手第一查:`/install` 必须已被你认领

Dify 的逻辑:**谁第一个打开 `/install` 谁就建管理员、谁就拥有整个实例。** 公网可达 + 管理员未建 = 任何人抢先接管。

**查**(北京机本地;`/install` 已认领 → 应跳登录,不再给注册表单):
```bash
# 北京机上(或经 SSH 隧道):
curl -sI http://127.0.0.1:8080/install        # 已认领通常 302→/signin;未认领才给 setup
curl -s  http://127.0.0.1:8080/console/api/setup   # {"step":"finished"} = 已认领;"not_started"/表单 = 危险!
```

- **若未认领** → **立刻**用浏览器开 `/install` 设**强口令**管理员账号(runbook line 111),抢在任何人之前。
- 设完再继续后面的 nginx 锁定。

---

## 2. 关掉自助注册(只许邀请制)

确保陌生人不能自己注册账号进你的工作区。Dify `.env` / 环境:

```bash
# 期望:不开放注册;新成员只能由管理员邀请
ALLOW_REGISTER=false            # 或对应版本的注册开关
ALLOW_CREATE_WORKSPACE=false    # 不让外人建工作区
# 邮箱邀请需要 SMTP;无 SMTP 时管理员手动建号即可
```
改后 `docker compose up -d` 重载。**验**:退出登录后访问注册入口应被拒。

---

## 3. nginx:把后台锁进白名单 —— 本清单最强的一招

> 思路:**默认拒绝整站,只对外开真正需要公网的路径**。让公网**够不到登录页**,爆破无从谈起。

先决定**到底什么需要公网**(见 §3.0),再套 §3.1 配置。

### 3.0 决策:什么真的需要公网?(尽量缩)

| 路径 | 是什么 | 需要公网吗 |
|---|---|---|
| `/console/api/*`、`/install`、控制台 SPA(`/`,`/apps`,`/datasets`…) | **管理后台**(改 prompt 流、看数据、配模型) | **否**——只你自己用 → 锁 IP 白名单 / basic-auth |
| `/v1/*` | **App Service API**(idea-factory 调,bearer app-key 保护) | **看部署**:若 idea-factory **跑在北京本机**调 `127.0.0.1` → **不必公网**;若从外部调 → 仅对**已知调用方 IP** 开 |
| 已发布 webapp(`/chat/*`、`/completion/*` 等) | 对外产品页 | 仅当你确实发布给外部用户;否则一并锁 |

> **推荐最小面**:idea-factory 的 Dify 调用尽量走**北京本机 `127.0.0.1`**(同机,不出公网,符合 no-straddle:OC 核心不调公网实例)。如此一来**几乎没有路径需要公网**,整站锁白名单即可,攻击面最小。

### 3.1 host nginx 配置片段(反代 `127.0.0.1:8080` 的那个 server 块)

```nginx
# —— 允许名单:只放你自己的出口 IP ——
geo $dify_allowed {
    default 0;
    # 新加坡 OC 核心机公网出口
    43.156.82.236/32   1;
    # Windows VPS 公网出口 IP(按实际填;tailnet IP 对公网 nginx 无意义,要填它的公网出口)
    # <WIN_VPS_PUBLIC_IP>/32  1;
    # 你的常用办公/家庭 IP(可选)
    # <YOUR_IP>/32  1;
}

server {
    listen 443 ssl http2;
    server_name dify.<你的域名>;

    # —— TLS(§4)——
    ssl_certificate     /etc/letsencrypt/live/dify.<域名>/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/dify.<域名>/privkey.pem;

    # —— 管理后台 + setup:白名单外一律拒 ——
    location ~ ^/(install|console|apps|datasets|tools|account|signin|workspace) {
        if ($dify_allowed = 0) { return 403; }
        # 可叠加 basic-auth 做二层:auth_basic "dify"; auth_basic_user_file /etc/nginx/.dify_htpasswd;
        proxy_pass http://127.0.0.1:8080;
        include proxy_params;
    }

    # —— App API:bearer-key 保护,按需对已知调用方开 + 限速(§5)——
    location /v1/ {
        # 若 idea-factory 走北京本机 127.0.0.1,这段可直接 `return 403;` 彻底不对外
        if ($dify_allowed = 0) { return 403; }   # 收紧:仅已知调用方;或删此行靠 app-key + 限速
        limit_req zone=dify_api burst=20 nodelay;
        proxy_pass http://127.0.0.1:8080;
        include proxy_params;
    }

    # —— 其余(含控制台 SPA 根 / 静态)默认锁白名单 ——
    location / {
        if ($dify_allowed = 0) { return 403; }
        proxy_pass http://127.0.0.1:8080;
        include proxy_params;
    }
}

# http → https 强制跳转
server {
    listen 80;
    server_name dify.<你的域名>;
    return 301 https://$host$request_uri;
}
```

> ⚠️ Dify 的精确路由随版本(1.14.2)略有差异 —— 套用后**按 §6 实测**每条 location 行为对不对,别假设。basic-auth 生成:`htpasswd -c /etc/nginx/.dify_htpasswd <user>`。

---

## 4. TLS:登录口令绝不走明文

- host nginx/caddy 上 Let's Encrypt 证书,80 强制 301 → 443(见 §3.1)。
- **绝不**让 `/install`、`/console`、登录页跑在明文 http(口令会被中间人截)。
- **验**:`curl -sI http://dify.<域名>/` 应 301 到 https。

---

## 5. 限速 + 配额:防刷算力(开放钱包)

公网 + 计量后端(现 Tencent LKEAP)= 任何人刷 `/v1` 就是刷你的钱。

```nginx
# nginx http{} 顶层
limit_req_zone $binary_remote_addr zone=dify_api:10m rate=5r/s;   # /v1 用(见 §3.1 location)
```
- 另在 Dify 侧给每个 app-key 配**调用配额**(runbook Part 7「每消费方 API-key + 配额」)。
- App-key 是 bearer 凭证:**只存在 idea-factory 的 env / 密钥管理,绝不进 git、不进日志**。

---

## 6. 强秘钥 + 版本

- **强口令**:管理员、`SECRET_KEY`(`openssl rand -base64 42`)、`PGVECTOR_PASSWORD`、任何对外认证(runbook line 73/81/125)。任一是弱口令/默认值 = 漏。
- **轮换**:若 `/install` 早前可能被人摸过、或密钥曾明文流转 → 轮换 `SECRET_KEY` + 管理员口令。
- **版本/CVE**:记录当前 Dify 版本(1.14.2),关注其安全公告;升级走 stock 镜像 tag(别 fork 核心源码,见 handoff ①)。

---

## 7. 暴露区隔离(攻陷北京 ⇏ 打回核心)

OC 分区纪律(runbook line 13-14 / memory `core-exposed-security-zoning`),**逐条自查**:

- [ ] 北京机**不持有**任何核心地址 / tailnet 凭证 / 核心 SSH 私钥。(连通是"核心→北京"单向发起,北京无回连凭证。)
- [ ] **无"北京→核心"防火墙洞**:核心私域端口不对北京开。
- [ ] 北京机**出站**尽量收紧(只放它要的:Tencent API、apt 镜像、Let's Encrypt),减少被当跳板回攻/外联的面。
- [ ] `deploy` 用户无 passwordless sudo、不在 docker 组之外的特权;SSH 仅密钥登录、禁口令登录。
- [ ] Lighthouse 防火墙:只放行确需的入站(443;22 限源 IP 到核心出口),**别直开 8080**(runbook line 36)。

---

## 8. 验证 playbook(硬化后,从"外部"视角实测)

从**白名单外**的设备(如手机 4G,不是你白名单 IP)实测——这才是攻击者视角:

```bash
# 1) 后台登录页:白名单外应 403,够不到
curl -sI https://dify.<域名>/console        # 期望 403
curl -sI https://dify.<域名>/install        # 期望 403(且已认领)
curl -sI https://dify.<域名>/signin         # 期望 403

# 2) http 强制跳 https
curl -sI http://dify.<域名>/                 # 期望 301 → https

# 3) /v1 无 key 应 401;若已收紧 IP 则 403
curl -sI https://dify.<域名>/v1/             # 期望 401 或 403,绝不 200 裸放

# 4) 限速:连刷应见 429
for i in $(seq 1 30); do curl -s -o /dev/null -w "%{http_code} " https://dify.<域名>/v1/; done; echo
```
从**白名单内**(核心机出口)再测一遍:`/console` 应可达(200/302)。

**全绿判据**:外部够不到后台(403)、http 跳 https、`/v1` 不裸放、限速生效、`/install` 已认领且锁死。达成即"安全"。

---

## 9. 完成后回到推进路线

安全确认(§8 全绿)后再继续 Dify 集成,且优先把暴露面降到最低:
- 建两条流**优先走核心机 SSH 隧道 + DSL import**(`dify/import_flows.py`),少用公网 UI 拖画布。
- idea-factory 调 Dify 尽量走北京**本机 127.0.0.1**(no-straddle),减少 `/v1` 公网暴露。
- 详见 [`dify-handoff.md`](dify-handoff.md) §2 ①–④。
