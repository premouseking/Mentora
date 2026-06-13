# Mentora 桌面图标设计

## 目标

将 `pnpm dev:desktop` 当前显示的 Electron 默认图标替换为 Mentora 自有图标，并让
Windows 开发态窗口、任务栏和安装包保持一致。

## 已选方案

采用预览中的 B 版“任务栏强化版”：

- 保留 Mentora 品牌标识的 `M` 外轮廓和中轴书签；
- 删除标题栏版本中的底部书页短线；
- 加粗主轮廓和书签，提升 16×16 与 32×32 像素下的识别度；
- 使用现有品牌深绿 `#123f37` 作为圆角方形底色；
- 使用白色单色线条，不使用渐变、阴影或文字。

## 资源格式

以一个 1024×1024 的透明背景主 PNG 作为视觉源，图形本身占满画布并保留适量安全
边距。由主 PNG 生成：

- `apps/desktop/build/icon.png`：供 electron-builder 使用，至少 256×256；
- `apps/desktop/build/icon.ico`：包含 Windows 常用多尺寸图层；
- `apps/desktop/build/icon-dev.png`：供 macOS/Linux 开发态 `BrowserWindow` 使用；
- `apps/desktop/build/icon.ico`：Windows 开发态与打包共用（多尺寸 ICO）。

生成后的位图必须保持相同轮廓，不为不同格式单独调整构图。

## Electron 接入

- 在桌面端配置模块中集中解析图标路径；
- 开发态：Windows 从 `build/icon.ico` 读取，并调用 `app.setAppUserModelId("com.mentora.desktop")`（与 `electron-builder.yml` 的 `appId` 一致），避免任务栏仍显示 Electron 默认图标；macOS/Linux 从 `build/icon-dev.png` 读取；
- 打包态由 electron-builder 将 `build/icon.ico` 写入可执行文件；
- `BrowserWindow` 通过 `nativeImage.createFromPath` 显式设置 `icon`；路径不可读时写 warn 日志；
- `electron-builder.yml` 显式声明 Windows 图标，避免依赖隐式文件名查找。

## 验收标准

1. 执行 `pnpm dev:desktop` 后，Windows 任务栏显示 Mentora B 版图标；
2. 图标在 16×16、32×32 和 64×64 像素下轮廓清晰，无细线糊成一团；
3. `pnpm build:desktop`、桌面端类型检查和测试通过；
4. `pnpm --dir apps/desktop pack:dir` 生成的 Windows 应用使用同一图标；
5. 不修改应用内现有的完整 `M + 书签 + 书页线` 标识。
