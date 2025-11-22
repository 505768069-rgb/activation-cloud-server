# Railway 部署说明

这是激活码云端服务器，用于实时验证和管理激活码。

## 部署到 Railway

1. 访问 https://railway.app/
2. 使用 GitHub 登录
3. 创建新项目
4. 部署此仓库

## 环境变量

不需要额外配置，默认即可运行。

## 访问

部署后获取 URL：`https://your-app.railway.app`

API端点：
- `GET /api/health` - 健康检查
- `POST /api/verify` - 验证激活码
- `POST /api/activate` - 标记激活码为已使用
- `POST /api/admin/generate` - 生成激活码
- `GET /api/admin/list` - 查看激活码列表
- `GET /api/admin/statistics` - 查看统计信息

## 数据库

使用 JSON 文件存储：`cloud_activation_db.json`

Railway 会自动持久化此文件。

## 安全提示

1. 修改 `SECRET_KEY` 为随机字符串
2. 在生产环境添加管理员认证
3. 定期备份数据库文件

---

© 2025 激活码云端服务
