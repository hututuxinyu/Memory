# BrowserGateway 逆向文档自动审核清单（示例）

> 以下基于 `D:\Code\SBG\BrowserGateway\docs` 真实文档目录和内容生成，模拟自动扫描后的输出。

---

```
══════════════════════════════════════════════════════════════════
逆向文档自动审核清单
══════════════════════════════════════════════════════════════════

仓库: BrowserGateway
文档生成时间: 2026-08-18
自动扫描时间: 2026-10-12
文档总数: 130个文件
原子声明总数: 1000条
══════════════════════════════════════════════════════════════════

自动扫描统计:
  ✅ 高置信(无需审核):  768条 (77%)  → 机械检查+代码比对确认一致
  ⚠️ 疑似问题(需审核):  232条 (23%)  → 见下方清单
  
  问题分类:
    ❌ 代码已变:     98条  (函数/逻辑改了，文档没跟上)
    ⚠️ 语义缺失:     74条  (文档不完整，缺少新增逻辑)
    🔤 术语偏差:     35条  (AI描述的业务术语和领域定义不一致)
    📋 枚举/配置过时: 25条  (枚举值/配置项变了)
══════════════════════════════════════════════════════════════════
```

---

## 【高优先级】代码已变 — 文档描述的逻辑和代码现状直接矛盾（98条，展示前5条）

---

### 1. docs/0-biz/rules/rules-browser.md — 规则 browser-closer-if-expired

```
📄 文档原文(8月18日):
   规则名: browser-closer-if-expired
   条件: 本地心跳过期 System.nanoTime() - chromeSet.getHeartbeats(userId) > ttl
   动作: chromeSet.delete(userId) 关闭过期实例并上报用量
   代码位置: BrowserCloserTask.java

🔍 代码现状(10月12日):
   commit a1b2c3d (9月5日) 新增了远端不活跃判断:
   
   // BrowserCloserTask.java 第67行
   if (ub == null || browserInstance == null 
       || !browserInstance.equals(config.getSelfAddr()) 
       || heartbeats == null) {     // ← 新增的判断
       chromeSet.delete(userId);
       return;
   }
   if (System.nanoTime() - heartbeats > ttl) {  // ← 原来的判断
       chromeSet.delete(userId);
   }
   
   现在是"远端不活跃 OR 心跳过期"两个条件，文档只写了心跳过期。

❌ 差异: 文档缺少 browser-closer-is-active 规则（新增的远端不活跃判断）
置信度: 0.15 (极低 — 文档与代码明确不一致)
建议: 补充规则 browser-closer-is-active，条件为"CSE远端UserBind不活跃"
```
`[确认过时 → 补充规则]  [AI误报 → 标记正确]  [查看代码 → BrowserCloserTask.java:67]`

---

### 2. docs/0-tech/concurrency-guidelines/concurrency-guidelines-browser-check-task.md — 检查周期配置

```
📄 文档原文(8月18日):
   | browsergw.scheduled.check-browser-period | 检查周期配置key | 
   代码默认 1800000ms；application.yaml 配置 600000 |

🔍 代码现状(10月12日):
   # application.yaml 第23行（9月修改）
   browsergw:
     scheduled:
       check-browser-period: 300000    # ← 从600000改成了300000
   
   # BrowserCheckTask.java 第18行
   @Value("${browsergw.scheduled.check-browser-period:1800000}")
   private long period;   // 代码默认值还是1800000，但yaml配了300000

❌ 差异: yaml配置从600000改为300000，文档写的600000已过时
置信度: 0.20
建议: 更新为"代码默认1800000ms；application.yaml配置300000"
```
`[确认过时 → 更新配置值]  [AI误报]  [查看代码 → application.yaml:23]`

---

### 3. docs/0-arch/interaction-model/interaction-model-create-browser.md — Chrome启动方式

