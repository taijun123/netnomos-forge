import type {
  AgentSeat,
  CourierWaypoint,
  Doorway,
  FurnitureItem,
  OfficeAsset,
  RoomLayout,
} from "../types/domain";

// 真实 PBR 材质（Poly Haven CC0，已下载到本地）
export const officeAssets: OfficeAsset[] = [
  { key: "woodDiff", path: "/assets/textures/wood_diff.jpg" },
  { key: "woodNor", path: "/assets/textures/wood_nor.jpg" },
  { key: "woodRough", path: "/assets/textures/wood_rough.jpg" },
  { key: "tileDiff", path: "/assets/textures/tile_diff.jpg" },
  { key: "tileNor", path: "/assets/textures/tile_nor.jpg" },
  { key: "tileRough", path: "/assets/textures/tile_rough.jpg" },
];

// 建筑外壳：x ∈ [-4.6, 7.0]，z ∈ [-3.9, 3.9]；门外收发区在建筑左侧
export const rooms3d: RoomLayout[] = [
  {
    id: "corridor",
    name: "门外收发区",
    label: "门外",
    center: { x: -5.9, z: 1.9 },
    size: { width: 2.2, depth: 3.2 },
    floor: "tile",
  },
  {
    id: "manager",
    name: "主管办公室",
    label: "主管室",
    center: { x: -2.6, z: -2.55 },
    size: { width: 4.0, depth: 2.7 },
    floor: "wood",
  },
  {
    id: "validation",
    name: "规则验证区",
    label: "验证区",
    center: { x: 1.8, z: -2.55 },
    size: { width: 4.8, depth: 2.7 },
    floor: "wood",
  },
  {
    id: "operations",
    name: "数据分析区",
    label: "分析区",
    center: { x: -2.1, z: 1.35 },
    size: { width: 5.0, depth: 5.1 },
    floor: "wood",
  },
  {
    id: "pluginLab",
    name: "插件制作间",
    label: "插件间",
    center: { x: 2.3, z: 1.35 },
    size: { width: 3.8, depth: 5.1 },
    floor: "wood",
  },
  {
    id: "lounge",
    name: "共享休息区",
    label: "休息区",
    center: { x: 5.6, z: 0 },
    size: { width: 2.8, depth: 7.8 },
    floor: "wood",
  },
];

export const doorways3d: Doorway[] = [
  { id: "front", from: "corridor", to: "operations", position: { x: -4.6, z: 1.9 }, width: 1.0, rotation: Math.PI / 2 },
  { id: "manager-door", from: "manager", to: "operations", position: { x: -1.4, z: -1.2 }, width: 0.9, rotation: 0 },
  { id: "validation-door", from: "validation", to: "operations", position: { x: -0.1, z: -1.2 }, width: 0.85, rotation: 0 },
  { id: "plugin-top-door", from: "validation", to: "pluginLab", position: { x: 2.4, z: -1.2 }, width: 0.9, rotation: 0 },
  { id: "plugin-door", from: "operations", to: "pluginLab", position: { x: 0.4, z: 1.6 }, width: 0.95, rotation: Math.PI / 2 },
  { id: "lounge-door", from: "pluginLab", to: "lounge", position: { x: 4.2, z: 0.9 }, width: 0.9, rotation: Math.PI / 2 },
];

