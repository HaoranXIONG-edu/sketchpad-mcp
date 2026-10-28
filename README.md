# 几何画板 MCP（Sketchpad MCP）

通过 MCP 让 AI 客户端操作 Windows 中文版几何画板 5.06，创建原生可编辑几何对象、函数与标注。当前版本：v1.0。

## 功能

- 窗口观察、原生工具选择、几何构造、对话框输入和新文件保存。
- 实时发现已加载的自定义工具；解析本机工具箱脚本。
- 36 类手册操作指导、8 组带验证状态的工作配方。
- 已知操作批处理、原生分式模板、有限坐标系及有界函数操作。

## 安装和连接

需要 Windows、Python 3.11+，以及自行安装的中文版几何画板 5.06。

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
```

参考 `mcp-config.example.json` 或 `workbuddy-mcp.example.json`，将 Python、server.py 和几何画板程序路径改为本机绝对路径，再加入客户端配置。保留客户端已有服务。服务器通过 stdio 通信。

手动打开几何画板，保持桌面解锁，并确保客户端与几何画板权限一致。先调用 `sketchpad_observe` 检查窗口，再在新文档内操作。

## 使用原则与限制

先查询 `sketchpad_get_function_guide(query="要完成的操作", limit=1)`，按照前置条件和验证范围选择操作；规则指导不等于自动执行成功。

工具箱来自用户本机安装目录，不随项目分发。发现工具不代表已验证全部工具。截图会返回给 AI 客户端，使用前请留意画面中的个人信息。

部分配方经过本机保存、重开及拖动验证；标注跟随、子模式切换、参数滑块、原生四栏合页和部分边界情况仍有限制。四图完整制作耗时尚未重新测量，不能用单项测速代表整体提速。

详见 [手册流程索引](手册流程索引.md)、[使用规则缺口审计](使用规则缺口审计.md) 和 [开发历史与验证记录](CHANGELOG-and-history.md)。历史记录提及的本机辅助材料不包含在此仓库中；历史版本说明以对应版本为准。

## 开发测试

```powershell
.venv/Scripts/python.exe -m pip install pytest
.venv/Scripts/python.exe -m pytest tests -q
```

自动测试主要使用模拟窗口，不能替代实际桌面制图验证。

## 分发范围

本仓库仅包含 MCP 源码、测试及整理的操作指导，不包含几何画板安装程序、工具箱本体、教程 PDF、个人绘图、截图、运行环境或账号凭据。
