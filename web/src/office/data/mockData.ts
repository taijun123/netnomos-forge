import type {
  Agent,
  Artifact,
  ChatMessage,
  Conversation,
  CourierRoute,
  DataSource,
  OfficeProp,
  OfficeRoom,
  PacketRecord,
  RuleGroup,
  RuleItem,
  RuleSet,
  WorkflowEvent,
} from "../types/domain";

export const officeRooms: OfficeRoom[] = [
  {
    id: "corridor",
    name: "门外收发区",
    label: "门外",
    purpose: "快递B初始等待与取件的位置",
    bounds: { left: 2, top: 49, width: 17, height: 40 },
    tone: "corridor",
  },
  {
    id: "manager",
    name: "主管办公室",
    label: "主管室",
    purpose: "主管A上传规则集后进行监管扫描",
    bounds: { left: 21, top: 8, width: 31, height: 31 },
    tone: "manager",
  },
  {
    id: "operations",
    name: "数据分析办公室",
    label: "分析区",
    purpose: "员工C从 pcap/csv 数据中发现规则候选",
    bounds: { left: 21, top: 42, width: 31, height: 47 },
    tone: "work",
  },
  {
    id: "validation",
    name: "验证办公室",
    label: "验证区",
    purpose: "员工D校验规则集稳定性",
    bounds: { left: 54, top: 8, width: 24, height: 39 },
    tone: "lab",
  },
  {
    id: "pluginLab",
    name: "插件制作间",
    label: "插件间",
    purpose: "员工E打包规则插件，员工F确认受控输出",
    bounds: { left: 54, top: 50, width: 24, height: 39 },
    tone: "lab",
  },
  {
    id: "lounge",
    name: "共享休息区",
    label: "咖啡/健身",
    purpose: "办公室细节场景，提供 Marvis 式生活化元素",
    bounds: { left: 80, top: 8, width: 18, height: 81 },
    tone: "lounge",
  },
];

export const officeProps: OfficeProp[] = [
  { id: "door-main", kind: "door", label: "数据门", roomId: "corridor", position: { left: 18, top: 66 } },
  { id: "manager-board", kind: "whiteboard", label: "规则看板", roomId: "manager", position: { left: 25, top: 16 } },
  { id: "manager-plant", kind: "plant", label: "绿植", roomId: "manager", position: { left: 47, top: 31 } },
  { id: "ops-server", kind: "server", label: "数据柜", roomId: "operations", position: { left: 24, top: 78 } },
  { id: "ops-plant", kind: "plant", label: "盆栽", roomId: "operations", position: { left: 48, top: 50 } },
  { id: "validate-board", kind: "whiteboard", label: "反例墙", roomId: "validation", position: { left: 58, top: 17 } },
  { id: "plugin-shelf", kind: "shelf", label: "插件架", roomId: "pluginLab", position: { left: 57, top: 79 } },
  { id: "coffee", kind: "coffee", label: "咖啡机", roomId: "lounge", position: { left: 87, top: 26 } },
  { id: "treadmill", kind: "treadmill", label: "健身角", roomId: "lounge", position: { left: 88, top: 57 } },
  { id: "sofa", kind: "sofa", label: "短休沙发", roomId: "lounge", position: { left: 88, top: 78 } },
];

export const courierRoute: CourierRoute = {
  start: { left: 10, top: 72 },
  stops: [
    { left: 32, top: 63 },
    { left: 67, top: 29 },
    { left: 66, top: 72 },
    { left: 73, top: 72 },
    { left: 10, top: 72 },
  ],
  labels: ["取件", "分析", "验证", "插件", "产品确认", "返回"],
};

