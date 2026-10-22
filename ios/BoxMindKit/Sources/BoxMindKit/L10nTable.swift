// GENERATED from frontend/src/i18n.ts (+ ios/scripts/l10n_extra.json) by ios/scripts/gen_l10n.py — do not edit by hand.
// UI strings. English is the default; Chinese is the other supported language.

public enum L10nKey: String, CaseIterable, Sendable {
    case tab_home
    case tab_boxes
    case tab_me
    case cancel
    case confirm
    case done
    case add
    case download
    case view_box
    case record_here
    case new_badge
    case location_pending
    case items_n
    case empty_box
    case playing
    case read_aloud
    case unlimited
    case new_box_generic
    case home_stats
    case home_tip
    case home_last
    case home_target
    case hold_to_talk
    case home_hint
    case home_hint_target
    case input_placeholder
    case chip_where_drill
    case chip_how_many
    case chip_no_location
    case label_sample
    case my_boxes
    case new_box_l1
    case new_box_l2
    case no_boxes
    case new_box_hint
    case box_missing
    case cover_photo
    case cover_placeholder
    case new_box_badge
    case handwritten
    case updated_at
    case gps_recorded
    case gps_none
    case items_title
    case items_count
    case add_item_ph
    case from_source
    case source_voice
    case source_text
    case photos_title
    case tap_cover
    case cover_badge
    case add_photo
    case voice_notes
    case voice_note_n
    case ask_title
    case ask_sub
    case ask_ph
    case listening
    case confirm_needed
    case confirm_run
    case tts_failed
    case not_heard_type
    case mic_unavailable
    case greeting
    case agent_confirm_text
    case agent_ok
    case agent_error
    case exec_failed
    case exec_done
    case exec_incomplete
    case cancelled
    case ask_error
    case cam_title
    case cam_hint
    case cam_recognizing
    case cam_result
    case retake
    case cam_into
    case cam_existing
    case cam_new
    case cam_label_found
    case cam_label_none
    case conf_high
    case conf_medium
    case conf_low
    case cam_add_ph
    case cam_footnote
    case cam_saving
    case cam_confirm
    case cam_no_camera
    case cam_not_ready
    case recog_none
    case recog_unavailable
    case recog_failed
    case select_one
    case scan_title
    case scan_hint
    case scan_manual_link
    case scan_found
    case rescan
    case manual_title
    case manual_desc
    case manual_ph
    case scan_unknown
    case scan_failed
    case op_failed
    case me_title
    case quota
    case unlimited_big
    case used_n
    case quota_note
    case ui_lang
    case lang_note
    case gps_auto
    case gps_desc
    case export_json
    case export_csv
    case about
    case account
    case anonymous
    case sign_out
    case footer_yours
    case export_failed
    case login_email_prompt
    case login_code_sent
    case get_code
    case sending
    case dev_code
    case dev_toast
    case code_ph
    case signing_in
    case sign_in
    case change_email
    case resend
    case resend_in
    case login_footer
    case err_send_failed
    case err_verify_failed
    case err_too_soon
    case err_code_invalid
    case err_code_expired
    case err_too_many
    case err_invalid_email
    case ob_skip
    case ob1_tag
    case ob1_title
    case ob1_desc
    case ob2_tag
    case ob2_title
    case ob2_desc
    case ob3_tag
    case ob3_title
    case ob3_desc
    case ob_demo_q
    case ob_demo_a
    case ob_continue
    case ob_start
    case rec_ph
    case rec_release
    case parsing
    case confirm_title
    case new_box_auto
    case existing_append
    case original
    case fix
    case saving
    case confirm_save
    case askbox_title
    case askbox_hint
    case new_box_n
    case new_box_desc
    case recommended
    case edit_title
    case reparse
    case toast_no_items
    case toast_parse_failed
    case toast_save_failed
    case toast_not_heard
    case done_created
    case done_saved
    case done_location
    case done_gps
    case done_no_location
    case marker_tip
    case marker_tip_short
    case photo_line2
    case toast_photo_failed
    case toast_cover_set
    case toast_cover_failed
    case toast_add_failed
    case toast_save_item_failed
    case toast_delete_failed
    case toast_settings_failed
    case just_now
    case minutes_ago
    case today
    case nearby
    case km_away
    case toast_offline
    case gps_denied
    case gps_off_hint
}

