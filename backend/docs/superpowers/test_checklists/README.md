# Test Checklists

这个目录用于沉淀 Agent / MCP / RAG 等模块的测试清单。

设计目标：

- 与 `specs/` 分离，避免把测试执行清单和设计文档混在一起
- 支持持续追加“当前已验证项 + 待补测项 + 结果记录”
- 让后续联调、回归、上线前检查都能复用同一份 checklist

建议约定：

- 一类能力一份 checklist
- 文件名优先使用 `YYYY-MM-DD-<topic>-test-checklist.md`
- 清单里明确区分：
  - `已通过`
  - `待测试`
  - `失败/阻塞`
  - `备注`