```
📄 文档原文(8月18日):
   browser-gateway 调用本接口拉起 Chrome 浏览器：初始化用户数据目录与扩展白名单，
   通过 Playwright 以 persistent context 方式启动 Chrome（加载控制/录屏扩展），
   包装为 BrowserWrapper 登记入内存列表。

🔍 代码现状(10月12日):
   commit f8a3b2c (9月20日):
   
   # browser_proxy/api/browser.py 第45行
   # 原来: context = playwright.chromium.launch_persistent_context(userdata_dir, ...)
   # 现在:
   browser = await playwright.chromium.launch(     # ← 改为launch()
       headless=False,
       args=["--load-extension=" + ext_path]
   )
   context = await browser.new_context()            # ← 独立创建context

❌ 差异: 启动方式从 launch_persistent_context 改为 launch() + new_context()
        persistent context（持久上下文）→ 独立浏览器实例
置信度: 0.10 (极低)
建议: 更新为"通过Playwright launch()启动Chrome独立实例，加载控制/录屏扩展"
```
`[确认过时 → 更新交互模型]  [AI误报]  [查看代码 → browser.py:45]`

---

### 4. docs/0-biz/data-model/data-model-browser-wrapper.md — BrowserWrapper字段

```
📄 文档原文(8月18日):
   | 字段名 | 类型 | 说明 |
   | proxyContextId | String | Playwright创建的context ID |
   | muenDriver | MuenDriver | Muen SDK驱动实例 |
   | status | BrowserStatus | 实例状态枚举 |

🔍 代码现状(10月12日):
   commit i7j8k9l (10月8日) 新增字段:
   
   # browser_proxy/models/browser_wrapper.py
   class BrowserWrapper:
       proxy_context_id: str
       muen_driver: MuenDriver
       status: BrowserStatus
       tcp_channel_ref: TcpChannelRef     # ← 新增! TCP通道引用
       last_health_check: float            # ← 新增! 上次健康检查时间
   
   文档缺少 tcp_channel_ref 和 last_health_check 两个字段

❌ 差异: 数据模型新增2个字段，文档未记录
置信度: 0.18
建议: 补充 tcp_channel_ref(TcpChannelRef) 和 last_health_check(float) 字段
```
`[确认过时 → 补充字段]  [AI误报]  [查看代码 → browser_wrapper.py]`

---

### 5. docs/0-tech/concurrency-guidelines/concurrency-guidelines-tcp-channel-monitor.md — 整个文件

```
📄 文档原文(8月18日):
   （文件不存在 — 8月18日时还没有TcpChannelMonitor类）

🔍 代码现状(10月12日):
   commit i7j8k9l (10月8日) 新增完整类:
   
   # browser-gateway/.../scheduled/TcpChannelMonitor.java
   @Component
   public class TcpChannelMonitor {
       @PostConstruct
       public void init() {
           scheduler = Executors.newSingleThreadScheduledExecutor();
           scheduler.scheduleAtFixedRate(
               this::monitorChannels, 0, 
               period, TimeUnit.MILLISECONDS);
       }
       
       public void closeStaleChannel() { ... }
       public void closeAllChannels() { ... }
   }
   
   配置项: browsergw.scheduled.tcp-monitor-period = 60000

❌ 差异: 完整新增模块，文档完全没有
        包括: 并发规范、交互模型、业务规则全部缺失
置信度: 0.05 (极低 — 文档完全缺失)
建议: 新增3个文档:
      - 0-tech/concurrency-guidelines/concurrency-guidelines-tcp-channel-monitor.md
      - 0-arch/interaction-model/interaction-model-tcp-channel-monitor.md
      - 0-biz/rules/rules-tcp-channel.md
```
`[确认缺失 → 新增文档]  [AI误报]  [查看代码 → TcpChannelMonitor.java]`

---

## 【中优先级】语义缺失 — 文档不完整，缺少新增逻辑（74条，展示前5条）

---

### 6. docs/0-biz/rules/rules-browser.md — 规则 check-browser-status-reopen

