# Backend Architecture (DDD)

## 分层

Router → Service → Repository → Model

---

## 规则

- Router：仅处理请求/响应
- Service：业务逻辑
- Repository：数据库操作

---

## 禁止

- Router调用Repository ❌
- Service写SQL ❌

---

## 模块结构

每个模块：

- models.py
- schema.py
- repository.py
- service.py
- router.py