export const agents: Agent[] = [
  {
    id: "supervisor",
    code: "主管A",
    name: "主管A",
    role: "规则监管主管",
    status: "idle",
    description: "接收预设规则集，持续监管规则流转。",
    color: "#1677ff",
    roomId: "manager",
    workstation: { left: 39, top: 26 },
    accessory: "badge",
  },
  {
    id: "courier",
    code: "快递B",
    name: "快递B",
    role: "数据快递员",
    status: "idle",
    description: "上传 pcap/csv 数据目录，向后续工位反复派送数据包。",
    color: "#f5c400",
    roomId: "corridor",
    workstation: courierRoute.start,
    accessory: "parcel",
  },
  {
    id: "analyst",
    code: "员工C",
    name: "数据分析员工C",
    role: "数据分析",
    status: "analyzing",
    description: "分析数据中的隐含约束和异常模式。",
    color: "#28c76f",
    roomId: "operations",
    workstation: { left: 36, top: 63 },
    accessory: "chart",
  },
  {
    id: "validator",
    code: "员工D",
    name: "规则集验证员工D",
    role: "规则验证",
    status: "validating",
    description: "用样例和反例验证规则集是否稳定。",
    color: "#18b7c8",
    roomId: "validation",
    workstation: { left: 67, top: 31 },
    accessory: "shield",
  },
  {
    id: "plugin",
    code: "员工E",
    name: "规则插件制作员工E",
    role: "插件打包",
    status: "building",
    description: "把验证通过的规则集封装成可嵌入插件。",
    color: "#7c3cff",
    roomId: "pluginLab",
    workstation: { left: 60, top: 74 },
    accessory: "package",
  },
  {
    id: "pm",
    code: "员工F",
    name: "产品经理员工F",
    role: "受控模型沟通",
    status: "reviewing",
    description: "展示嵌入规则后大模型的受约束输出。",
    color: "#ff4b3e",
    roomId: "pluginLab",
    workstation: { left: 74, top: 74 },
    accessory: "chat",
  },
];

export const seedRuleSet: RuleSet = {
  id: "ruleset-demo",
  name: "实时输出约束规则集 v0.3",
  source: "demo/preset-rules.yaml",
  constraints: [
    "输出前必须检查规则冲突",
    "涉及敏感数据时优先给出脱敏版本",
    "所有结论必须标注依据来源",
    "模型不能越过已验证规则集给出承诺",
  ],
  validationStatus: "pending",
};

// 规则集按「组」组织：财务组、网络组、输出约束组（可查看、启停、组内新建、加新组）
export const seedRuleGroups: RuleGroup[] = [
  {
    id: "finance",
    name: "财务规则组",
    domain: "财务",
    rules: [
      { id: "R01", text: "资产 = 负债 + 所有者权益", type: "恒等式", enabled: true, source: "preset" },
      { id: "R02", text: "毛利 = 营收 - 销货成本", type: "恒等式", enabled: true, source: "preset" },
      { id: "R03", text: "期末存货 = 期初存货 + 采购 - 销货成本", type: "恒等式", enabled: true, source: "preset" },
      { id: "R04", text: "存货周转应落在行业分位区间内", type: "范围", enabled: true, source: "preset" },
    ],
  },
  {
    id: "network",
    name: "网络规则组",
    domain: "网络",
    rules: [
      { id: "N01", text: "UDP 流必须为无标志位（noflags）", type: "蕴含", enabled: true, source: "preset" },
      { id: "N02", text: "单流字节数不超过物理链路上界", type: "范围", enabled: true, source: "preset" },
      { id: "N03", text: "SYN 包必含 TCP 标志位", type: "蕴含", enabled: false, source: "preset" },
    ],
  },
  {
    id: "output",
    name: "输出约束组",
    domain: "通用",
    rules: [
      { id: "C01", text: "输出前必须检查规则冲突", type: "约束", enabled: true, source: "preset" },
      { id: "C02", text: "涉及敏感数据时优先脱敏", type: "约束", enabled: true, source: "preset" },
      { id: "C03", text: "所有结论必须标注依据来源", type: "约束", enabled: true, source: "preset" },
    ],
  },
];

