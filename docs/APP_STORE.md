# App Store 提交资料(BoxMind iOS 1.0)

填 App Store Connect 时照抄本文件;改动先改这里再改后台,保持一份真相。中英文都要填(App Store 本地化:en-US 主,zh-Hans 副)。

## 1. 基本信息

| 项 | 值 |
|---|---|
| App 名称 | BoxMind: Find My Stuff(ASC 记录名,2026-10-22 建;设备上显示名仍是 BoxMind) |
| Bundle ID | `me.boxmind.app` |
| SKU | `boxmind-ios` |
| 主语言 | English (U.S.) |
| 分类 | Productivity(次选 Utilities) |
| 年龄分级 | 4+(所有问卷项选 None / No;无用户生成内容对外展示,无购买) |
| 价格 | 免费,无内购 |
| 版权 | 2026 Zhe Li |
| 支持 URL | https://github.com/lizhe-x/BoxMind |
| 营销 URL | https://github.com/lizhe-x/BoxMind |
| 隐私政策 URL | https://lizhe-x.github.io/BoxMind/privacy/ (`docs/privacy/index.html`,需在仓库 Settings → Pages 开启 "main / docs") |
| 设备 | iPhone only,iOS 26+ |
| 出口合规 | 只用 HTTPS → "No" 使用非豁免加密(`ITSAppUsesNonExemptEncryption = NO` 已在 Info.plist) |
| 内容版权 | 不含第三方内容 |

## 2. 文案

### en-US

**Subtitle**(30 字内):`Say it, snap it, find it`

**Promotional text**(170 字内):
> Tell BoxMind what went into a box — by voice, text or photo — and ask it later where things are. The AI organises; you just talk.

**Description**:
```
BoxMind remembers what is in your boxes so you don't have to.

SAY IT
Hold the button and say "box 3 has two down jackets and a headlamp, garage left shelf". BoxMind turns the sentence into a box with items and a location — you confirm, done.

SNAP IT
Point the camera at an open box. BoxMind lists what it sees, reads the handwritten label, and files everything under that box with the photo as its cover.

FIND IT
Ask "where are my snow boots?" or "which boxes have no location?" and get a straight answer with the box card to tap.

TELL IT WHAT TO DO
"Move the drill to box 5", "merge the two kitchen boxes", "undo that" — BoxMind carries out the change and asks before anything destructive.

ALSO
• Scan a QR or barcode on a box to open it; or type the handwritten label
• Edit items, add photos, set the cover, play back voice notes
• Optional location memory with distance to each box
• English and Chinese, light and dark
• Export everything as JSON or CSV; delete your account in one tap

Sign in with your email — no password to remember.
```

**Keywords**(100 字内,逗号分隔):
`storage,inventory,boxes,moving,garage,organizer,declutter,voice,AI,find,label,closet`

**What's New**(1.0):`First release.`

### zh-Hans

**副标题**:`说一句,拍一张,随时找到`

**宣传文本**:
> 用语音、文字或照片告诉 BoxMind 什么放进了哪个箱子,之后直接问它东西在哪。AI 负责整理,你只管开口。

**描述**:
```
BoxMind 替你记住每个箱子里有什么。

说一句
按住按钮说"3号箱放了两件羽绒服和一个头灯,在车库左边架子上",BoxMind 自动整理成箱子、物品和位置,你确认一下就入库。

拍一张
对准打开的箱子拍一张,BoxMind 列出看到的物品、认出手写编号,照片顺便当封面。

随时找到
问"雪地靴在哪?""哪些箱子还没写位置?",直接得到答案和可点开的箱子卡片。

动口不动手
"把电钻移到5号箱""合并两个厨房箱""撤销刚才的操作"——BoxMind 照做,涉及删除、合并会先向你确认。

还有
• 扫箱子上的二维码 / 条码直接打开;没贴码就输手写编号
• 编辑物品、添加照片、切换封面、回放语音备注
• 可选的位置记忆,显示每个箱子离你多远
• 中英文界面
• 一键导出 JSON / CSV;一键删除账号

邮箱验证码登录,不用记密码。
```

**关键词**:`收纳,整理,箱子,搬家,储物,库存,语音,AI,找东西,标签,衣柜,车库`

**新功能**:`首个版本。`

## 3. App Privacy(隐私标签)

"Data Linked to You",全部用途为 App Functionality,均不用于追踪:

