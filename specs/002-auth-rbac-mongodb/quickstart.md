# Quickstart: 用户角色权限系统 (RBAC)

## 前置条件

- Python 3.11+
- MongoDB 已启动

## 安装依赖

```bash
pip install fastapi uvicorn pymongo python-jose[cryptography] passlib[bcrypt] pydantic
```

## 启动服务

```bash
cd apps/api
uvicorn main:app --reload
```

## 测试场景

### 1. 创建权限

```bash
curl -X POST http://localhost:8000/permissions \
  -H "Content-Type: application/json" \
  -d '{"name": "user:create", "resource": "user", "action": "create"}'
```

### 2. 创建角色

```bash
curl -X POST http://localhost:8000/roles \
  -H "Content-Type: application/json" \
  -d '{"name": "admin", "description": "管理员角色", "permission_ids": []}'
```

### 3. 创建用户

```bash
curl -X POST http://localhost:8000/users \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "password123", "email": "admin@example.com"}'
```

### 4. 用户登录

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "password123"}'
```

**返回**:
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer"
}
```

### 5. 使用令牌访问受保护资源

```bash
curl -X GET http://localhost:8000/users \
  -H "Authorization: Bearer eyJ..."
```

## 验证清单

| 场景 | 预期结果 | 实际结果 |
|------|----------|----------|
| 创建权限 | 返回权限对象 | ☐ |
| 创建角色 | 返回角色对象 | ☐ |
| 创建用户 | 返回用户对象 | ☐ |
| 用户登录 | 返回JWT令牌 | ☐ |
| 无效登录 | 返回401错误 | ☐ |
| 使用令牌访问 | 返回数据 | ☐ |
| 无权限访问 | 返回403错误 | ☐ |