// 员工D 从上传数据「自发现」候选规则组（NetNomos 式规则挖掘的演示）。
// 按数据域给网络/财务两套候选；疑似巧合项默认不启用、待人工勾选确认。
export function buildDiscoveredGroup(dataName: string, kind: DataSource["kind"]): RuleGroup {
  const isFinance = kind === "xlsx" || kind === "pdf";
  const rules: RuleItem[] = isFinance
    ? [
        { id: "D01", text: "GrossProfit = Revenue - COGS", type: "恒等式", enabled: true, source: "learned", confidence: 0.99 },
        { id: "D02", text: "TotalAssets = TotalLiabilities + TotalEquity", type: "恒等式", enabled: true, source: "learned", confidence: 0.98 },
        { id: "D03", text: "Inventory_End = Inventory_Begin + Purchases - COGS", type: "恒等式", enabled: true, source: "learned", confidence: 0.96 },
        { id: "D04", text: "应收/营收 落在 [120, 3800] bp 区间", type: "范围", enabled: true, source: "learned", confidence: 0.84 },
        { id: "D05", text: "NetProfit 末位恒为偶数", type: "约束", enabled: false, source: "learned", confidence: 0.41, coincidence: true },
      ]
    : [
        { id: "D01", text: "Proto=UDP → Flags=noflags", type: "蕴含", enabled: true, source: "learned", confidence: 0.99 },
        { id: "D02", text: "Bytes ≤ 1514 × Packets（MTU 上界）", type: "范围", enabled: true, source: "learned", confidence: 0.95 },
        { id: "D03", text: "Proto=TCP ∧ Flags 含 S → Packets ≥ 1", type: "蕴含", enabled: true, source: "learned", confidence: 0.92 },
        { id: "D04", text: "Duration ∈ [0, 86400] 秒", type: "范围", enabled: true, source: "learned", confidence: 0.87 },
        { id: "D05", text: "SrcPort=53 → Proto=UDP", type: "蕴含", enabled: false, source: "learned", confidence: 0.36, coincidence: true },
      ];
  return {
    id: isFinance ? "disc-finance" : "disc-network",
    name: isFinance ? "自发现规则组（财务）" : "自发现规则组（网络）",
    domain: isFinance ? "财务" : "网络",
    discovered: true,
    from: dataName,
    rules,
  };
}

// 数据源（预置 + 已上传）
export const seedDataSources: DataSource[] = [
  { id: "ds-cidds", name: "cidds_wk2_normal_10k.csv", kind: "csv", meta: "10,000 行 NetFlow", status: "已加载", source: "preset" },
  { id: "ds-fin", name: "华信咨询_待审资料包.xlsx", kind: "xlsx", meta: "8 期财务报表", status: "已加载", source: "preset" },
  { id: "ds-pcap", name: "netflix_capture.pcap", kind: "pcap", meta: "≈ 4.2 MB", status: "待处理", source: "preset" },
];

// 产出物（按员工产生的文档/制品）
export const seedArtifacts: Artifact[] = [
  {
    id: "art-cards",
    title: "规则卡集（财务 R01–R04）",
    producer: "validator",
    kind: "规则卡",
    time: "09:32",
    preview:
      "R01 资产 = 负债 + 所有者权益\n  依据：会计基本恒等式\n  判定：keep（强约束）\n\nR02 毛利 = 营收 - 销货成本\n  依据：利润表勾稽\n  判定：keep",
  },
  {
    id: "art-validate",
    title: "勾稽校验报告.md",
    producer: "validator",
    kind: "验证报告",
    time: "09:40",
    preview:
      "# 校验报告\n违规命中：5 处\n- COGS 应为 2000（=10000+4000-12000）\n- 资产负债未配平：差 300\n满足率：92.3%",
  },
  {
    id: "art-plugin",
    title: "rule_guard_v03.zip",
    producer: "plugin",
    kind: "插件包",
    time: "09:48",
    preview:
      "封装规则集 → 可嵌入插件\n包含：财务组 R01–R04 + 输出约束 C01–C03\n入口：guard.validate(record) -> violations[]",
  },
  {
    id: "art-dual",
    title: "双轨对比报告.html",
    producer: "plugin",
    kind: "双轨报告",
    time: "09:55",
    preview:
      "A 轨（裸模型）：照抄错误，标红 5 处\nB 轨（受约束）：槽位回填修正，终检通过\n记分卡：检出 5/5 · 数字冲突 0",
  },
  {
    id: "art-chat",
    title: "合规问答留痕",
    producer: "pm",
    kind: "对话留痕",
    time: "10:02",
    preview:
      "Q：涉及敏感数据该如何回答？\nA：【规则约束输出】先给规则依据，再给可执行步骤，最后标注需验证的数据接口。",
  },
];

