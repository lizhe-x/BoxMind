# iOS 发布规划（原生 SwiftUI）

> 2026-10-20 重新制定。取代 2026-10-09 的 Capacitor 壳方案。
> 决定:**iOS 用原生 SwiftUI 重写客户端,后端原样复用,Web 前端冻结不再维护。**

## 1. 目标与边界

- 交付物:App Store 上架的 iPhone 应用 BoxMind,功能对齐现在 Web 版能跑通的闭环
  (登录 → 语音/文字/拍照/扫码录入 → 自然语言提问 → agent 操作 + 确认 + 撤销 → 箱子管理 → 设置/导出)。
- 后端 FastAPI 不改协议,只补上架必需的几个接口(见 §4)。
- Web 前端 `frontend/` 冻结:不再加功能、不再修 bug,但保留在仓库里当"行为规格"和测试用例来源。
  后端继续托管 `frontend/dist` 不影响 iOS。
- 第一版只做 iPhone(竖屏),不做 iPad、不做 Widget、不做推送、不做内购。

### 为什么不用壳(Capacitor / WKWebView)

- 审核风险:Guideline 4.2(最低功能)对"网页套壳"很敏感,BoxMind 的界面就是一屏一个大按钮,被判成网站的概率不低。
- 体验:按住说话、相机取景、扫码、触感反馈这几个核心交互,原生才顺手;Web Speech 在 iOS WKWebView 里根本不可用。
- 代价可控:前端业务逻辑总共约 4500 行 TS,其中可直接"翻译"的是 `store.ts`(状态机)、`api.ts`(API 客户端)、`i18n.ts`(文案表),界面 8 屏 + 1 个录入浮层。

## 2. 现状盘点(可复用的东西)

| 资产 | 位置 | iOS 怎么用 |
|---|---|---|
| 后端 API(约 25 个端点,Bearer JWT,SSE 流式问答,multipart 上传) | `backend/app/routers/*` | 原样调用。Codable 模型按 `backend/app/schemas.py` 定义 |
| 前端状态机(录入 8 个阶段、agent 确认流、拍照/扫码流) | `frontend/src/store.ts` | 逐个 action 翻译成 Swift `@Observable` 模型的方法 |
| 前端 API 客户端 + SSE 解析 | `frontend/src/api.ts` | 翻译成 `URLSession` actor |
| 文案表 EN/ZH(约 500 行) | `frontend/src/i18n.ts` | 转成 `Localizable.xcstrings` |
| 设计规范(颜色、字体、圆角、动效 token) | `docs/design/README.md` | 转成 `Theme.swift`;Space Grotesk 字体随 app 打包(OFL 许可) |
| 高保真原型 | `docs/design/prototype/` | 对照还原界面 |
| 品牌图标 SVG | `docs/brand/` | 导出 1024×1024 App Icon 与启动页 |
| 47 条前端测试 | `frontend/tests/*.test.ts` | 一比一改写为 XCTest(见 §6) |
| 测试服务器 | Mac mini,launchd + Colima/Postgres,Tailscale `https://zhes-mac-mini.tailb3c9f2.ts.net` | 开发期直连;上架前要公网可达(见 §4) |
| 工具链 | Xcode 27.1、xcodegen 已装;付费 Apple Developer 账号 | 直接可用 |

Web 端能力 → iOS 原生替代:

| Web 端 | iOS 原生 |
|---|---|
| Web Speech 实时转写 | `SpeechAnalyzer` / `SpeechTranscriber`(iOS 26,端侧、支持中英)+ `AVAudioEngine` 同时落一份 m4a 用于保存 |
| MediaRecorder → `/api/transcribe` 兜底 | `AVAudioRecorder` 录 m4a → 同一接口兜底;再兜底手动输入 |
| ZXing 扫码 | `VisionKit.DataScannerViewController`(QR + 一维码) |
| getUserMedia 拍照 | `AVCaptureSession` 自定义取景(按原型样式)或 `UIImagePickerController` 起步 |
| TTS 音频播放 / 语音备注回放 | `AVAudioPlayer`;可选 `AVSpeechSynthesizer` 做零成本朗读 |
| navigator.geolocation | `CoreLocation`(仅使用期间) |
| localStorage token | Keychain(token)+ UserDefaults(语言、偏好) |
| 下载导出 URL | 下载到临时文件后 `ShareLink` / `fileExporter` |
| CSS 动效(淡入、波形、打字机) | SwiftUI 动画 + `TimelineView` |
| 触感 | `UIImpactFeedbackGenerator` / `.sensoryFeedback` |

