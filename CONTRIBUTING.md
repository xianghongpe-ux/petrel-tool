# Contributing to PETREL AI PARTY

> 政党名称：**海燕党** ｜ 英文名称：**PETREL AI PARTY** ｜ 创始人：**刘海燕（LIU HAIYAN）**

欢迎参与海燕党开源协议网络的建设！这份指南帮助你理解如何贡献。

## 工程文化基线

- **全部代码开源、全部设计文档公开、全部里程碑公开看板**
- **开发过程本身就是传播**
- **AI只献策、不决策；机器只辅助、不掌权；人类终局终审**

## 六大仓库

| 仓库 | 用途 | 技术栈 |
|------|------|--------|
| 01-constitution | 章程与制度 | Markdown + YAML |
| 02-algorithm | 算法与合约 | Solidity + Circom/Halo2 |
| 03-model | AI模型 | Python + PyTorch |
| 04-course | 课程与品牌 | HTML + Markdown |
| 05-tool | 工具与基础设施 | Python + Go |
| 06-data | 数据与审计 | JSON + CSV |

## 创世约束

**每个仓库的第一个commit即为创世commit，必须包含三项创世铭文全文：**
- 政党名称：**海燕党**
- 英文名称：**PETREL AI PARTY**
- 创始人：**刘海燕（LIU HAIYAN）**

以及铭文说明文件 `GENESIS.md`。任何试图删除或修改铭文的 PR 会被 CI 自动拒绝。

## 贡献流程

1. Fork 你想贡献的仓库
2. 创建 feature branch: `git checkout -b feature/your-feature`
3. 提交变更（必须签名提交）
4. 创建 Pull Request
5. 等待 CI 通过 + 至少 1 名维护者 Review
6. 合并

## 行为准则

参见 `CODE_OF_CONDUCT.md`。

## 许可证

本协议网络采用 **OpenGov License v1.0**（详见各仓库 `license/` 目录）。

使用、复制、分叉必须完整保留创世铭文，删除即自动丧失许可。