export const initialEvents: WorkflowEvent[] = [
  {
    id: "evt-1",
    time: "09:20",
    agent: "supervisor",
    stage: "待接入",
    status: "pending",
    description: "等待主管A上传预设规则集。",
  },
  {
    id: "evt-2",
    time: "09:21",
    agent: "courier",
    stage: "待派送",
    status: "pending",
    description: "快递B在门外等待 pcap/csv 数据目录。",
  },
  {
    id: "evt-3",
    time: "09:22",
    agent: "analyst",
    stage: "分析准备",
    status: "running",
    description: "员工C已加载规则发现模板。",
  },
  {
    id: "evt-4",
    time: "09:23",
    agent: "validator",
    stage: "验证准备",
    status: "pending",
    description: "员工D等待候选规则。",
  },
];

export const conversations: Conversation[] = [
  {
    id: "group",
    title: "规则办公室工作群",
    subtitle: "6 名成员，规则流转同步",
  },
  {
    id: "supervisor",
    title: "主管A",
    subtitle: "规则监管主管",
    avatarAgent: "supervisor",
  },
  {
    id: "courier",
    title: "快递B",
    subtitle: "数据快递员",
    avatarAgent: "courier",
  },
  {
    id: "analyst",
    title: "数据分析员工C",
    subtitle: "规则发现与数据解释",
    avatarAgent: "analyst",
  },
  {
    id: "validator",
    title: "规则验证员工D",
    subtitle: "样例、反例和回归测试",
    avatarAgent: "validator",
  },
  {
    id: "plugin",
    title: "规则插件制作员工E",
    subtitle: "插件打包与嵌入",
    avatarAgent: "plugin",
  },
  {
    id: "pm",
    title: "产品经理员工F",
    subtitle: "受规则约束的大模型输出",
    avatarAgent: "pm",
  },
];

export const initialMessages: ChatMessage[] = [
  {
    id: "msg-1",
    conversationId: "group",
    sender: "supervisor",
    content: "预设规则集还未接入，先保持各工位待命。",
    time: "09:20",
  },
  {
    id: "msg-2",
    conversationId: "group",
    sender: "analyst",
    content: "规则发现模板已加载，等待快递B投递 pcap/csv 数据目录。",
    time: "09:21",
  },
  {
    id: "msg-3",
    conversationId: "pm",
    sender: "pm",
    content: "我是接入规则集后的模型出口。你可以发送一个产品问题，我会用规则约束格式回复。",
    time: "09:24",
    constrained: true,
  },
  {
    id: "msg-4",
    conversationId: "supervisor",
    sender: "supervisor",
    content: "双击我的主管办公室形象上传预设规则集，我会进入监管状态。",
    time: "09:24",
  },
  {
    id: "msg-5",
    conversationId: "courier",
    sender: "courier",
    content: "双击我上传数据目录。开始派送后，再双击我可以打开抓包工作台。",
    time: "09:24",
  },
];