| 类型 | 项 |
|---|---|
| Contact Info | Email Address |
| Location | Precise Location(用户可选开启) |
| User Content | Photos or Videos;Audio Data;Other User Content(文字记录) |
| Identifiers | 无(不收集设备 ID) |
| Usage Data / Diagnostics | 无(不接分析 SDK、不上报崩溃) |

与 `ios/BoxMind/Resources/PrivacyInfo.xcprivacy` 一致。第三方:LLM 网关只在处理请求时接触上述内容,不训练。

## 4. 审核备注(Review Notes)

```
Demo account (no email is sent for this account; the code is fixed):
  Email: review@boxmind.app
  Code:  <see backend/.env BOXMIND_REVIEW_CODE on the server>

How to try the core loop:
1. Home → type or hold the big button and say: "box 3 has two lamps and a headlamp, garage left shelf" → Save.
2. Home → type: "where is the tent?" → streamed answer with a box card (the demo account has boxes 1, 2 and "Kitchen spare").
3. Home → type: "delete box 2" → confirmation card → Confirm → then "undo" restores it.
4. Camera button → take a photo of any box or shelf → items are recognised → Save.
5. Scan button → "Enter the handwritten label" → type 1 → the box opens.

AI features send the typed/spoken text, the photo, and the user's own box data to our server, which calls a large language model to produce the reply. Nothing is used for training. Location is optional and off by default. Account deletion: Me → Delete account.
```

填之前把 `<see backend/.env …>` 换成真实验证码(服务器 `backend/.env` 里 `BOXMIND_REVIEW_CODE`),并确认审核期间后端可从公网访问(见下)。

## 5. 截图

6.9" 一组即可(iPhone 17 Pro Max 模拟器,1320 × 2868),由 `BoxMindUITests/ScreenshotTests` 在 `-bm-mock` 下生成,文件在 `docs/app-store/screenshots/`。顺序:首页 → 录入确认卡 → 入库完成 → 问答 → 拍照识别 → 扫码命中 → 箱子列表 → 箱子详情。上传前可在 ASC 里只选前 5 张。

## 6. 提交前必须由你完成的事

1. **后端公网可达**:已于 2026-10-22 开启 Tailscale Funnel(`tailscale funnel --bg 8001`),公网地址 `https://zhes-mac-mini.tailb3c9f2.ts.net`,与 `ios/Config/Release.xcconfig` 的 `API_BASE_URL` 一致,归档不用改;关闭用 `tailscale funnel --https=443 off`。这是 Mac mini 家用网络上的服务,够 TestFlight 和审核用;正式域名 + AWS 单机部署见下一条。
1b. **正式部署(可选)**:公司 AWS 账号(CatchLine 用的那个,us-east-1)上一台小 EC2(arm64,2–4 GB)跑 docker compose(后端 + Postgres/pgvector),EBS 存 media,Caddy 做 TLS,Route53 指一个子域。Lambda 不合适:后端常驻 1 GB 的向量模型、要 Postgres、要 SSE 流式。
2. **SMTP**:已配 Gmail(smtp.gmail.com:587,应用专用密码,发件人 lizhe.dev@gmail.com),真实验证码已收到。审核账号不受影响。
3. **App Store Connect**:App 记录已建(2026-10-22,"BoxMind: Find My Stuff",Bundle ID `me.boxmind.app`,SKU `boxmind-ios`);Free / Paid Apps 协议均 Active。
4. **上传**:`xcodebuild -exportArchive … destination=upload` 需要该 Apple ID 在 ASC 有权限,或用 ASC API Key(Key ID + **Issuer ID** + .p8)。本机 `~/.appstoreconnect/private_keys/` 已有两把 key(`63Z6JY7LQX`、`LMPCU2FSGZ`),缺 Issuer ID。拿到后:
   ```bash
   xcodebuild -exportArchive -archivePath <archive> -exportOptionsPlist ExportOptions.plist -exportPath out \
     -allowProvisioningUpdates -authenticationKeyPath ~/.appstoreconnect/private_keys/AuthKey_<ID>.p8 \
     -authenticationKeyID <ID> -authenticationKeyIssuerID <ISSUER>
   ```
   或把已导出的 `BoxMind.ipa` 用 Transporter 拖上去。
5. **GitHub Pages**:仓库 Settings → Pages → Source "Deploy from a branch",Branch `main` / folder `/docs`,隐私政策地址即生效。
6. TestFlight 内测通过后,在 ASC 填本文件的文案、截图、隐私标签、审核备注,提交审核。
