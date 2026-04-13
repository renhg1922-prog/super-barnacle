# Desktop Floating Window

一个可打包为 Windows 便携 EXE 的桌面浮窗项目。

最终交付方式已经整理为：

- 程序文件放在实际安装目录中，例如 `%LOCALAPPDATA%\DesktopFloatingWindow`
- 桌面只保留 `DesktopFloatingWindow.lnk` 启动快捷方式
- 配置和运行时文件始终写在 EXE 所在目录，不写到桌面

## 功能

- 提供一个可拖动、可调整大小的桌面浮窗
- 显示时钟、标题、状态按钮和便签内容
- 保存窗口位置、大小、透明度、置顶状态和文本内容
- 支持托盘、开机自启和便携目录迁移

## 依赖

- Python 3.11+
- `pywin32`
- `PyInstaller`

安装依赖：

```powershell
python -m pip install -r .\requirements.txt
```

## 从源码运行

```powershell
python .\app.py
```

## 构建 EXE

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

构建输出：

```text
dist\DesktopFloatingWindow\DesktopFloatingWindow.exe
```

`build.ps1` 会自动完成三段验证：

1. 直接从构建输出目录运行
2. 复制到新的安装目录后再次运行
3. 通过桌面快捷方式启动被复制后的 EXE，并确认配置文件仍然写在 EXE 目录

## 安装到本机

构建完成后执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

默认行为：

- 将 `dist\DesktopFloatingWindow` 复制到 `%LOCALAPPDATA%\DesktopFloatingWindow`
- 在桌面创建 `DesktopFloatingWindow.lnk`
- 不把任何程序文件夹放到桌靊

常用参数：

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Force
powershell -ExecutionPolicy Bypass -File .\install.ps1 -SourceDir C:\path\to\DesktopFloatingWindow
powershell -ExecutionPolicy Bypass -File .\install.ps1 -InstallDir D:\Apps\DesktopFloatingWindow -Force
```

卸载：

```powershell
powershell -ExecutionPolicy Bypass -File .\uninstall.ps1
```

## 生成可分发发布包

```powershell
powershell -ExecutionPolicy Bypass -File .\package_release.ps1
```

输出内容：

- `release\DesktopFloatingWindow_portable\`
- `release\DesktopFloatingWindow_portable.zip`

发布包内包含：

- `DesktopFloatingWindow\` 可运行目录
- `install.ps1`
- `uninstall.ps1`
- `README.md` 最终用户说明

## 自动发版

仓库内置了 GitHub Actions 自动发版流程：

1. 先把代码推到 `main`
2. 创建并推送版本标签，例如 `v1.0.0`
3. GitHub Actions 会在 Windows 环境自动构建
4. 自动生成 GitHub Release，并附带 `DesktopFloatingWindow_portable.zip`

本地也可以继续手动执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\package_release.ps1
```

## GitHub 发布建议

推荐把 GitHub 仓库和最终给用户的发布包分开处理：

1. 仓库只提交源码、脚本和文档
2. 不提交 `dist/`、`build/`、`relocation_check/` 等本地产物
3. 每次发版前运行 `build.ps1`
4. 运行 `package_release.ps1` 生成可上传的发布包，或直接推送版本 tag 触发自动发版
5. GitHub Release 中的最终资产是 `DesktopFloatingWindow_portable.zip`

最终用户解压后只砞要运行 `install.ps1`，桌面上只会出现快捷方式。

## 参考项目

- FloatTrans: https://github.com/nickwx97/FloatTrans
- Zebar: https://github.com/glzr-io/zebar
- WindowTop: https://github.com/WindowTop/WindowTop-App
- OnTop: https://github.com/NeonOrbit/OnTop