extension L10n {
    static let en: [L10nKey: String] = [
        .tab_home: "Home",
        .tab_boxes: "Boxes",
        .tab_me: "Me",
        .cancel: "Cancel",
        .confirm: "Confirm",
        .done: "Done",
        .add: "Add",
        .download: "Download",
        .view_box: "View box",
        .record_here: "Record into this box",
        .new_badge: "New",
        .location_pending: "Location not set",
        .items_n: "{n} item types",
        .empty_box: "Empty",
        .playing: "Playing…",
        .read_aloud: "Read aloud",
        .unlimited: "Unlimited",
        .new_box_generic: "New box",
        .home_stats: "{boxes} boxes · {items} item types remembered",
        .home_tip: "Write a label on the box with a marker (e.g. “1”), then hold the button and say what went inside.",
        .home_last: "Saved to {name} · {time}",
        .home_target: "Recording into {name}",
        .hold_to_talk: "Hold to talk",
        .home_hint: "Add items or ask a question — the AI works out which",
        .home_hint_target: "Just name the items, they go into {name}",
        .input_placeholder: "Type to add items or ask…",
        .chip_where_drill: "Which box is the drill in?",
        .chip_how_many: "How many boxes do I have?",
        .chip_no_location: "Which boxes have no location?",
        .label_sample: "1",
        .my_boxes: "My boxes",
        .new_box_l1: "Write a label,",
        .new_box_l2: "say it, done",
        .no_boxes: "No boxes yet — go home and say “box 1 has…” to create the first one",
        .new_box_hint: "Go home and say “box N has…” to create a box",
        .box_missing: "Box not found",
        .cover_photo: "Box photo",
        .cover_placeholder: "Box photo · placeholder",
        .new_box_badge: "New box",
        .handwritten: "Label {label}",
        .updated_at: "Updated {time}",
        .gps_recorded: "GPS recorded, visible only to you",
        .gps_none: "No GPS recorded",
        .items_title: "Items",
        .items_count: "{n} types",
        .add_item_ph: "Add an item (type a name)",
        .from_source: "From {source} entry · organised by AI",
        .source_voice: "voice",
        .source_text: "text",
        .photos_title: "Photos",
        .tap_cover: "Tap a photo to set the cover",
        .cover_badge: "Cover",
        .add_photo: "Add photo",
        .voice_notes: "Voice notes",
        .voice_note_n: "Voice note {n}",
        .ask_title: "Ask BoxMind",
        .ask_sub: "Ask in any language",
        .ask_ph: "Where is my…",
        .listening: "Listening…",
        .confirm_needed: "These actions need your confirmation:",
        .confirm_run: "Confirm",
        .tts_failed: "Text-to-speech failed",
        .not_heard_type: "Didn't catch that, type your question",
        .mic_unavailable: "Microphone unavailable, type your question",
        .greeting: "Hi! I remember everything in your boxes. Ask me anything, like “where is the drill?”",
        .agent_confirm_text: "Please confirm this action:",
        .agent_ok: "Done.",
        .agent_error: "Something went wrong, please try again.",
        .exec_failed: "Failed",
        .exec_done: "Done",
        .exec_incomplete: "Not completed",
        .cancelled: "OK, cancelled.",
        .ask_error: "Something went wrong, please try again later.",
        .cam_title: "Photo intake",
        .cam_hint: "Point at the open box and take one shot — items and the handwritten label are both read",
        .cam_recognizing: "AI is looking…",
        .cam_result: "Results",
        .retake: "Retake",
        .cam_into: "Into {box} · {status}",
        .cam_existing: "existing box",
        .cam_new: "new box",
        .cam_label_found: "Handwritten label “{label}” found in the photo",
        .cam_label_none: "No label found, next number assigned",
        .conf_high: "high",
        .conf_medium: "medium",
        .conf_low: "low",
        .cam_add_ph: "Add an item manually",
        .cam_footnote: "Edit names / quantities · tap the dot to unselect · add items by hand",
        .cam_saving: "Saving…",
        .cam_confirm: "Save {n} item types",
        .cam_no_camera: "Cannot open the camera, check permissions",
        .cam_not_ready: "Camera is not ready yet",
        .recog_none: "Nothing recognised, try another angle",
        .recog_unavailable: "Recognition service unavailable",
        .recog_failed: "Recognition failed, try again",
        .select_one: "Select at least one item",
        .scan_title: "Scan",
        .scan_hint: "Point at the QR / barcode on the box",
        .scan_manual_link: "No code on the box? Enter the handwritten label",
        .scan_found: "Found · {code}",
        .rescan: "Scan again",
        .manual_title: "Enter the label written on the box",
        .manual_desc: "Numbers, letters or words all work — e.g. 3, ABC, red box. If it does not exist yet it is created.",
        .manual_ph: "e.g. 3",
        .scan_unknown: "No box linked to this code, try the handwritten label",
        .scan_failed: "Scan failed, try again",
        .op_failed: "Something went wrong, try again",
        .me_title: "Me",
        .quota: "Usage",
        .unlimited_big: "Unlimited",
        .used_n: "{n} used",
        .quota_note: "Unlimited intake and AI questions · scanning and browsing are free",
        .ui_lang: "Language",
        .lang_note: "AI answers follow the language you ask in",
        .gps_auto: "Record GPS automatically",
        .gps_desc: "Tell home / storage unit / parents' place apart; visible only to you",
        .export_json: "Export my data (JSON)",
        .export_csv: "Export my data (CSV)",
        .about: "About BoxMind",
        .account: "Account",
        .anonymous: "anonymous",
        .sign_out: "Sign out",
        .footer_yours: "Your data is yours: export or delete it any time",
        .export_failed: "Export failed, try again",
        .login_email_prompt: "Enter your email to sign in or sign up with a code",
        .login_code_sent: "Code sent to {email}",
        .get_code: "Get code",
        .sending: "Sending…",
        .dev_code: "Dev-mode code",
        .dev_toast: "Dev mode: the code is shown below",
        .code_ph: "6-digit code",
        .signing_in: "Signing in…",
        .sign_in: "Sign in",
        .change_email: "Use another email",
        .resend: "Resend",
        .resend_in: "Resend ({s}s)",
        .login_footer: "By signing in you agree that your data is yours to export or delete at any time",
        .err_send_failed: "Could not send the code",
        .err_verify_failed: "Verification failed",
        .err_too_soon: "Too many requests, wait a moment",
        .err_code_invalid: "Wrong code",
        .err_code_expired: "Code expired",
        .err_too_many: "Too many attempts, request a new code",
        .err_invalid_email: "Invalid email address",
        .ob_skip: "Skip",
        .ob1_tag: "01 · No setup",
        .ob1_title: "A marker pen is all you need",
        .ob1_desc: "Write a label on the box — “1”, “ABC”, “red box”, anything. No stickers, no printing: say the label and the box exists.",
        .ob2_tag: "02 · Hold to talk",
        .ob2_title: "Say it once, the AI remembers",
        .ob2_desc: "“Box 1 has three down jackets and two pairs of snow boots” — let go, and items, quantities and location are filed. No forms, no categories.",
        .ob3_tag: "03 · Just ask",
        .ob3_title: "Ask where it is, get an answer",
        .ob3_desc: "“Where are my snow boots?” Record in one language, ask in another. The AI tells you the box, the shelf and how far away it is.",
        .ob_demo_q: "Where are my snow boots?",
        .ob_demo_a: "In Box 1 · garage, left shelf",
        .ob_continue: "Continue",
        .ob_start: "Get started",
        .rec_ph: "Say what went in and where, or ask me to find something…",
        .rec_release: "Release to finish · the AI organises it",
        .parsing: "AI is organising…",
        .confirm_title: "Organised. Save it?",
        .new_box_auto: "New box · created automatically",
        .existing_append: "Existing box · items appended",
        .original: "You said: {text}",
        .fix: "Edit",
        .saving: "Saving…",
        .confirm_save: "Save",
        .askbox_title: "{n} item types organised — which box?",
        .askbox_hint: "You didn't name a box — pick one, or let me number a new one",
        .new_box_n: "New {name}",
        .new_box_desc: "Next free number · GPS recorded too",
        .recommended: "Suggested",
        .edit_title: "Edit the text",
        .reparse: "Parse again",
        .toast_no_items: "I couldn't find any items to add, could you be more specific?",
        .toast_parse_failed: "The AI could not parse that, please try again",
        .toast_save_failed: "Saving failed, please try again",
        .toast_not_heard: "Didn't catch that, try typing in the box below",
        .done_created: "Created {name} and saved",
        .done_saved: "Saved to {name}",
        .done_location: "Location: {loc}",
        .done_gps: "GPS position recorded",
        .done_no_location: "Location to be added",
        .marker_tip: "Remember to write “{label}” on the box with a marker so you can match it later",
        .marker_tip_short: "Remember to write “{label}” on the box",
        .photo_line2: "Recognised from the photo · organised by AI",
        .toast_photo_failed: "Photo upload failed, try again",
        .toast_cover_set: "Set as cover",
        .toast_cover_failed: "Could not set the cover",
        .toast_add_failed: "Could not add, try again",
        .toast_save_item_failed: "Could not save, try again",
        .toast_delete_failed: "Could not delete, try again",
        .toast_settings_failed: "Could not save settings, try again",
        .just_now: "just now",
        .minutes_ago: "{n} min ago",
        .today: "today",
        .nearby: "nearby",
        .km_away: "{km} km away",
        .toast_offline: "Can't reach the server — check your connection",
        .gps_denied: "Location access is off — allow it in Settings to remember where boxes are",
        .gps_off_hint: "Location is off; boxes are saved without a position",
    ]