## 3. 技术方案

```
ios/
├── project.yml              # xcodegen;.xcodeproj 不入库
├── BoxMind/                 # App target(SwiftUI)
│   ├── App/                 # 入口、路由(Screen 枚举 ↔ store.screen)
│   ├── Screens/             # Onboarding Login Home Ask Boxes BoxDetail Settings Camera Scan
│   ├── Entry/               # 录入浮层(EntryOverlay 的 8 阶段状态机)
│   ├── Theme/               # 设计 token、字体、组件(胶囊按钮、牛皮纸箱卡、确认卡)
│   ├── Platform/            # 语音、相机、扫码、定位、触感、Keychain 的封装
│   └── Resources/           # Localizable.xcstrings、字体、Assets、PrivacyInfo.xcprivacy
├── BoxMindKit/              # Swift Package,纯逻辑,无 UI,可 `swift test`
│   ├── Sources/BoxMindKit/  # Models(Codable)、APIClient、SSEParser、AppModel(状态机)
│   └── Tests/               # 对应 47 条前端测试
└── fastlane/ 或 scripts/    # 后期:截图、TestFlight 上传
```

关键取舍:

- **最低 iOS 26,Xcode 27 构建。** 只支持上一代及以上系统,换来 `SpeechAnalyzer`、`@Observable`、新版 `ShareLink` 等直接可用,不写兼容分支。
- **逻辑放进 Swift Package。** `BoxMindKit` 不依赖 UIKit,CI 上 `swift test` 几十秒跑完,不用起模拟器。网络层用 `URLProtocol` 打桩,复刻前端"脚本化 API"的测法。
- **状态机忠实翻译,不重新设计。** `store.ts` 里每个 action 对应 `AppModel` 一个方法,`EntryPhase` / `Screen` 枚举名字沿用,方便对照前端测试逐条验收。
- **一个 API 基地址,编译期注入。** Debug 指向 Tailscale 地址,Release 指向正式域名;不做运行时切换(设置页不暴露)。
- **xcodegen 生成工程**,`project.yml` 入库,避免 `.xcodeproj` 合并冲突。

## 4. 后端 / 基础设施需要补的

上架硬性要求,和 iOS 开发并行做:

1. **账号删除接口** `DELETE /api/me`:级联删箱子、物品、媒体文件、撤销快照、验证码记录。App Store 5.1.1(v) 要求凡有注册必有应用内删除。设置页加入口 + 二次确认。
2. **审核专用账号**:新增 `BOXMIND_REVIEW_EMAIL` / `BOXMIND_REVIEW_CODE` 配置,该邮箱固定验证码、不发邮件。审核员在 App Review Notes 里拿到这组凭据直接登录(Guideline 2.1 要求演示账号)。
3. **配置 SMTP**:现在没配 SMTP 等于开发模式,验证码直接从接口返回,不能上线。
4. **音频默认格式**:iOS 上传 `audio/mp4`(m4a)。`media.py` 已识别 `audio/mp4 → .m4a`;需确认网关 ASR 接受 m4a(`asr.py` 透传 content-type,预期没问题,M2 第一天实测)。
5. **公网 HTTPS**:
   - TestFlight 阶段:`tailscale funnel 8001` 打开公网(前提是 3 已完成),用 `*.ts.net` 域名即可,ATS 认它的证书。
   - 正式上架:建议换一个自己的域名(即使仍然反代到这台 Mac mini),否则以后迁移服务器要发版。审核期间后端必须 7×24 在线、LLM 网关 key 有余额。