export const packetRows: PacketRecord[] = [
  {
    id: 348,
    time: "65.242532",
    source: "192.168.0.21",
    destination: "rules.local",
    protocol: "DNS",
    length: 77,
    info: "Standard query A rule-registry.internal",
    sourceFormat: "pcap",
    raw: { frame: 348, format: "pcap", service: "rule-registry" },
    tree: [
      "Frame 348: 77 bytes on wire",
      "Ethernet II, Src: Courier_B, Dst: Supervisor_A",
      "Internet Protocol Version 4, Src: 192.168.0.21",
      "Domain Name System (query)",
      "Queries: rule-registry.internal: type A, class IN",
    ],
    hex: "00 15 00 35 84 f4 01 c7 83 3f 21 88 01 00 00 01 00 00 00 00 00 00 0d 72 75 6c 65 2d 72 65 67",
  },
  {
    id: 349,
    time: "65.276870",
    source: "rules.local",
    destination: "192.168.0.21",
    protocol: "DNS",
    length: 489,
    info: "Standard query response A rule-registry.internal CNAME api.rules.local",
    sourceFormat: "pcap",
    raw: { frame: 349, format: "pcap", answerRRs: 4 },
    tree: [
      "Frame 349: 489 bytes captured",
      "Domain Name System (response)",
      "Transaction ID: 0x2188",
      "Answer RRs: 4",
      "Additional RRs: 9",
    ],
    hex: "00 15 00 35 84 f4 01 c7 83 3f 21 88 81 80 00 01 00 04 00 00 00 09 c0 0c 00 05 00 01 00 00",
  },
  {
    id: 350,
    time: "65.297599",
    source: "192.168.0.21",
    destination: "10.0.4.88",
    protocol: "TCP",
    length: 74,
    info: "37063 -> 8080 [SYN] Seq=0 Win=5840 Len=0 MSS=1460",
    sourceFormat: "pcap",
    raw: { frame: 350, format: "pcap", srcPort: 37063, dstPort: 8080 },
    tree: [
      "Transmission Control Protocol",
      "Src Port: 37063, Dst Port: 8080",
      "Flags: 0x002 (SYN)",
      "Window size value: 5840",
    ],
    hex: "45 00 00 3c 1c 46 40 00 40 06 b1 e6 c0 a8 00 15 0a 00 04 58 90 c7 1f 90 00 00 00 00",
  },
  {
    id: 351,
    time: "65.298396",
    source: "10.0.4.88",
    destination: "192.168.0.21",
    protocol: "TLS",
    length: 66,
    info: "Server Hello, Certificate, Encrypted Extensions",
    sourceFormat: "pcap",
    raw: { frame: 351, format: "pcap", tlsVersion: "1.3" },
    tree: [
      "Transport Layer Security",
      "TLSv1.3 Record Layer: Handshake Protocol",
      "Handshake Protocol: Server Hello",
      "Rule plugin channel negotiated",
    ],
    hex: "16 03 03 00 7a 02 00 00 76 03 03 ab 4e 11 08 7b 91 0c 73 65 72 76 65 72 2d 68 65 6c 6f",
  },
  {
    id: 352,
    time: "65.318730",
    source: "192.168.0.21",
    destination: "10.0.4.88",
    protocol: "HTTP",
    length: 153,
    info: "POST /rules/validate HTTP/1.1",
    sourceFormat: "csv",
    raw: { row: 17, format: "csv", endpoint: "/rules/validate" },
    tree: [
      "CSV normalized row 17",
      "Hypertext Transfer Protocol",
      "POST /rules/validate HTTP/1.1",
      "Content-Type: application/json",
      "Payload: candidate_ruleset",
    ],
    hex: "50 4f 53 54 20 2f 72 75 6c 65 73 2f 76 61 6c 69 64 61 74 65 20 48 54 54 50 2f 31 2e 31",
  },
  {
    id: 353,
    time: "65.327810",
    source: "10.0.4.88",
    destination: "plugin.builder",
    protocol: "PLUGIN",
    length: 1514,
    info: "RuleSet passed, package plugin artifact rule_guard_v03.zip",
    sourceFormat: "csv",
    raw: { row: 18, format: "csv", artifact: "rule_guard_v03.zip" },
    tree: [
      "CSV normalized row 18",
      "Rule Plugin Builder Protocol",
      "Stage: package",
      "Artifact: rule_guard_v03.zip",
      "Status: passed with constraints",
    ],
    hex: "52 55 4c 45 2d 47 55 41 52 44 20 76 30 2e 33 20 50 41 43 4b 41 47 45 44 20 4f 4b",
  },
  {
    id: 354,
    time: "65.351002",
    source: "plugin.builder",
    destination: "pm.console",
    protocol: "PLUGIN",
    length: 620,
    info: "Controlled model outlet refreshed with validated constraints",
    sourceFormat: "csv",
    raw: { row: 19, format: "csv", status: "constrained-output-ready" },
    tree: [
      "CSV normalized row 19",
      "Plugin Runtime Event",
      "Outlet: Product Manager F",
      "Constraint policy: source-first, desensitize-first",
    ],
    hex: "43 4f 4e 53 54 52 41 49 4e 45 44 20 4f 55 54 50 55 54 20 52 45 41 44 59",
  },
];

export const agentNameMap = Object.fromEntries(
  agents.map((agent) => [agent.id, agent.name])
) as Record<string, string>;
