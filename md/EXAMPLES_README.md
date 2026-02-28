# 示例文件（科研写作场景）

科研写作「加载示例」会读取本目录下的文件进行案例展示。

## 所需文件

| 文件 | 说明 |
|------|------|
| `SUMMARY.md` | Nature 量子计算综述项目说明（已有） |
| `quantum_summary_paper.pdf` | 输出论文 PDF（7 页） |
| `structured.json` | 参考源论文结构化提取（已有） |
| `figures/` | 论文截图（可选，供 structured.json 引用） |

## 获取 quantum_summary_paper.pdf

从 `writing_outputs` 复制：

```powershell
Copy-Item "..\..\writing_outputs\20260228_002318_nature_quantum_three_papers_summary\final\quantum_summary_paper.pdf" .
```

或 Linux/Mac：

```bash
cp ../../writing_outputs/20260228_002318_nature_quantum_three_papers_summary/final/quantum_summary_paper.pdf .
```
