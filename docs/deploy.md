# ProteinHub 部署指南

这份指南面向第一版生产部署：单台 Ubuntu 服务器、PostgreSQL、systemd
托管应用、Caddy 负责 HTTPS 反向代理。当前预计 10 人使用，这条路线足够稳，
也方便后续迭代。

## 1. 服务器准备

推荐配置：

- Ubuntu 22.04 或 24.04
- Python 3.11 或更高版本
- 2 vCPU / 4 GB RAM 起步
- 80 GB 以上 SSD；如果实验原始文件很多，优先扩磁盘
- 域名解析到服务器公网 IP

安装基础依赖：

```bash
sudo apt update
sudo apt install -y git postgresql postgresql-contrib curl gnupg software-properties-common
python3 --version
```

ProteinHub 要求 Python 3.11 或更高版本。Ubuntu 22.04 / Pop!_OS 常见默认
`python3` 是 3.10，需要额外安装 Python 3.11：

```bash
python3.11 --version
```

如果上面命令提示找不到 `python3.11`，先尝试：

```bash
sudo apt install -y python3.11 python3.11-venv python3.11-dev
```

如果 apt 源里也找不到，再添加 deadsnakes PPA 后安装：

```bash
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev
python3.11 --version
```

Pop!_OS/Ubuntu 默认 apt 源里可能没有 `caddy` 包。按 Caddy 官方 Debian/Ubuntu
包安装方式添加 apt 源后再安装：

```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo chmod o+r /usr/share/keyrings/caddy-stable-archive-keyring.gpg
sudo chmod o+r /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install -y caddy
caddy version
```

创建系统用户和目录：

```bash
sudo useradd --system --home-dir /var/lib/proteinhub --shell /usr/sbin/nologin proteinhub
sudo mkdir -p /opt/proteinhub /var/lib/proteinhub/storage /var/backups/proteinhub /opt/proteinhub-tools
sudo chown -R proteinhub:proteinhub /var/lib/proteinhub /var/backups/proteinhub /opt/proteinhub
sudo chmod 700 /var/backups/proteinhub
```

## 2. PostgreSQL

创建数据库用户和数据库：

```bash
sudo -u postgres createuser proteinhub --pwprompt
sudo -u postgres createdb proteinhub -O proteinhub
```

确认连接可用：

```bash
psql "postgresql://proteinhub:<password>@127.0.0.1:5432/proteinhub" -c "select 1;"
```

ProteinHub 启动时会初始化当前 schema。生产环境上线后，每次发布前都要先备份。

## 3. 部署应用

把代码放到 `/opt/proteinhub`。如果仓库是公开的，最省事的是先把目录让当前
用户可写，再用 HTTPS clone；如果仓库是私有的，就给执行 clone 的那个用户
配置 GitHub SSH key 或 PAT。

```bash
sudo mkdir -p /opt/proteinhub
sudo chown -R "$USER":"$USER" /opt/proteinhub
git clone https://github.com/Haoyu-Ding/ProteinHub.git /opt/proteinhub
sudo chown -R proteinhub:proteinhub /opt/proteinhub
cd /opt/proteinhub
sudo -u proteinhub git checkout codex-architecture-cleanup
sudo -u proteinhub git pull --ff-only
```

创建 Python 3.11 虚拟环境并安装依赖。如果之前误用 Python 3.10 创建过
`.venv`，先删掉旧环境再重建：

```bash
cd /opt/proteinhub
sudo rm -rf .venv
sudo -u proteinhub python3.11 -m venv .venv
sudo -u proteinhub .venv/bin/python -m pip install -U pip setuptools wheel
sudo -u proteinhub .venv/bin/pip install -e ".[dev]"
```

安装完成后先确认虚拟环境确实是 Python 3.11+，再跑一次项目检查：

```bash
cd /opt/proteinhub
sudo -u proteinhub .venv/bin/python --version
sudo -u proteinhub .venv/bin/python -m pytest
sudo -u proteinhub .venv/bin/python -m compileall -q proteinhub tests main.py
```

后续在 `/opt/proteinhub` 里拉代码时，也用 `proteinhub` 用户执行，避免 Git
因为目录所有者不同报 `dubious ownership`：

```bash
sudo -u proteinhub git -C /opt/proteinhub pull --ff-only
```

复制环境变量模板：

```bash
sudo cp /opt/proteinhub/.env.example /etc/proteinhub.env
sudo chown root:proteinhub /etc/proteinhub.env
sudo chmod 640 /etc/proteinhub.env
```

编辑 `/etc/proteinhub.env`，至少替换：

- `PROTEINHUB_DATABASE_URL`
- `PROTEINHUB_JWT_SECRET`
- `PROTEINHUB_NICEGUI_STORAGE_SECRET`
- `PROTEINHUB_ADMIN_EMAILS`

生成 secret 可以用：

```bash
python3.11 - <<'PY'
import secrets
print(secrets.token_urlsafe(48))
PY
```

如果你已经完成上面的 `pip install -e ".[dev]"`，接下来就从这里继续：