6. **CORS 不再重要**:原生 App 不带 Origin。`main.py` 里的 `capacitor://` 分支可留可删。
7. 顺手把这次工作区里 `embedding_cache_dir` 的改动(`config.py` / `embeddings.py` / `.env.example`)提交掉。

## 5. 里程碑

每个里程碑结束时都能在真机上装一个可用的构建;验收标准写在括号里。

| 里程碑 | 内容 | 预估 |
|---|---|---|
| **M0 准备** | §4 的 1–4;`ios/` 骨架(xcodegen、两个 target、空 App 能在真机跑);App Icon / 启动页;Bundle ID、签名、App Store Connect 建 App | 1–2 天 |
| **M1 读通** | `BoxMindKit`:Codable 模型、`APIClient`(Bearer、401 登出、错误码)、Keychain;登录页(邮箱验证码、语言切换)、箱子列表、箱子详情(只读)、设置页(语言/登出)。(真机登录测试服务器,看到自己的箱子) | 2–3 天 |
| **M2 核心闭环** | Home 大按钮 + 录入浮层状态机(文字 → interpret → 确认卡 / 选箱 / 编辑 → ingest);按住说话(端侧转写 + 落 m4a + 服务端 ASR 兜底 + 手动输入兜底);Ask 页 SSE 流式回答 + 箱卡;agent 消息 / 确认卡 / 执行 / 撤销;TTS 朗读。(复刻 README 里那条"move + merge + undo"的完整链路) | 4–5 天 |
| **M3 采集** | 拍照取景 → `/api/recognize` → 置信度勾选 → 入库并设封面;扫码(QR/条码)→ `/api/boxes/resolve` → 未知码走手写编号兜底 → "在此录入"锁定目标箱;箱子详情的照片、语音备注回放、封面切换、物品增删改 | 3–4 天 |
| **M4 收尾** | Onboarding;GPS 开关 + 定位;导出 JSON/CSV 分享;删除账号;触感;空态/错误态;深色主题 token 全面对齐原型;中英文案全量;`PrivacyInfo.xcprivacy`、Info.plist 权限文案 | 2–3 天 |
| **M5 发布** | TestFlight 内测 → 外测;隐私政策页(GitHub Pages);App Store 元数据、截图(6.9" 一组即可)、年龄分级、App Privacy 标签;审核备注(演示账号 + AI 功能说明);提交。预留一次被拒返工 | 3–5 天 + 审核等待 |

合计约 3–4 周(单人 + AI 协作,按每天几小时估)。M2 是风险最大的一段:端侧语音识别和 SSE 两件事优先实测。

## 6. 测试

- `BoxMindKit` 的 XCTest 一比一覆盖 `frontend/tests/api.test.ts` 与 `store.test.ts` 的 47 条:
  Bearer/401/错误码、multipart、SSE 跨 chunk 重组、录入状态机各分支、agent 确认/执行/取消、拍照勾选、扫码兜底、i18n 辅助函数。
- 网络用 `URLProtocol` 子类打桩,记录请求、回放响应;和前端 mock `api` 的思路一致。
- 后端 pytest 补:删除账号级联、审核账号固定码、m4a 上传。
- UI 层只做一条 XCUITest 冒烟(登录 → 文字录入 → 确认 → 列表出现),其余靠真机手测。
- CI:现有 workflow 加一个 `macos-latest` job 跑 `swift test`(只测 Kit,不起模拟器,便宜)。

## 7. 上架检查清单

- [x] Guideline 5.1.1(v):应用内删除账号(§4.1)
- [x] Guideline 2.1:演示账号写入 Review Notes(§4.2);后端审核期间在线;LLM key 有余额
- [x] 隐私政策 URL(需写明:照片、语音、文字会发送给第三方模型网关处理;邮箱用于登录;位置可选)
- [x] App Privacy 标签:邮箱、照片/视频、音频、位置(可选)、用户内容;不做追踪
- [x] `PrivacyInfo.xcprivacy`:UserDefaults 等 Required Reason API 声明
- [x] Info.plist 权限文案:相机、麦克风、语音识别、使用期间定位(中英双语)
- [x] 出口合规:只用 HTTPS → `ITSAppUsesNonExemptEncryption = NO`
- [ ] 不接 Google/微信等第三方登录(否则触发 4.8 必须加 Sign in with Apple);邮箱验证码登录本身不触发
- [ ] 不展示"额度 / 购买"相关 UI(现在后端 `credit_balance` 只记账不限制;一旦出现付费必须走 IAP 3.1.1)
- [x] 不支持 iPad 时在 target 里只勾 iPhone,免得要 iPad 截图
- [ ] ATS 不加例外;后端证书有效

## 8. 待你拍板的事(不阻塞开工)

1. **正式域名**:上架用 `*.ts.net` Funnel 地址,还是买个域名?(建议买域名,M5 之前定即可。)
2. **SMTP 用什么**:自己邮箱的 SMTP、还是 Resend/Postmark 之类的服务?(审核账号用固定码,SMTP 只影响真实用户。)
3. **TTS 走网关还是端侧** `AVSpeechSynthesizer`:端侧零成本、离线可用,音色差一点;网关音色好、要花钱。建议 v1 先端侧,设置里不暴露选项。(M2 已按端侧实现;要换网关只需改 `Speaker`。)
4. **App Store 名称 / 副标题 / 分类**:建议分类 Productivity,名称 "BoxMind",副标题沿用 "Say it, snap it, find it" 一类。

## 9. 进度

### 2026-10-20 · M0 大部分完成

- 本文件建立;Capacitor 方案作废,相关依赖撤回。
- 后端:`DELETE /api/me`(级联删数据与文件)、审核账号 `BOXMIND_REVIEW_EMAIL/CODE`、CORS 去掉 capacitor origin;pytest 170 通过。
- `ios/`:xcodegen 工程(`project.yml`)、`BoxMindKit` 包(Codable 模型、`APIClient`、SSE 解析、`TokenStore`)+ 9 条 XCTest;
  App 壳(Keychain token、`AppEnvironment`、占位首页)在模拟器运行并连通测试服务器;真机签名构建通过(Team `GZ4LT9W9H9`,自动签名)。
- App Icon 由 `docs/brand/render.html` 经 headless Chrome 渲染为 1024 px 不透明 PNG。
- CI 新增 `ios-kit` job(macOS runner 上 `swift test`)。

**M0 剩余(需要你的账号或凭据):** SMTP 配置;`backend/.env` 填审核账号;App Store Connect 建 App(Bundle ID `me.boxmind.app`);
Tailscale Funnel 开公网(等 SMTP 配好之后)。

### 2026-10-20 · M1 完成

- `BoxMindKit`:`Lang`/`L10n`(199 条文案由 `ios/scripts/gen_l10n.py` 从 `i18n.ts` 生成)、`Display` 辅助(时间分桶、
  距离、徽章字号、去 markdown)、`BoxMindAPI` 协议 + `PreferenceStore` + `LocationProvider` 端口、`AppModel`
  (`store.ts` 的会话/导航/语言/toast 部分,action 同名)。XCTest 27 条。
- App:主题 token、Space Grotesk 字体、通用组件(牛皮纸徽章、渐变按钮、Chip、TabBar、Toast)、登录页、引导页、
  首页静态版、箱子列表、箱子详情(只读 + 语音备注播放)、设置页(语言、GPS、导出分享、退出、删除账号)。
- `BoxMindUITests/SmokeTests`:模拟器上走通 登录(dev 验证码)→ 引导 → 首页 → 列表 → 详情 → 设置,
  `TEST_RUNNER_BM_SHOT_DIR=<dir> xcodebuild test …` 可顺带导出截图。
- 测试服务器上有演示账号 `ios-test@example.com`(dev 模式任意验证码流程),已塞 4 个箱子。

**开发命令:**

```bash
cd ios && xcodegen generate            # 生成 BoxMind.xcodeproj(不入库)
cd ios/BoxMindKit && swift test        # 逻辑层单元测试,不需要模拟器
python3 ios/scripts/gen_l10n.py        # i18n.ts 改动后重新生成 Swift 文案表
cd ios && xcodebuild test -project BoxMind.xcodeproj -scheme BoxMind \
  -destination 'platform=iOS Simulator,name=iPhone 17'   # UI 测试(SmokeTests 需本机后端 dev 模式;EntryFlowTests 用内置 mock)
open ios/BoxMind.xcodeproj             # 在 Xcode 里选真机运行
```

### 2026-10-20 · M2 完成

- `BoxMindKit`:`BoxMindAPI` 协议补齐 interpret / ingest / uploadAudio(multipart,`audio/mp4`)/ transcribe / askStream
  (SSE,按原始 `\n` 字节切分——`AsyncBytes.lines` 会吞掉分隔块的空行)/ agent / agentExecute / tts;
  `AppModel` 移植 `store.ts` 的录入状态机(`EntryPhase`:recording → parsing → confirm / askbox / edit → done,
  `targetBox` 锁定、`pendingAudio` 入库后 best-effort 上传)、问答(`ask` 流式拼接 delta、`done` 挂箱卡)、
  agent(`agentSend` 带历史与 GPS、确认卡 `agentConfirm` 逐条执行 + 刷新、`agentCancel`)、`chatSend` 路由。
  XCTest 57 条(对应 `store.test.ts` 的 submitText / confirmEntry / agent / voice 分组 + SSE、multipart 用例)。
- App:
  - `Platform/VoiceRecorder`:`AVAudioEngine` 单路采集 → 同时写 m4a(AAC 48 kbps)和喂 `SpeechAnalyzer` +
    `SpeechTranscriber`(iOS 26 端侧,volatile 结果实时上屏);端侧没有文本时把 m4a 发 `/api/transcribe` 兜底;
    模型按当前语言在后台预下载(`AssetInventory`)。模拟器上直接返回"不可用"(这台 Mac mini 无麦克风,
    `AVAudioEngine.inputNode` 会在 CoreAudio 里 abort)。
  - `Platform/Speaker`:朗读走端侧 `AVSpeechSynthesizer`(§8.3 先按端侧实现,网关 `/api/tts` 客户端已留着)。
  - `Platform/HoldToTalk`:按住说话手势(零距离 DragGesture),首页大按钮和问答页麦克风共用。
  - `Platform/MockAPI`(仅 Debug,`-bm-mock` 启动参数):内存后端,规则版 interpret、逐词流式回答、
    delete/undo agent。UI 测试和没有网关时的界面开发都用它。
  - 首页完整版(教学卡 / 最近入库卡、目标箱芯片、按住说话、输入行、示例 chip)、`Entry/EntryOverlay`
    六个阶段、`Screens/AskView`(流式光标、箱卡、确认卡、朗读、chip、输入 + 麦克风)。
- `BoxMindUITests/EntryFlowTests`(mock 后端):文字录入 → 确认 → 完成 → 首页活动卡;无编号 → 选箱;
  提问 → 流式回答 + 箱卡;`delete box 4` → 确认卡 → 执行 → `undo` → 列表恢复;按住说话松手不卡死。
  `SmokeTests` 仍打真后端。两条都通过。
- 真机(iPhone 16 Pro Max)已装 M2 构建。
- 网关 key 问题的解法(同日):后端新增 `BOXMIND_LLM_PROVIDER=claude_code`(`services/llm_claude.py`),
  用这台 Mac mini 上登录了 Max 订阅的 `claude -p` 顶替网关:interpret / recognize 走 `--json-schema` 结构化
  输出,agent 的 function calling 用「系统提示里列工具 + JSON 返回 tool_calls」模拟后转成 OpenAI 形状,
  ask 走 `stream-json` 的 text_delta,拍照识别把图写进 `media/.claude-work/` 让模型用 Read 工具看。
  每次请求起一个进程,约 2.5–4 s;10 条单测(CLI 打桩)+ 真机链路(interpret / ask SSE / agent 确认 /
  recognize 经 Tailscale)都验过。测试服务器已切换;**只用于测试**,正式环境仍要网关或 API key。
  ASR / TTS 两个服务端接口在这个 provider 下仍不可用(iOS 已端侧实现,`/api/transcribe` 只是兜底)。
### 2026-10-20 · M3 完成

- `BoxMindKit`:`RecogResult`/`RecogDraft`/`ResolveResult`/`PhotoClip` 模型;`BoxMindAPI` 增加 recognize、resolveCode、
  uploadPhoto(set_cover)、setCover、add/update/deleteItem;`AppModel` 移植 store.ts 的拍照(openCamera / recognizePhoto /
  toggle / edit / add / confirmPhoto)、扫码(openScan / resolveScan / scanManual / recordToFound)和详情编辑
  (addBoxPhoto / setBoxCover / add / update / deleteBoxItem)。XCTest 57 → 76 条(拍照勾选、扫码兜底、编辑写穿、
  multipart / query / PATCH 用例)。
- App:
  - `Platform/CameraController` + `CameraPreview`:AVCaptureSession 后置取景、JPEG 拍照,竖屏旋转角固定 90°;
    `Platform/ImageResize`:CGImageSource 缩略图(最长边 1600、JPEG 0.82、EXIF 方向烤进像素),同 `image.ts`;
    模拟器没相机时 Debug 用占位图走完流程。
  - `Platform/BarcodeScanner`:VisionKit `DataScannerViewController`(QR / 条码),一次扫描只回调首个码;不支持的设备退化为静态取景框 + 手写编号。
  - `Screens/CameraView`:三分线取景、快门、"AI is looking…" 扫描线、结果底浮层(目标箱卡、勾选 / 改名 / 改数量 / 置信度 pill / 手动添加 / 入库)。
  - `Screens/ScanView`:取景框 + 扫描线、识别成功浮层(箱卡 → 详情、"在此录入"、"查看箱子"、重扫)、手写编号浮层。
  - `Screens/BoxDetailView`:物品行可改名 / 改数量(失焦提交)/ 删除,底部添加行;照片点选设封面,`PhotosPicker` 多选上传
    (无封面时首张设封面);"在此录入"锁定目标箱回首页。
  - `MockAPI` 补 recognize / resolve / photo / item 接口;`-bm-mock` 下 UI 测试仍不依赖 LLM。
- `BoxMindUITests/CameraScanTests`:拍照 → 结果 → 勾选 → 入库完成卡;扫码手写编号建 7 号箱 → "在此录入" → 文字录入直接到确认卡;
  详情页加物品 / 删物品。
- 真机(iPhone 16 Pro Max)已装 M3 构建;后端 `claude_code` provider 让 recognize 真机可测。
- 没做 / 留到 M4:相机页从相册选图(Web 版也只有实时取景);箱子改名 / 改位置(Web 详情页也没有,走 agent)。

### 2026-10-20 · M4 完成(收尾)

- 定位:`Platform/CoreLocationProvider`(`CLLocationManager`,使用期间授权,10 分钟缓存、8 秒超时);`LocationProvider`
  返回 `position / denied / unavailable`。启动时仅在 `gps_enabled` 为真才取位置且静默;设置里打开开关会立刻取位置,
  被拒绝时提示一次去系统设置允许;关掉开关即清掉 `userPos`。录入、拍照入库、agent 都带 GPS。
- 离线启动:token 还在但服务器连不上时不再踢回登录页(Web 版会),保持会话 + toast;回到前台自动重试
  (`reconnectIfNeeded`),token 失效才登出。
- 触感:按住说话按下 / 松开、快门、拍照结果勾选、扫码命中、入库完成卡。
- 文案:生成脚本支持 `ios/scripts/l10n_extra.json`(iOS 专有 3 条,中英双语),表 199 → 202 条;
  `Resources/{en,zh-Hans}.lproj/InfoPlist.strings` 让相机 / 麦克风 / 语音识别 / 定位的权限提示跟随系统语言。
- `PrivacyInfo.xcprivacy` 已在 M0 建好(邮箱、照片、音频、精确位置、用户内容;UserDefaults CA92.1),本次核对无需改。
- XCTest 76 → 83 条(离线启动、重连、定位开关、拒绝提示、设置保存失败不取位置)。
- 空态 / 错误态核对:箱子列表空态、首页教学卡、详情"箱子不存在"、问答出错气泡、拍照无结果 / 服务不可用、
  扫码未知码、相机不可用,均已有文案;未新增。
- 真机(iPhone 16 Pro Max)已装 M4 构建。

### 2026-10-20 · M5 准备就绪(上传待账号)

- Release 归档成功(`xcodebuild archive`,自动签名,Team GZ4LT9W9H9,版本 1.0 (1));`API_BASE_URL` 仍是 Tailscale 地址,
  正式域名定了再改 `Config/Release.xcconfig` 重新归档。
- **上传 TestFlight 失败**:`-exportArchive` 报 "Failed to Use Accounts / No Accounts"——这台 Mac 的命令行拿不到
  有 App Store Connect 权限的 Apple ID 会话;`~/.appstoreconnect/private_keys/` 有两把 API key(`63Z6JY7LQX`、
  `LMPCU2FSGZ`)但缺 Issuer ID。解法见 `docs/APP_STORE.md` §6。
- `docs/APP_STORE.md`:名称 / 副标题 / 宣传文本 / 描述 / 关键词(中英)、分类与年龄分级、隐私标签对照、审核备注
  (演示账号 + 操作步骤 + AI 说明)、提交前待办。
- `docs/privacy/index.html`:中英双语隐私政策(自动按系统语言切换),地址 https://lizhe-x.github.io/BoxMind/privacy/,
  需在 GitHub 仓库开启 Pages(main / docs)并推送。
- 审核演示账号:测试服务器 `backend/.env` 已填 `BOXMIND_REVIEW_EMAIL=review@boxmind.app` + 固定验证码,
  已登录并塞入 3 个箱子;审核期间后端必须公网可达(Funnel 或正式域名),这一步没做。
- 截图:新建 iPhone 17 Pro Max 模拟器(6.9",1320×2868,状态栏 9:41),`BoxMindUITests/ScreenshotTests`
  在 `-bm-mock` 下产出 8 张到 `docs/app-store/screenshots/`。

### 2026-10-22 · 回复点赞 / 点踩(评测闭环的 iOS 端)

- 后端每次模型请求落 `agent_runs` 一行,`/api/agent` 响应和 `/api/ask` 的 done 事件带 `run_id`
  (`AgentResponse.runId`、`AskEvent.done(boxes:creditsLeft:runId:)`),`AskMsg` 记 `runId` 和 `feedback`。
- `BoxMindAPI.rateRun(id:value:)` → `POST /api/runs/{id}/feedback`;`AppModel.rate(_:_:)` 乐观更新,再点一次清除,
  失败回滚并 toast。本地消息(问候、错误、取消)没有 run,不显示按钮。
- Ask 页每条有 run 的回复下方,朗读按钮右侧两个小拇指(`ask.up.<i>` / `ask.down.<i>`),选中态填充 + `isSelected`。
- 测试:Kit +6(`AppModelFeedbackTests`、SSE run_id、客户端请求),UI `EntryFlowTests` 增加点踩 / 清除步骤。
- 撤销已经是隐式负反馈(后端做),这里只补显式的那一半。
