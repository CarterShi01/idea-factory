# 把 Dify 经 di.enjoyapier.cloud 公网暴露(IP 白名单硬化)

> 目标:`https://di.enjoyapier.cloud` 公网可达 Dify 控制台,用来编排工作流;**只放行白名单 IP**,白名单外一律 403。
> 防护层:**IP 白名单 + TLS + Dify 强口令 + 关自助注册 + 限速**。
> 决策:创始人 2026-06-27 选「IP 白名单」(见 [`dify-public-hardening.md`](dify-public-hardening.md) §3)。
>
> ⚠️ **7 硬门**:这是「上线部署 + 改凭证」。**root/nginx/证书步骤由创始人执行**(本机这只手是 `deploy`,无 sudo);**DNS、所有口令由创始人设**。Dify 侧(.env + 重启)`deploy` 可做,但**需创始人显式 go 后**才动。

## 既有环境(已查实)
- 北京机 `211.159.154.240`;`:443` 由 **sslh** 多路复用(`--ssh 127.0.0.1:22 --tls 127.0.0.1:8443`)。
- host nginx vhost 走 `listen 127.0.0.1:8443 ssl`(在 sslh 后);证书 certbot + acme-webroot `/var/www/html`。
- Dify compose:`/home/deploy/dify/docker`;Dify 自带 nginx 在 host `:8080`(http)/`:8444`(https);Lighthouse **未开** 8080/8444(公网直连已挡 ✅)。
- Dify `.env` 公网 URL 现全空;`setup:finished`(管理员已认领,6/24)。

---

## 步骤(按序;标注谁做)

### 0)DNS —— 创始人
在 enjoyapier.cloud 的 DNS 加 A 记录:`di` → `211.159.154.240`。
验证:`dig +short di.enjoyapier.cloud` 应回 `211.159.154.240`。

### 1)nginx :80 vhost(acme + 跳转)—— 创始人(root)
新建 `/etc/nginx/sites-available/dify`:
```nginx
server {
    listen 80; listen [::]:80;
    server_name di.enjoyapier.cloud;
    location /.well-known/acme-challenge/ { root /var/www/html; }
    location / { return 301 https://$host$request_uri; }
}
```
```bash
sudo ln -s /etc/nginx/sites-available/dify /etc/nginx/sites-enabled/dify
sudo nginx -t && sudo systemctl reload nginx
```

### 2)签证书 —— 创始人(root)
```bash
sudo certbot certonly --webroot -w /var/www/html -d di.enjoyapier.cloud
# 成功后:/etc/letsencrypt/live/di.enjoyapier.cloud/{fullchain,privkey}.pem
```

### 3)nginx :8443 vhost(白名单 + 反代 Dify)—— 创始人(root)
把下面**追加**到同一个 `/etc/nginx/sites-available/dify` 文件(`geo`/`limit_req_zone` 是 http 级,放文件最前):
```nginx
# —— 白名单:只放行这些【公网出口 IP】(换网络就来这加一行)——
# ⚠️ 必须是公网出口 IP,不是 tailnet 100.x —— 北京机【故意 off-tailnet】(暴露区不入网,
#    防被攻破后回攻核心,见 memory core-exposed-security-zoning)。在目标机访问
#    https://api.ipify.org 看到的就是要填的 IP。
geo $di_ok {
    default 0;
    43.156.82.236/32   1;   # 新加坡核心机(idea-factory 调 /v1 + 这只手经此)
    43.165.169.167/32  1;   # Mac
    43.133.33.7/32     1;   # Windows VPS(经 a-browser 取得真实公网出口)
    # <家庭出口IP>/32   1;
    # <公司出口IP>/32   1;
}
limit_req_zone $binary_remote_addr zone=di_zone:10m rate=10r/s;

server {
    listen 127.0.0.1:8443 ssl;   # sslh 后面
    server_name di.enjoyapier.cloud;
    ssl_certificate     /etc/letsencrypt/live/di.enjoyapier.cloud/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/di.enjoyapier.cloud/privkey.pem;

    if ($di_ok = 0) { return 403; }   # 白名单外全拒(含登录页,公网根本看不到)

    client_max_body_size 100m;        # Dify 上传 / 导入 DSL 要

    location / {
        limit_req zone=di_zone burst=20 nodelay;
        proxy_pass http://127.0.0.1:8080;   # → Dify 自带 nginx
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_http_version 1.1;             # websocket(Dify 控制台要)
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 3600s;           # 长连接 / SSE
    }
}
```
```bash
sudo nginx -t && sudo systemctl reload nginx
```