export const furniture3d: FurnitureItem[] = [
  // —— 主管办公室 ——
  { id: "manager-rug", kind: "rug", roomId: "manager", position: { x: -2.8, z: -2.5 }, size: { width: 2.5, depth: 1.8 }, rotation: 0 },
  { id: "manager-desk", kind: "desk", roomId: "manager", position: { x: -2.8, z: -3.0 }, size: { width: 1.7, depth: 0.9 }, rotation: 0 },
  { id: "manager-shelf", kind: "bookshelf", roomId: "manager", position: { x: -4.25, z: -2.4 }, size: { width: 0.45, depth: 1.6 }, rotation: 0 },
  { id: "manager-plant", kind: "plant", roomId: "manager", position: { x: -0.95, z: -3.4 }, size: { width: 0.5, depth: 0.5 }, rotation: 0 },

  // —— 数据分析区（开放办公）——
  { id: "analyst-desk", kind: "desk", roomId: "operations", position: { x: -2.7, z: 0.55 }, size: { width: 1.5, depth: 0.9 }, rotation: 0 },
  { id: "meeting", kind: "meetingTable", roomId: "operations", position: { x: -0.95, z: 2.95 }, size: { width: 2.0, depth: 1.0 }, rotation: 0 },
  { id: "ops-server", kind: "server", roomId: "operations", position: { x: -4.05, z: -0.45 }, size: { width: 0.7, depth: 1.1 }, rotation: Math.PI / 2 },
  { id: "ops-plant", kind: "plant", roomId: "operations", position: { x: -4.15, z: 3.35 }, size: { width: 0.5, depth: 0.5 }, rotation: 0 },
  { id: "ops-doormat", kind: "doormat", roomId: "operations", position: { x: -4.1, z: 1.9 }, size: { width: 0.7, depth: 1.1 }, rotation: 0 },

  // —— 规则验证区 ——
  { id: "validator-desk", kind: "desk", roomId: "validation", position: { x: 1.6, z: -3.0 }, size: { width: 1.5, depth: 0.9 }, rotation: 0 },
  { id: "validation-shelf", kind: "shelf", roomId: "validation", position: { x: 3.5, z: -3.4 }, size: { width: 1.1, depth: 0.5 }, rotation: 0 },
  { id: "validation-plant", kind: "plant", roomId: "validation", position: { x: -0.05, z: -3.4 }, size: { width: 0.5, depth: 0.5 }, rotation: 0 },

  // —— 插件制作间（E 与 F）——
  { id: "plugin-desk", kind: "desk", roomId: "pluginLab", position: { x: 1.5, z: 0.55 }, size: { width: 1.4, depth: 0.88 }, rotation: 0 },
  { id: "pm-desk", kind: "desk", roomId: "pluginLab", position: { x: 3.15, z: 0.55 }, size: { width: 1.4, depth: 0.88 }, rotation: 0 },
  { id: "plugin-packages", kind: "package", roomId: "pluginLab", position: { x: 1.2, z: 3.2 }, size: { width: 0.95, depth: 0.75 }, rotation: 0 },
  { id: "plugin-plant", kind: "plant", roomId: "pluginLab", position: { x: 3.7, z: 3.35 }, size: { width: 0.5, depth: 0.5 }, rotation: 0 },

  // —— 共享休息区 ——
  { id: "lounge-rug", kind: "rug", roomId: "lounge", position: { x: 5.6, z: -2.0 }, size: { width: 2.2, depth: 2.6 }, rotation: 0 },
  { id: "sofa", kind: "sofa", roomId: "lounge", position: { x: 5.6, z: -2.7 }, size: { width: 1.6, depth: 0.85 }, rotation: 0 },
  { id: "coffee-table", kind: "coffeeTable", roomId: "lounge", position: { x: 5.6, z: -1.55 }, size: { width: 0.95, depth: 0.5 }, rotation: 0 },
  { id: "coffee", kind: "coffee", roomId: "lounge", position: { x: 6.5, z: 0.65 }, size: { width: 0.65, depth: 0.72 }, rotation: -Math.PI / 2 },
  { id: "treadmill", kind: "treadmill", roomId: "lounge", position: { x: 5.55, z: 2.55 }, size: { width: 0.8, depth: 1.5 }, rotation: 0 },
  { id: "lounge-plant-a", kind: "plant", roomId: "lounge", position: { x: 4.75, z: 3.4 }, size: { width: 0.55, depth: 0.55 }, rotation: 0 },
  { id: "lounge-plant-b", kind: "plant", roomId: "lounge", position: { x: 6.5, z: -3.4 }, size: { width: 0.5, depth: 0.5 }, rotation: 0 },

  // —— 门外收发区 ——
  { id: "corridor-package", kind: "package", roomId: "corridor", position: { x: -6.35, z: 2.7 }, size: { width: 0.85, depth: 0.65 }, rotation: 0.2 },
  { id: "corridor-doormat", kind: "doormat", roomId: "corridor", position: { x: -5.05, z: 1.9 }, size: { width: 0.65, depth: 1.05 }, rotation: 0 },
];

// 座位：rotation 0 = 面向 -z（看向桌面/显示器），与桌沿留出安全距离避免穿模
export const agentSeats3d: AgentSeat[] = [
  { agentId: "supervisor", position: { x: -2.8, z: -2.0 }, rotation: 0, pose: "supervising", labelOffset: { x: 0, z: 0.66 } },
  { agentId: "courier", position: { x: -5.8, z: 1.9 }, rotation: -Math.PI / 2, pose: "carryingParcel", labelOffset: { x: 0, z: 0.66 } },
  { agentId: "analyst", position: { x: -2.7, z: 1.46 }, rotation: 0, pose: "seatedTyping", labelOffset: { x: 0, z: 0.66 } },
  { agentId: "validator", position: { x: 1.6, z: -2.1 }, rotation: 0, pose: "seatedTyping", labelOffset: { x: 0, z: 0.66 } },
  { agentId: "plugin", position: { x: 1.5, z: 1.44 }, rotation: 0, pose: "seatedTyping", labelOffset: { x: -0.2, z: 0.66 } },
  { agentId: "pm", position: { x: 3.15, z: 1.44 }, rotation: 0, pose: "reviewing", labelOffset: { x: 0.2, z: 0.66 } },
];

// 快递B路线：只在「门外 ↔ 员工C」之间往返交接，不深入办公区
// 重复的航点 = 原地停留（取件/交接动作）
export const courierWaypoints3d: CourierWaypoint[] = [
  { id: "outside", position: { x: -5.8, z: 1.9 }, label: "门外取件" },
  { id: "outside-wait", position: { x: -5.8, z: 1.9 }, label: "整理包裹" },
  { id: "porch", position: { x: -4.95, z: 1.9 }, label: "走向大门" },
  { id: "door", position: { x: -4.3, z: 1.9 }, label: "进门" },
  { id: "handoff", position: { x: -3.55, z: 1.62 }, label: "交给员工C" },
  { id: "handoff-wait", position: { x: -3.55, z: 1.62 }, label: "数据交接" },
  { id: "door-back", position: { x: -4.3, z: 1.9 }, label: "返回大门" },
  { id: "outside-return", position: { x: -5.8, z: 1.9 }, label: "回到门外" },
];