```
📄 文档原文(8月18日):
   规则名: check-browser-status-reopen
   条件: equalsConfig判定Chrome配置变更
   配置字段: ControlExtentionPath/ControlExtentionId/ChromeHeight/
             ChromeWidth/FrameRate/SampleRate/Channels/BitRate
   动作: 删除旧实例并以新配置重建浏览器

🔍 代码现状(10月12日):
   commit c3d4e5f (10月1日) equalsConfig 方法新增了比较字段:
   
   # RemoteImpl.java equalsConfig()
   // 原来比较8个字段
   // 新增:
   if (!Objects.equals(this.userdataPath, other.userdataPath)) return false;  // ← 新增
   if (!Objects.equals(this.incognito, other.incognito)) return false;        // ← 新增
   if (this.maxVideoBitrate != other.maxVideoBitrate)) return false;          // ← 新增

⚠️ 差异: equalsConfig新增了3个比较字段(userdataPath/incognito/maxVideoBitrate)
        文档列的还是8个字段，实际是11个
        不完全错误，但配置变更判断条件不完整
置信度: 0.42 (中低)
建议: 补充 userdataPath、incognito、maxVideoBitrate 三个字段到配置变更列表
```
`[确认缺失 → 补充字段]  [AI误报]  [查看代码 → RemoteImpl.java:equalsConfig]`

---

### 7. docs/0-arch/interaction-model/interaction-model-control-tcp-login.md — 登录流程

```
📄 文档原文(8月18日):
   时序图: GW → API → Login → onControlTcpConnected → 事件处理完成
   参与方: browser-gateway, api, Playwright/Chrome

🔍 代码现状(10月12日):
   单看每个函数: Login()还在 ✓, onControlTcpConnected()还在 ✓
   
   跨commit合成发现:
   commit d4e5f6g (9月15日): 在Login和onControlTcpConnected之间
     插入了 TcpChannelMonitor.registerChannel() 步骤
   
   commit e5f6g7h (9月28日): 在onControlTcpConnected之后
     插入了 ServiceReporter.reportLoginResult() 步骤
   
   实际流程: Login → registerChannel → onControlTcpConnected 
            → reportLoginResult → 事件处理
   文档流程: Login → onControlTcpConnected → 事件处理

⚠️ 差异: 流程从3步变为5步，文档缺少registerChannel和reportLoginResult两步
        单看每个函数都在(机械检查通过)，但流程不完整(合成检查发现)
置信度: 0.35 (中低 — 隐性不完整)
建议: 时序图补充 registerChannel 和 reportLoginResult 两个步骤
```
`[确认缺失 → 补充流程]  [AI误报]  [查看代码 → control_tcp_login相关文件]`

---

### 8. docs/0-biz/rules/rules-browser.md — 规则 alarm-300033

```
📄 文档原文(8月18日):
   规则名: alarm-300033
   条件: 创建/登录异常消息含 "failed to create browsers"
   动作: 上报告警 ALARM_300033，随后删除用户实例

🔍 代码现状(10月12日):
   commit f6g7h8i (10月3日):
   
   // RemoteImpl.java
   if (msg.contains("failed to create browsers") 
       || msg.contains("failed to init extension")    // ← 新增!
       || msg.contains("extension load timeout")) {   // ← 新增!
       AlarmUtil.report(AlarmEnum.ALARM_300033);
       chromeSet.delete(userId);
   }
   
   触发条件从1个扩展到3个

⚠️ 差异: 告警触发条件从"failed to create browsers"1个扩展到3个
        文档只写了第1个，缺少后2个新增的触发条件
置信度: 0.38
建议: 补充 "failed to init extension" 和 "extension load timeout" 两个触发条件
```
`[确认缺失 → 补充条件]  [AI误报]  [查看代码 → RemoteImpl.java]`

---

### 9. docs/0-tech/concurrency-guidelines/concurrency-guidelines-websocket-boss-worker.md — Worker数量

```
📄 文档原文(8月18日):
   | bossGroup | NioEventLoopGroup | Boss线程数=1，接受连接 |
   | workerGroup | NioEventLoopGroup | Worker线程数=Runtime.getRuntime().availableProcessors()*2 |

🔍 代码现状(10月12日):
   commit g7h8i9j (9月25日):
   
   # WebSocketServer.java
   int workerCount = config.getWebSocket().getWorkerThreads();  // ← 改为配置
   // 原来硬编码: availableProcessors()*2
   // 现在从yaml读: browsergw.websocket.worker-threads: 4
   
   workerGroup = new NioEventLoopGroup(workerCount);

⚠️ 差异: Worker线程数从硬编码availableProcessors()*2改为配置化
        文档描述的是旧的硬编码方式
置信度: 0.40
建议: 更新为"Worker线程数由browsergw.websocket.worker-threads配置，默认4"
```
`[确认过时 → 更新描述]  [AI误报]  [查看代码 → WebSocketServer.java]`