```bash
sudo cp /opt/proteinhub/.env.example /etc/proteinhub.env
sudo chown root:proteinhub /etc/proteinhub.env
sudo chmod 640 /etc/proteinhub.env
sudo editor /etc/proteinhub.env
```

编辑时至少替换这些值：

```bash
PROTEINHUB_DATABASE_URL=postgresql://proteinhub:<真实数据库密码>@127.0.0.1:5432/proteinhub
PROTEINHUB_ARTIFACT_STORAGE_BACKEND=database
PROTEINHUB_JWT_SECRET=<python3.11 生成的长随机字符串>
PROTEINHUB_NICEGUI_STORAGE_SECRET=<另一个长随机字符串>
PROTEINHUB_ADMIN_EMAILS=<你的管理员邮箱>
PROTEINHUB_DATA_DIR=/var/lib/proteinhub
PROTEINHUB_STORAGE_DIR=/var/lib/proteinhub/storage
```

保存后继续第 4-8 步：可选外部工具、安装 systemd service、健康检查、
选择访问方式、设置备份。

## 4. AKTA 和反向翻译外部工具

这一节是可选步骤。先部署主系统时可以不配置；ProteinHub 仍然可以登录、
建项目、建蛋白、上传 HPLC/SPR 等数据。

如果你现在只是先把网站跑起来，就执行这个检查命令，然后继续第 5 步：

```bash
cd /opt/proteinhub
sudo -u proteinhub .venv/bin/python scripts/check-external-tools.py \
  --env-file /etc/proteinhub.env
```

看到 AKTA 或 domesticator 显示未配置也没关系，只要命令没有失败即可。
不要在 `/etc/proteinhub.env` 里填写不存在的路径。

如果你现在就要启用 AKTA zip 渲染或批次 DNA 优化，再继续下面的配置。
不要把 `.legacy/` 里的本地虚拟环境直接提交到主仓库。推荐在服务器上这样放置：

```text
/opt/proteinhub-tools/
  akta/
    bin/python
    akta_hap.py
  domesticator-env/
    bin/python
  domesticator/
    domesticator.py
    database/
```

然后在 `/etc/proteinhub.env` 中配置：

```bash
PROTEINHUB_AKTA_HAP_PYTHON=/opt/proteinhub-tools/akta/bin/python
PROTEINHUB_AKTA_HAP_SCRIPT=/opt/proteinhub-tools/akta/akta_hap.py

PROTEINHUB_LEGACY_DOMESTICATOR_PYTHON=/opt/proteinhub-tools/domesticator-env/bin/python
PROTEINHUB_LEGACY_DOMESTICATOR_SCRIPT=/opt/proteinhub-tools/domesticator/domesticator.py
PROTEINHUB_LEGACY_DOMESTICATOR_DATABASE=/opt/proteinhub-tools/domesticator/database
```

`domesticator-env` 是 Python/conda 环境；`domesticator` 是脚本和 database 目录。
不要把 conda 环境直接建在已有 `domesticator.py` 和 `database/` 的目录里。

如果服务器上已经有 `domesticator.py` 和 `database/`，但
`/opt/proteinhub-tools/domesticator/bin/python` 不存在，按下面方式创建单独环境：

```bash
sudo rm -rf /opt/proteinhub-tools/domesticator-env
sudo chown -R zhaojiao:zhaojiao /opt/proteinhub-tools
~/anaconda3/bin/conda create -y --override-channels -c conda-forge -p /opt/proteinhub-tools/domesticator-env python=3.7 pip
/opt/proteinhub-tools/domesticator-env/bin/python -m pip install "pip<24.1" "setuptools==57.5.0" wheel
/opt/proteinhub-tools/domesticator-env/bin/pip install dnachisel==1.1 biopython==1.72 CAI==1.0.3 scipy==1.4.1 tqdm==4.64.1
sudo chown -R proteinhub:proteinhub /opt/proteinhub-tools
```

如果你用的是 miniforge，把 conda 命令换成：

```bash
~/miniforge3/bin/conda create -y --override-channels -c conda-forge -p /opt/proteinhub-tools/domesticator-env python=3.7 pip
```

`--override-channels` 用来绕过服务器本机 conda 配置里的失效镜像源。
不要再检查 `/opt/proteinhub-tools/domesticator/bin/python`；正确 Python 路径是
`/opt/proteinhub-tools/domesticator-env/bin/python`。
`CAI==1.0.3` 是旧包，所以 domesticator 环境需要先固定
`setuptools==57.5.0`。

然后确认这些文件真的存在：

```bash
sudo -u proteinhub test -x /opt/proteinhub-tools/akta/bin/python
sudo -u proteinhub test -f /opt/proteinhub-tools/akta/akta_hap.py
sudo -u proteinhub test -x /opt/proteinhub-tools/domesticator-env/bin/python
sudo -u proteinhub test -f /opt/proteinhub-tools/domesticator/domesticator.py
sudo -u proteinhub test -d /opt/proteinhub-tools/domesticator/database
```

说明：

- 普通 reverse translation 使用 Python 依赖，不需要 legacy domesticator。
- 批次 DNA 优化流程会调用 xiaopang/domesticator 外部脚本。
- AKTA 上传会调用 `akta_hap.py` 把 zip 渲染成 PNG。

