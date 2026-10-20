# EvalScope 测试 VM 部署记录

- 测试 VM：10.2.23.3，Debian 12，16 vCPU，约 3.3 GiB 内存。
- 系统已完成 apt 索引和软件包升级；升级后 dpkg 审计无异常、无剩余可升级包。
- 已重启并确认运行内核 6.1.0-53-amd64，Docker 更新至 29.9.0。
- EvalScope 1.13.0，含 service 扩展，当前通过 Docker Compose 运行；未安装本地模型推理用的 GPU 环境。
- 首次部署因模板代理 magic.local 无法解析而使用虚拟环境备用方案。用户恢复代理并提供 10.2.210.3 后，已将 Docker 代理主机改为该 IP（端口 7897），构建镜像成功并切换到容器。
- Dockerfile 使用中科大 PyPI 镜像安装依赖；镜像 local/evalscope:1.13.0-cpu，容器 evalscope-evalscope-1。
- 网页：http://10.2.23.3:9000
- Docker 启用开机启动，容器重启策略 unless-stopped；旧 evalscope.service 已停止并禁用，虚拟环境保留作为回退。
- 容器内版本和 pip check 均通过；切换后网页及健康接口 HTTP 200，容器到 Strata 健康接口 HTTP 200。
- 从该 VM 到 http://10.2.21.4:8080/health 及 /v1/models 已验证可访问。
- 当前 Strata 模型仍为 swift-1.5-abliterated-iq3_s-q8ple，已加载；GPU 服务器配置未变更。
- 仅验证安装和连通性，没有提交模型生成或评测任务，也未下载评测数据集。

远程路径：

| 路径 | 用途 |
|---|---|
| `/opt/evalscope/README.md` | 使用说明 |
| `/opt/evalscope/configs/strata-connection.json` | API 连接参数；并发参考值 2 |
| `/opt/evalscope/requirements.docker.lock.txt` | 容器依赖版本；requirements.lock.txt 是旧虚拟环境版本 |
| `/opt/evalscope/outputs/` | 后续评测结果 |
| `/opt/evalscope/cache/` | 后续数据集缓存 |
| `/opt/evalscope/logs/` | 更新、安装和重启前后检查记录 |
| `/opt/evalscope/compose.yaml` | 当前容器服务配置 |
| `/etc/systemd/system/evalscope.service` | 停用的备用服务配置 |

命令：

```bash
cd /opt/evalscope
docker compose ps
docker compose exec evalscope evalscope --version
docker compose logs --tail 100
```

Dockerfile 与 compose.yaml 当前已启用。代理原配置备份在 `/opt/evalscope/backups/docker-proxy-20261014-171810/`；验证记录在 `/opt/evalscope/logs/docker-deployment-check.json`。下一步确定数据集、样本集、思考模式和输出预算后再开始正式评测。