---

### 10. docs/0-biz/interface/interface-control-tcp-server.md — 接口参数

```
📄 文档原文(8月18日):
   POST /control/tcp/login
   请求参数:
   | userId | String | 用户ID(IMEI+IMSI派生) |
   | deviceId | String | 设备ID |

🔍 代码现状(10月12日):
   commit h8i9j0k (10月5日):
   
   # ControlTcpServer.py
   async def login(self, request):
       user_id = request.userId
       device_id = request.deviceId
       session_token = request.sessionToken     # ← 新增! 会话令牌
       client_version = request.clientVersion   # ← 新增! 客户端版本
       
⚠️ 差异: 接口新增了 sessionToken 和 clientVersion 两个参数
        文档只列了 userId 和 deviceId
置信度: 0.30
建议: 补充 sessionToken(String, 会话令牌) 和 clientVersion(String, 客户端版本)
```
`[确认缺失 → 补充参数]  [AI误报]  [查看代码 → ControlTcpServer.py]`

---

## 【低优先级】术语偏差 — AI描述的业务术语和领域定义不一致（35条，展示前5条）

---

### 11. docs/0-biz/lexicon/lexicon-browser.md — 术语 "预开浏览器请求"

```
📄 AI逆向文档(8月18日):
   术语: 预开浏览器请求（InitBrowserRequest）
   释义: 预开浏览器实例的HTTP请求模型，含设备与应用信息，
         服务端按IMEI+IMSI生成userId并经Muen SDK创建Chrome

🔤 领域知识基准(田主校验过的正确版本):
   术语: 预开（PreOpen）
   正确释义: 为用户预先创建并分配Chrome实例，实例在用户连接前
            已完成初始化（含扩展加载、用户数据目录创建、屏幕参数配置），
            用户连接时直接复用已就绪实例，无需等待启动。
   
   区别: "预开"≠"提前打开"。"预开"是业务流程术语——
         在用户连接前准备好实例，属于容量预热策略；
         AI描述的"预开浏览器实例"容易被理解为"提前打开浏览器"，语义偏差。

🔤 差异: AI描述偏技术化（HTTP请求模型），缺少业务语义（容量预热策略）
置信度: 0.55 (中等 — 技术描述部分正确，但业务语义不完整)
建议: 补充"预开属于容量预热策略，实例在用户连接前完成初始化"的业务语义
```
`[确认偏差 → 补充业务语义]  [AI误报]  [查看术语表]`

---

### 12. docs/0-biz/rules/rules-browser.md — 术语 "关闭"

```
📄 AI逆向文档(8月18日):
   规则描述中使用"关闭过期实例""关闭实例"

🔤 领域知识基准:
   正确术语: "回收"（Recycle）≠ "关闭"（Close）
   - "关闭"：主动停止实例运行（用户操作或手动管理）
   - "回收"：系统判断实例不活跃或过期后自动清理（含数据上传+实例删除+用量上报）
   
   BrowserCloserTask 做的是"回收"不是"关闭"：
   回收 = uploadUserData + deleteInstance + reportUsage
   关闭 = 仅stopChromeProcess

🔤 差异: AI用"关闭"描述了"回收"逻辑，业务语义不同
        "关闭"不含数据上传和用量上报，"回收"包含
置信度: 0.48
建议: 将"关闭过期实例"改为"回收过期实例"，明确回收包含数据上传+删除+用量上报
```
`[确认偏差 → 更正术语]  [AI误报]  [查看术语表]`

---

### 13. docs/0-biz/lexicon/lexicon-browser.md — 术语 "播放模式(play_mode)"

```
📄 AI逆向文档(8月18日):
   术语: 播放模式（play_mode）
   释义: 0=JPG模式, 1=实时流模式（默认1）

🔤 代码现状:
   commit k9l0m1n (10月10日):
   
   # InitBrowserRequest.java
   public enum PlayMode {
       JPG(0),           // JPG降级模式
       REALTIME(1),      // 实时流模式
       ADAPTIVE(2)       // ← 新增! 自适应模式（根据网络动态切换）
   }

🔤 差异: 枚举新增了 ADAPTIVE(2)，文档只有0和1
        同时文档缺少业务语义说明：
        - JPG模式是降级模式（网络差时用），不是主动选择
        - ADAPTIVE模式会根据网络质量在JPG和REALTIME间动态切换
置信度: 0.25
建议: 补充 play_mode=2(ADAPTIVE)，并补充各模式的业务场景说明
```
`[确认缺失 → 补充枚举值]  [AI误报]  [查看代码 → InitBrowserRequest.java]`

