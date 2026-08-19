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
sudo chmod 600 /etc/proteinhub.env
sudo chown root:root /etc/proteinhub.env
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
sudo chmod 600 /etc/proteinhub.env
sudo chown root:root /etc/proteinhub.env
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

保存后继续第 4-7 步：外部工具检查、安装 systemd service、健康检查、
配置 Caddy HTTPS、设置备份。

## 4. AKTA 和反向翻译外部工具

不要把 `.legacy/` 里的本地虚拟环境直接提交到主仓库。推荐在服务器上单独放置：

```text
/opt/proteinhub-tools/
  akta/
    bin/python
    akta_hap.py
  domesticator/
    bin/python
    domesticator.py
    database/
```

然后在 `/etc/proteinhub.env` 中配置：

```bash
PROTEINHUB_AKTA_HAP_PYTHON=/opt/proteinhub-tools/akta/bin/python
PROTEINHUB_AKTA_HAP_SCRIPT=/opt/proteinhub-tools/akta/akta_hap.py

PROTEINHUB_LEGACY_DOMESTICATOR_PYTHON=/opt/proteinhub-tools/domesticator/bin/python
PROTEINHUB_LEGACY_DOMESTICATOR_SCRIPT=/opt/proteinhub-tools/domesticator/domesticator.py
PROTEINHUB_LEGACY_DOMESTICATOR_DATABASE=/opt/proteinhub-tools/domesticator/database
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

## 6. HTTPS 反向代理

复制 Caddy 模板：

```bash
sudo cp /opt/proteinhub/deploy/Caddyfile.example /etc/caddy/Caddyfile
sudo editor /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

把 `your-domain.example.com` 替换成真实域名。Caddy 会自动申请和续期 HTTPS
证书。

## 7. 备份和恢复

手动备份：

```bash
sudo -u proteinhub PROTEINHUB_ENV_FILE=/etc/proteinhub.env /opt/proteinhub/scripts/backup-postgres.sh
```

建议加 cron：

```bash
sudo crontab -u proteinhub -e
```

每天凌晨备份：

```cron
15 2 * * * PROTEINHUB_ENV_FILE=/etc/proteinhub.env /opt/proteinhub/scripts/backup-postgres.sh >> /var/backups/proteinhub/backup.log 2>&1
```

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
