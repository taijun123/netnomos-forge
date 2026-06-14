export type AgentStatus =
  | "idle"
  | "supervising"
  | "delivering"
  | "analyzing"
  | "validating"
  | "building"
  | "reviewing";

export type AgentId =
  | "supervisor"
  | "courier"
  | "analyst"
  | "validator"
  | "plugin"
  | "pm";

export type RoomId =
  | "corridor"
  | "manager"
  | "operations"
  | "validation"
  | "pluginLab"
  | "lounge";

export interface Point {
  left: number;
  top: number;
}

export interface Vec2 {
  x: number;
  z: number;
}

export interface Size2 {
  width: number;
  depth: number;
}

export interface Rect {
  left: number;
  top: number;
  width: number;
  height: number;
}

export interface OfficeRoom {
  id: RoomId;
  name: string;
  label: string;
  purpose: string;
  bounds: Rect;
  tone: "manager" | "work" | "lab" | "lounge" | "corridor";
}

export type OfficePropKind =
  | "coffee"
  | "plant"
  | "treadmill"
  | "door"
  | "server"
  | "whiteboard"
  | "sofa"
  | "shelf";

export interface OfficeProp {
  id: string;
  kind: OfficePropKind;
  label: string;
  roomId: RoomId;
  position: Point;
}

export type AgentPose =
  | "seatedTyping"
  | "supervising"
  | "walking"
  | "carryingParcel"
  | "reviewing";

export interface RoomLayout {
  id: RoomId;
  name: string;
  label: string;
  center: Vec2;
  size: Size2;
  floor: "wood" | "tile" | "carpet" | "corridor";
}

export type FurnitureKind =
  | "desk"
  | "chair"
  | "meetingTable"
  | "sofa"
  | "coffee"
  | "treadmill"
  | "plant"
  | "server"
  | "shelf"
  | "package"
  | "rug"
  | "doormat"
  | "coffeeTable"
  | "bookshelf";

export interface FurnitureItem {
  id: string;
  kind: FurnitureKind;
  roomId: RoomId;
  position: Vec2;
  size: Size2;
  rotation: number;
  assetKey?: string;
}

export interface Doorway {
  id: string;
  from: RoomId;
  to: RoomId;
  position: Vec2;
  width: number;
  rotation: number;
}

export interface AgentSeat {
  agentId: AgentId;
  position: Vec2;
  rotation: number;
  pose: AgentPose;
  labelOffset: Vec2;
}

export interface CourierWaypoint {
  id: string;
  position: Vec2;
  label: string;
}

export interface OfficeAsset {
  key: string;
  path: string;
  atlas?: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
}

export interface Agent {
  id: AgentId;
  code: string;
  name: string;
  role: string;
  status: AgentStatus;
  description: string;
  color: string;
  roomId: RoomId;
  workstation: Point;
  worldPosition?: Vec2;
  pose?: AgentPose;
  accessory: "badge" | "parcel" | "chart" | "shield" | "package" | "chat";
}

export interface CourierRoute {
  start: Point;
  stops: Point[];
  labels: string[];
}

export interface WorkflowEvent {
  id: string;
  time: string;
  agent: AgentId;
  stage: string;
  status: "pending" | "running" | "done" | "blocked";
  description: string;
}

export interface RuleSet {
  id: string;
  name: string;
  source: string;
  constraints: string[];
  validationStatus: "pending" | "validating" | "passed";
}

// 规则库面板用的结构化规则项（可查看 / 启停 / 自行新建 / 自发现候选）
export interface RuleItem {
  id: string;
  text: string;
  type: string; // 约束 / 恒等式 / 范围 / 蕴含 / 比率 / 自定义
  enabled: boolean;
  source: "preset" | "custom" | "learned"; // 预置 / 自建 / 自发现
  confidence?: number; // 自发现规则的支持度/置信度 0~1
  coincidence?: boolean; // 员工D 判定的疑似巧合（建议 drop，默认不启用）
}

// 规则集按「组」组织（财务规则组、网络规则组、自发现组…）
export interface RuleGroup {
  id: string;
  name: string;
  domain: string; // 财务 / 网络 / 通用
  rules: RuleItem[];
  discovered?: boolean; // 由数据自发现产出（员工D）
  from?: string; // 自发现来源数据名
}

// 数据源（预置或已上传），供「数据」视图展示
export interface DataSource {
  id: string;
  name: string;
  kind: "pcap" | "csv" | "xlsx" | "pdf";
  meta: string; // 行数 / 大小 等描述
  status: "已加载" | "待处理";
  source: "preset" | "upload";
}

// 产出物（某员工产生的文档/制品），供「产出物」视图展示
export interface Artifact {
  id: string;
  title: string;
  producer: AgentId; // 产出的员工
  kind: string; // 规则卡 / 验证报告 / 插件包 / 双轨报告 / 对话留痕
  time: string;
  preview: string; // 文档内容预览（多行）
}

export interface ChatMessage {
  id: string;
  conversationId: string;
  sender: "me" | AgentId | "system";
  content: string;
  time: string;
  constrained?: boolean;
}

export interface Conversation {
  id: string;
  title: string;
  subtitle: string;
  avatarAgent?: AgentId;
}

// 协议名为自由字符串（TCP/UDP/DNS/TLSv1.2/HTTP/ARP/ICMP/...），真实解析时由解码器给出
export type PacketProtocol = string;

// 协议详情树：按分层（Frame/Ethernet/IP/TCP/应用层）组织的字段列表
export interface PacketLayer {
  title: string;
  fields: Array<{ name: string; value: string }>;
}

export interface PacketRecord {
  id: number;
  time: string;
  source: string;
  destination: string;
  protocol: PacketProtocol;
  length: number;
  info: string;
  /** 旧版演示数据的纯文本树；真实解析的包使用 layers */
  tree: string[];
  /** 旧版演示数据的 hex 字符串；真实解析的包使用 bytes */
  hex: string;
  sourceFormat: "pcap" | "csv";
  raw: Record<string, string | number>;
  /** 原始帧字节（pcap 解析时为对文件缓冲的视图，零拷贝） */
  bytes?: Uint8Array;
  /** pcap link-layer type，懒解码协议树时需要 */
  linkType?: number;
  /** 绝对时间戳（秒，含小数） */
  epoch?: number;
  /** 预拼好的小写检索文本，加速大文件过滤 */
  searchText?: string;
}

export interface FlowNode {
  id: string;
  label: string;
  kind: "client" | "service" | "agent" | "plugin";
}

export interface FlowEdge {
  id: string;
  source: string;
  destination: string;
  protocol: PacketProtocol;
  packets: number;
  bytes: number;
  firstSeen: string;
  lastSeen: string;
}

export type PacketRow = PacketRecord;