### 3b)清理旧 vhost + deny-all 默认站 —— 创始人(root)
kx.naoyoulv.cn 已确认下线;删其 vhost,并加一个"拒绝未知域名/raw IP"的默认站(堵住用 IP 直连蹭到 idea 真站)。
```bash
# 删 kx(stockwise)—— 确认 kx 下线后
sudo rm /etc/nginx/sites-enabled/stockwise
# (可选)旧 default 站也可移除:sudo rm /etc/nginx/sites-enabled/default
```
新建 `/etc/nginx/sites-available/deny-default`(并 ln 进 sites-enabled):
```nginx
# 未知 SNI / raw IP 直接断连(不泄露任何真站)
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;
    return 444;
}
server {
    listen 127.0.0.1:8443 ssl default_server;   # sslh tls 后端
    server_name _;
    ssl_certificate     /etc/letsencrypt/live/di.enjoyapier.cloud/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/di.enjoyapier.cloud/privkey.pem;
    return 444;
}
```
```bash
sudo ln -s /etc/nginx/sites-available/deny-default /etc/nginx/sites-enabled/deny-default
sudo nginx -t && sudo systemctl reload nginx
```
> 注:`idea` / `di` 是按 server_name 精确匹配,不受默认站影响;只有"没匹配上的"(raw IP、未知域名)落到 444。
> ⚠️ 删 default 后必须有这个 deny-default 顶上,否则 nginx 会拿"第一个 vhost"当默认 → raw IP 又蹭到 idea。

### 4)Dify 公网 URL + 关注册 —— `deploy` 可做(需创始人 go)
编辑 `/home/deploy/dify/docker/.env`:
```bash
CONSOLE_API_URL=https://di.enjoyapier.cloud
CONSOLE_WEB_URL=https://di.enjoyapier.cloud
SERVICE_API_URL=https://di.enjoyapier.cloud
APP_API_URL=https://di.enjoyapier.cloud
APP_WEB_URL=https://di.enjoyapier.cloud
ALLOW_REGISTER=false          # 该版本若无此键则忽略,改在控制台关邀请
```
```bash
cd /home/deploy/dify/docker && docker compose up -d   # 重建以加载新 env
```

### 5)Lighthouse —— 无需改
`:443` 已开(sslh 用)。**别开 8080/8444**(保持公网直连被挡)。

---

## 验证(§8 风格)
- **白名单内**(核心机):`curl -I https://di.enjoyapier.cloud/` → 200,浏览器能打开控制台并登录。
- **白名单外**(手机 4G):`curl -I https://di.enjoyapier.cloud/` → **403**(看不到登录页)。
- `curl -I http://di.enjoyapier.cloud/` → 301 → https。
- Dify 直连端口仍打不通:`curl https://211.159.154.240:8080/` → 超时。
- 登录后确认 Settings→Members 只有你;`setup:finished`。

## 全绿判据
白名单内可正常编排;白名单外 403;http→https;8080/8444 公网仍封;管理员仅你。达成即「公网可用且安全」。

---

## 实际落地(最终架构,2026-06-27)—— 去 sslh 版

> 执行时发现 sslh 1.22c **不支持 proxyprotocol**,且它在 :443 后面让 nginx 只看到 `127.0.0.1`、白名单失效。创始人确认不需要 SSH-over-443(只用控制台 + socat 中继登)→ **移除 sslh,nginx 直听 443**,真实 IP 原生可见,白名单直接生效,URL 干净。

**最终状态:**
- `sslh`:`systemctl stop + disable`(不再占 443;SSH-over-443 取消)。
- `nginx`:直听 `0.0.0.0:443`+`:80`,按 SNI 分流。sites-enabled = `idea-factory` / `dify` / `deny-default`(`stockwise`+旧`default` 已删)。
- `idea-factory` vhost:`listen 443 ssl`(原 `127.0.0.1:8443`),反代 `:3010`,现拿到真实 IP。
- `dify` vhost:`listen 443 ssl` + `geo $di_ok` 白名单(核心 `43.156.82.236` / Mac `43.165.169.167` / Windows `43.133.33.7`)+ 限速 + 反代 `127.0.0.1:8080`。
- `deny-default`:`listen 443 ssl default_server` + `:80 default_server` → `return 444`(raw IP / 未知域名)。
- Dify `.env`:`CONSOLE_API_URL`/`CONSOLE_WEB_URL`/`SERVICE_API_URL`/`APP_API_URL`/`APP_WEB_URL` = `https://di.enjoyapier.cloud`;`docker compose up -d` 已应用。
- 备份:`/tmp/idea-factory.bak.*`、`/tmp/sslh.default.bak`、`docker/.env.bak.*`。

**白名单加 IP**:编辑 `/etc/nginx/sites-available/dify` 的 `geo $di_ok` 加一行 `<IP>/32 1;` → `sudo nginx -t && sudo systemctl reload nginx`。
**要从 Mac/Windows 直接 SSH**:在 Lighthouse 给 :22 加那台的公网 IP(现仅放行核心 `43.156.82.236`)。