---

### 14. docs/0-arch/structure-model/structure-model-browser-gateway.md — Muen SDK描述

```
📄 AI逆向文档(8月18日):
   "browser-gateway通过Muen SDK创建Chrome实例"

🔤 领域知识基准:
   正确描述: Muen SDK不是"创建Chrome"的SDK，而是:
   - Muen是华为的可信虚拟化平台（Trusted Hypervisor）
   - Muen SDK用于在可信执行环境（TEE）中隔离运行Chrome
   - 作用: 安全隔离，防止恶意网页访问宿主系统
   - 不是Chrome的启动器，是Chrome的安全沙箱

🔤 差异: AI把Muen SDK描述为"创建Chrome的SDK"，实际是"安全隔离Chrome的可信虚拟化平台"
        技术角色描述错误（启动器→安全沙箱）
置信度: 0.20
建议: 更正为"通过Muen SDK在可信执行环境(TEE)中隔离运行Chrome实例"
```
`[确认偏差 → 更正描述]  [AI误报]  [查看术语表]`

---

### 15. docs/0-tech/resilience-guidelines/resilience-guidelines-retry.md — 重试策略

```
📄 AI逆向文档(8月18日):
   "使用指数退避重试策略，初始间隔1秒，最大3次重试"

🔤 代码现状:
   # RetryConfig.java
   @Value("${browsergw.retry.max-attempts:5}")       // 文档说3，实际5
   private int maxAttempts;
   
   @Value("${browsergw.retry.initial-interval-ms:500}") // 文档说1秒，实际500ms
   private long initialInterval;
   
   @Value("${browsergw.retry.multiplier:2.0}")         // 文档没提乘子
   private double multiplier;

🔤 差异: 重试次数3→5，初始间隔1s→500ms，缺少乘子描述
置信度: 0.15
建议: 更新为"指数退避，初始500ms，乘子2.0，最大5次重试"
```
`[确认过时 → 更新参数]  [AI误报]  [查看代码 → RetryConfig.java]`

---

## 审核清单总结

```
══════════════════════════════════════════════════════════════
本次审核清单: 15条 (展示样例，实际共232条)
══════════════════════════════════════════════════════════════

按责任田分发建议:

┌─────────────────────────┬──────┬────────────────────────┐
│ 责任田                  │ 条数 │ 预计耗时              │
├─────────────────────────┼──────┼──────────────────────┤
│ 浏览器实例管理           │ 48条 │ 25分钟 (每条30秒)     │
│ TCP通道/网络传输         │ 35条 │ 18分钟                │
│ 视频流/媒体              │ 32条 │ 16分钟                │
│ 接口/数据模型            │ 28条 │ 14分钟                │
│ 定时任务/并发            │ 25条 │ 13分钟                │
│ 韧性/重试               │ 20条 │ 10分钟                │
│ 框架/外部调用            │ 24条 │ 12分钟                │
│ 安全/Muen               │ 20条 │ 10分钟                │
├─────────────────────────┼──────┼──────────────────────┤
│ 合计                    │ 232条│ ~2小时 (全量)         │
│                         │      │ 或按田分并行: ~25分钟 │
└─────────────────────────┴──────┴──────────────────────┘

对比全量人工审核:
  全量: 1000条 × 30秒 = ~8.3小时 = ~1人天
  本清单: 232条 × 30秒 = ~2小时
  节省: 75%

每条都附带:
  ✅ 文档原文 (当时AI怎么写的)
  🔍 代码现状 (现在代码是什么样)
  ❌/⚠️/🔤 差异类型 (代码已变/语义缺失/术语偏差)
  📊 置信度 (0-1, 越低越需要人工确认)
  💡 建议 (怎么改)
  [确认] [误报] [查看代码] (田主操作按钮)
══════════════════════════════════════════════════════════════
```

---

*审核清单示例生成日期: 2026-10-12*
