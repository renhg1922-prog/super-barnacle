# Desktop Floating Window

这是面向最终用户的便携发布包。

## 安装

1. 解压整个发布包到任意目录
2. 运行 `install.ps1`
3. 桌面会生成 `DesktopFloatingWindow.lnk`

安装脚本会自动把程序复制到 `%LOCALAPPDATA%\DesktopFloatingWindow`，所以桌面上不需要放任何程序文件夹。

## 卸载

运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\uninstall.ps1
```

## 说明

- 配置文件和运行报告会写在 EXE 安装目录中
- 桌面快捷方式只是入口，不保存程序数据
- 如果需要覆盖旧版本，请重新运行 `install.ps1 -Force`
