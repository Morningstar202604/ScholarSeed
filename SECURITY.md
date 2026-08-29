---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: 98adaa6f98486df4666888a6691e7607_eb8087db9b9111f1a98a525400f8a581
    ReservedCode1: Y0GfB1YNnTf+XzulMXOvHEu52nI2JPO6FHadZC9RGE0eniPtXE+qjaRs0vn+Mbv4M0EU4isO075Ge4HbvylQfdsVbnCKzfK+tmrLlJhJ9UlgbqzQ4skzMmBwu9KREbQbdODb626jKmHH4A7AkpZMHCazgM7VVzXz4gX1/R6cUEoJLSqh7cIGMoyYcCE=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: 98adaa6f98486df4666888a6691e7607_eb8087db9b9111f1a98a525400f8a581
    ReservedCode2: Y0GfB1YNnTf+XzulMXOvHEu52nI2JPO6FHadZC9RGE0eniPtXE+qjaRs0vn+Mbv4M0EU4isO075Ge4HbvylQfdsVbnCKzfK+tmrLlJhJ9UlgbqzQ4skzMmBwu9KREbQbdODb626jKmHH4A7AkpZMHCazgM7VVzXz4gX1/R6cUEoJLSqh7cIGMoyYcCE=
---

# 安全策略

## 报告漏洞

如果你发现安全漏洞（而非普通 bug），请**不要**在公开 Issue 中披露。请通过以下方式私密报告：

- 在 GitHub 仓库的 **Security → Report a vulnerability** 提交私密报告（优先）；
- 或向维护者邮箱发送邮件（在仓库主页查看）。

## 漏洞处置承诺

- 收到报告后 72 小时内确认；
- 确认后尽快发布修复版本，并在 CHANGELOG 中注明（涉及安全风险时先发修复再公开细节）；
- 漏洞修复前不公开利用细节。

## 已知安全边界

本插件基于 Agent Plugins 1.0 规范构建，该规范 v1.0.0 **不定义**权限模型、沙箱、签名与来源验证。使用方须知：

- 插件安装即被客户端隐式信任，安装来源不明的插件前请人工审查内容。
- `mcp.json` 声明的 MCP Server 可达任意端点，加载前请确认其行为。
- 本插件本身**不含任何凭据**；真实投稿/发布所需的账号与 API 密钥由使用方自行保管，禁止把密钥写入插件文件或提交进仓库。
*（内容由AI生成，仅供参考）*
