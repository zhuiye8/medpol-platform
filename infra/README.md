# Infra 使用说明

本目录维护本地开发所需的基础设施脚本。

## docker-compose

启动 Redis + PostgreSQL：

```bash
make infra-up
```

关闭服务：

```bash
make infra-down
```

默认账号：
- PostgreSQL：`postgresql://medpol:medpol@localhost:5432/medpol`
- Redis：`redis://localhost:6379/0`

## 后续计划
- 添加 Playwright 浏览器镜像，供需要无头浏览器的爬虫使用
- 引入 Celery Flower / Grafana 监控容器
- 根据部署环境扩展为 Helm chart