上线前检查：

```bash
cd /opt/proteinhub
sudo -u proteinhub .venv/bin/python scripts/check-external-tools.py \
  --env-file /etc/proteinhub.env \
  --require-akta \
  --require-domesticator
```

如果暂时不上 AKTA 或 domesticator，可去掉对应 `--require-*` 参数。

## 5. systemd

安装 service：

```bash
sudo cp /opt/proteinhub/deploy/proteinhub.service /etc/systemd/system/proteinhub.service
sudo systemctl daemon-reload
sudo systemctl enable --now proteinhub
sudo systemctl status proteinhub
```

查看日志：

```bash
journalctl -u proteinhub -f
```

健康检查：

```bash
curl http://127.0.0.1:8080/api/health
```

期望返回 `status: ok`。

## 6. 访问方式：公网域名或只用内网

先确认服务本机可用：

```bash
curl http://127.0.0.1:8080/api/health
```

如果这一步返回 `status: ok`，再选择下面两种访问方式之一。

### 6.1 只在内网使用

这种方式不需要域名，也不需要公网 IP。适合先在实验室、办公室、同一局域网
或 VPN/Tailscale 网络里给少数人使用。

查看服务器内网 IP：

```bash
hostname -I
```

假设看到的内网 IP 是 `10.6.108.62`，复制内网 Caddy 模板：

```bash
sudo cp /opt/proteinhub/deploy/Caddyfile.lan.example /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

如果服务器启用了 UFW 防火墙，放行 80 端口：

```bash
sudo ufw allow 80/tcp
sudo ufw status
```

同一内网的用户访问：

```text
http://10.6.108.62/
```

如果你想临时绕过 Caddy，也可以访问 Uvicorn 端口，但需要把 systemd 里的
`--host 127.0.0.1` 改成 `--host 0.0.0.0`，不建议作为正式方式。

### 6.2 用公网域名访问

这种方式适合让外网用户直接访问，例如：

```text
https://proteinhub.example.com/
```

你需要在域名服务商的 DNS 控制台添加一条 A 记录：

```text
类型: A
主机记录: proteinhub
记录值: 服务器公网 IP
```

如果服务器在家里、学校或公司内网里，通常没有公网入站能力；这时只配 DNS
不会生效，还需要路由器端口转发、云服务器、公网反向代理、frp、Tailscale
或 Cloudflare Tunnel 这类方案。

确认 80/443 端口可从公网访问后，复制公网 Caddy 模板：

```bash
sudo cp /opt/proteinhub/deploy/Caddyfile.example /etc/caddy/Caddyfile
sudo editor /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

把 `your-domain.example.com` 替换成真实域名。Caddy 会自动申请和续期 HTTPS
证书。如果服务器启用了 UFW 防火墙，放行 80/443：

```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw status
```

检查外网访问：

```bash
curl https://your-domain.example.com/api/health
```

## 7. 备份和恢复

手动备份：

```bash
sudo -u proteinhub PROTEINHUB_ENV_FILE=/etc/proteinhub.env /opt/proteinhub/scripts/backup-postgres.sh
```

安装本机每天自动备份：

```bash
sudo cp /opt/proteinhub/deploy/proteinhub-backup.service /etc/systemd/system/proteinhub-backup.service
sudo cp /opt/proteinhub/deploy/proteinhub-backup.timer /etc/systemd/system/proteinhub-backup.timer
sudo systemctl daemon-reload
sudo systemctl enable --now proteinhub-backup.timer
sudo systemctl list-timers proteinhub-backup.timer
```

这个 timer 会每天凌晨 `02:15` 备份一次。如果服务器当时关机，开机后会补跑一次。
立即测试一次自动备份：

```bash
sudo systemctl start proteinhub-backup.service
sudo journalctl -u proteinhub-backup.service -n 50 --no-pager
ls -lh /var/backups/proteinhub
```

默认本地备份保留 `14` 天；可以在 `/etc/proteinhub.env` 里用
`PROTEINHUB_BACKUP_RETENTION_DAYS=30` 之类的值调整。

恢复前先停服务：

```bash
sudo systemctl stop proteinhub
sudo -u proteinhub PROTEINHUB_ENV_FILE=/etc/proteinhub.env /opt/proteinhub/scripts/restore-postgres.sh /var/backups/proteinhub/proteinhub_YYYYmmdd_HHMMSS.dump
sudo systemctl start proteinhub
```

## 8. 发布升级流程

每次上线按这个顺序：

```bash
cd /opt/proteinhub
sudo -u proteinhub PROTEINHUB_ENV_FILE=/etc/proteinhub.env scripts/backup-postgres.sh
sudo -u proteinhub git pull --ff-only
sudo -u proteinhub .venv/bin/pip install -e ".[dev]"
sudo -u proteinhub .venv/bin/python -m pytest
sudo -u proteinhub .venv/bin/python -m compileall -q proteinhub tests main.py
sudo systemctl restart proteinhub
curl http://127.0.0.1:8080/api/health
```

生产部署后，数据库结构变更要更谨慎：先在 staging 数据库跑一遍，再部署生产。