    static let zh: [L10nKey: String] = [
        .tab_home: "首页",
        .tab_boxes: "箱子",
        .tab_me: "我的",
        .cancel: "取消",
        .confirm: "确认",
        .done: "完成",
        .add: "添加",
        .download: "下载",
        .view_box: "查看箱子",
        .record_here: "录入到此箱",
        .new_badge: "新",
        .location_pending: "位置待补充",
        .items_n: "{n} 类物品",
        .empty_box: "空箱",
        .playing: "播放中…",
        .read_aloud: "朗读",
        .unlimited: "无限次",
        .new_box_generic: "新箱子",
        .home_stats: "{boxes} 个箱子 · {items} 类物品已记住",
        .home_tip: "用马克笔在箱子上写个编号(如「1号」),点击下方按钮,说说里面装了什么。",
        .home_last: "已记录到 {name} · {time}",
        .home_target: "录入到 {name}",
        .hold_to_talk: "按住说话",
        .home_hint: "录入物品,或直接提问 — AI 自动听懂",
        .home_hint_target: "直接说物品,自动归入 {name}",
        .input_placeholder: "输入文字录入或提问…",
        .chip_where_drill: "电钻在哪个箱子?",
        .chip_how_many: "我一共有几个箱子?",
        .chip_no_location: "哪些箱子还没记位置?",
        .label_sample: "1号",
        .my_boxes: "我的箱子",
        .new_box_l1: "写个编号",
        .new_box_l2: "开口即建",
        .no_boxes: "还没有箱子 — 回主页说一句「1号箱放了…」即可建第一个箱子",
        .new_box_hint: "回到主页,说一句「N号箱放了…」就能建箱",
        .box_missing: "箱子不存在",
        .cover_photo: "箱子照片",
        .cover_placeholder: "箱子照片 · 占位",
        .new_box_badge: "新箱子",
        .handwritten: "手写编号 {label}",
        .updated_at: "更新于 {time}",
        .gps_recorded: "GPS 已记录,仅自己可见",
        .gps_none: "未记录 GPS",
        .items_title: "箱内物品",
        .items_count: "{n} 类",
        .add_item_ph: "添加物品(输入名称)",
        .from_source: "来自{source}录入 · AI 自动整理",
        .source_voice: "语音",
        .source_text: "文字",
        .photos_title: "箱子照片",
        .tap_cover: "点照片设为封面",
        .cover_badge: "封面",
        .add_photo: "添加照片",
        .voice_notes: "录入语音",
        .voice_note_n: "录入语音 {n}",
        .ask_title: "问 BoxMind",
        .ask_sub: "中 / 英 · 跨语言都能查",
        .ask_ph: "问我东西在哪…",
        .listening: "正在听…",
        .confirm_needed: "以下操作需要确认:",
        .confirm_run: "确认执行",
        .tts_failed: "语音合成失败",
        .not_heard_type: "没听清,直接打字问我吧",
        .mic_unavailable: "麦克风不可用,直接打字问我吧",
        .greeting: "你好!我记得你所有箱子里的东西。想找什么直接问,比如「电钻在哪?」",
        .agent_confirm_text: "需要你确认这个操作:",
        .agent_ok: "好的。",
        .agent_error: "操作出错了,请重试。",
        .exec_failed: "执行失败",
        .exec_done: "已完成",
        .exec_incomplete: "未完成",
        .cancelled: "好的,已取消。",
        .ask_error: "出错了,请稍后再试。",
        .cam_title: "拍照识别",
        .cam_hint: "对准打开的箱子,拍一张就行 — 物品和手写编号都能认",
        .cam_recognizing: "AI 识别中…",
        .cam_result: "识别结果",
        .retake: "重拍",
        .cam_into: "入库到 {box} · {status}",
        .cam_existing: "已有箱子",
        .cam_new: "自动新建",
        .cam_label_found: "照片识别到手写编号「{label}」",
        .cam_label_none: "未识别到编号,自动起号",
        .conf_high: "置信度高",
        .conf_medium: "置信度中",
        .conf_low: "置信度低",
        .cam_add_ph: "手动添加物品(输入名称)",
        .cam_footnote: "可改名称/数量 · 点圆点取消勾选 · 可手动加物品",
        .cam_saving: "入库中…",
        .cam_confirm: "确认入库({n} 类)",
        .cam_no_camera: "无法打开摄像头,请检查权限",
        .cam_not_ready: "摄像头还没准备好",
        .recog_none: "没识别到物品,换个角度再拍?",
        .recog_unavailable: "识别服务暂不可用",
        .recog_failed: "识别失败,请重试",
        .select_one: "至少选一类物品",
        .scan_title: "扫码",
        .scan_hint: "对准箱子上的二维码 / 条形码",
        .scan_manual_link: "箱子没贴码?输入手写编号",
        .scan_found: "识别成功 · {code}",
        .rescan: "重新扫描",
        .manual_title: "输入箱子上的手写编号",
        .manual_desc: "数字、字母、中文都可以 — 比如 3号、ABC、红色大箱。没有就帮你新建。",
        .manual_ph: "如:3号",
        .scan_unknown: "未关联箱子,试试输入手写编号",
        .scan_failed: "识别失败,请重试",
        .op_failed: "操作失败,请重试",
        .me_title: "我的",
        .quota: "使用额度",
        .unlimited_big: "无限制",
        .used_n: "已用 {n} 次",
        .quota_note: "录入与 AI 查询不限次数,免费畅用 · 扫码与浏览不计次",
        .ui_lang: "界面语言",
        .lang_note: "AI 对话语言自动识别:说中文答中文,说英文答英文",
        .gps_auto: "自动记录 GPS 位置",
        .gps_desc: "区分家 / 仓库 / 父母家,仅你自己可见",
        .export_json: "导出我的数据 (JSON)",
        .export_csv: "导出我的数据 (CSV)",
        .about: "关于 BoxMind",
        .account: "当前账户",
        .anonymous: "匿名",
        .sign_out: "退出登录",
        .footer_yours: "数据归你所有,可随时导出或删除",
        .export_failed: "导出失败,请重试",
        .login_email_prompt: "输入邮箱,用验证码登录或注册",
        .login_code_sent: "验证码已发送至 {email}",
        .get_code: "获取验证码",
        .sending: "发送中…",
        .dev_code: "开发模式验证码",
        .dev_toast: "开发模式:验证码已显示在下方",
        .code_ph: "6 位验证码",
        .signing_in: "登录中…",
        .sign_in: "登录",
        .change_email: "换个邮箱",
        .resend: "重新发送",
        .resend_in: "重新发送 ({s}s)",
        .login_footer: "登录即表示同意,数据归你所有,可随时导出或删除",
        .err_send_failed: "发送失败",
        .err_verify_failed: "验证失败",
        .err_too_soon: "请求过于频繁,请稍后再试",
        .err_code_invalid: "验证码错误",
        .err_code_expired: "验证码已过期",
        .err_too_many: "尝试次数过多,请重新获取",
        .err_invalid_email: "邮箱格式不正确",
        .ob_skip: "跳过",
        .ob1_tag: "01 · 零门槛",
        .ob1_title: "一支马克笔,就能开始",
        .ob1_desc: "在箱子上写个编号 —「1号」「ABC」「红色大箱」都行。不用贴纸、不用打印,说出编号就能建箱。",
        .ob2_tag: "02 · 按住说话",
        .ob2_title: "说一句话,AI 全记住",
        .ob2_desc: "「1号箱放了羽绒服三件、雪地靴两双」— 松开手指,物品、数量、位置自动整理入库。无表单、无分类。",
        .ob3_tag: "03 · 开口就找到",
        .ob3_title: "东西在哪,问一句就知道",
        .ob3_desc: "「我的雪地靴在哪?」中文录入、英文提问也能查到。AI 告诉你在哪个箱子、哪层货架、离你多远。",
        .ob_demo_q: "雪地靴在哪?",
        .ob_demo_a: "在 1号箱 · 车库左侧货架",
        .ob_continue: "继续",
        .ob_start: "开始使用",
        .rec_ph: "说出物品和位置,或问我找东西…",
        .rec_release: "松开手指结束 · AI 自动整理",
        .parsing: "AI 正在整理…",
        .confirm_title: "AI 已整理,确认入库?",
        .new_box_auto: "新箱子 · 自动创建",
        .existing_append: "已有箱子 · 追加入库",
        .original: "原话:{text}",
        .fix: "修正",
        .saving: "入库中…",
        .confirm_save: "确认入库",
        .askbox_title: "已整理 {n} 类物品 — 放进哪个箱子?",
        .askbox_hint: "你这次没说箱号 — 选一个已有的,或让我自动起号",
        .new_box_n: "新建 {name}",
        .new_box_desc: "自动取下一个编号 · GPS 同时记录",
        .recommended: "推荐",
        .edit_title: "修正内容",
        .reparse: "重新解析",
        .toast_no_items: "没听出要录入的物品,再说具体一点?",
        .toast_parse_failed: "AI 解析失败,请重试",
        .toast_save_failed: "入库失败,请重试",
        .toast_not_heard: "没听清,在下方输入框直接打字试试",
        .done_created: "已建 {name}并入库",
        .done_saved: "已记录到 {name}",
        .done_location: "位置:{loc}",
        .done_gps: "GPS 已记录当前位置",
        .done_no_location: "位置待补充",
        .marker_tip: "记得用马克笔把「{label}」写到箱子上,下次一眼对上号",
        .marker_tip_short: "记得用马克笔把「{label}」写到箱子上",
        .photo_line2: "照片已识别 · AI 自动整理",
        .toast_photo_failed: "照片上传失败,请重试",
        .toast_cover_set: "已设为封面",
        .toast_cover_failed: "设置封面失败",
        .toast_add_failed: "添加失败,请重试",
        .toast_save_item_failed: "保存失败,请重试",
        .toast_delete_failed: "删除失败,请重试",
        .toast_settings_failed: "设置保存失败,请重试",
        .just_now: "刚刚",
        .minutes_ago: "{n} 分钟前",
        .today: "今天",
        .nearby: "就在附近",
        .km_away: "距你 {km} km",
        .toast_offline: "连不上服务器,请检查网络后重试",
        .gps_denied: "没有定位权限,请到系统设置里允许,才能记住箱子的位置",
        .gps_off_hint: "定位已关闭,入库时不记录位置",
    ]
}
