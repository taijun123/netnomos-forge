import * as THREE from "three";
import type { Agent, AgentPose } from "../types/domain";

// 趣味活动（叠加在 setPose 几何基底上的加性动作层）
export type CatActivity =
  | "idleBreathe"
  | "typing"
  | "checkPhone"
  | "talking"
  | "coffee"
  | "reviewing"
  | "supervising"
  | "stretch"
  | "packing"
  | "sofaRest";

export interface CatAgentRig {
  root: THREE.Group;
  body: THREE.Mesh;
  head: THREE.Group;
  leftArm: THREE.Group;
  rightArm: THREE.Group;
  leftLeg: THREE.Mesh;
  rightLeg: THREE.Mesh;
  tail: THREE.Group;
  badge: THREE.Mesh;
  parcel: THREE.Mesh;
  screen: THREE.Mesh;
  chair: THREE.Group;
  phone: THREE.Object3D;
  cup: THREE.Object3D;
  paper: THREE.Object3D;
}

// 双色短毛猫：炭灰身体 + 奶白口鼻/胸/爪/耳内/尾尖，配按角色配色的围巾做身份识别。
// 取景为半俯视背影（猫坐办公椅、头耳露在椅背上方），所以体型直立、头大耳朵明显。
const FUR_DARK = "#2f323b"; // 不用纯黑，避免在暗背景里糊成一坨；留出明暗过渡
const FUR_LIGHT = "#f1e8d6"; // 奶白
const INNER_EAR = "#e79aa6"; // 耳内粉
const EYE = "#9be8ff";
const NOSE = "#e8a0ac";
const TAIL_BASE_ROTATION = -0.5;

export function createCatAgentRig(agent: Agent, pose: AgentPose): CatAgentRig {
  // 主体毛发：MeshPhysicalMaterial + sheen 模拟绒毛边缘的柔光，配合场景轮廓光更蓬松
  const fur = new THREE.MeshPhysicalMaterial({
    color: FUR_DARK,
    roughness: 0.78,
    metalness: 0,
    sheen: 1,
    sheenRoughness: 0.85,
    sheenColor: new THREE.Color("#6b7180"),
    clearcoat: 0.18,
    clearcoatRoughness: 0.6,
  });
  const cream = new THREE.MeshStandardMaterial({ color: FUR_LIGHT, roughness: 0.7, metalness: 0 });
  const innerEarMat = new THREE.MeshStandardMaterial({ color: INNER_EAR, roughness: 0.6 });
  const scarfMat = new THREE.MeshStandardMaterial({
    color: agent.color,
    roughness: 0.5,
    metalness: 0.04,
    emissive: new THREE.Color(agent.color),
    emissiveIntensity: 0.22,
  });
  const eye = new THREE.MeshStandardMaterial({
    color: EYE,
    roughness: 0.18,
    emissive: new THREE.Color(EYE),
    emissiveIntensity: 0.9,
  });
  const noseMat = new THREE.MeshStandardMaterial({ color: NOSE, roughness: 0.5 });
  const parcelMat = new THREE.MeshStandardMaterial({ color: "#d6a24e", roughness: 0.66 });

  const isBoss = agent.id === "supervisor";
  const root = new THREE.Group();
  root.userData.agentId = agent.id;

  // 接地软阴影（椭圆），增强落地感
  const shadow = new THREE.Mesh(
    new THREE.CircleGeometry(0.5, 40),
    new THREE.MeshBasicMaterial({ color: "#0a0c12", transparent: true, opacity: 0.16, depthWrite: false })
  );
  shadow.rotation.x = -Math.PI / 2;
  shadow.scale.set(1.0, 0.78, 1);
  shadow.position.y = 0.012;
  root.add(shadow);

  const chair = createChairModel(agent.color, isBoss);
  root.add(chair);

  // —— 身体：下半身（坐垫上的圆臀）+ 上半身（前倾的胸腔）——
  const body = new THREE.Group() as unknown as THREE.Mesh; // 用 Group 承载，但保留 body 句柄给动画
  const haunch = ellipsoid(fur, 0.27, 0.22, 0.30);
  haunch.position.set(0, 0.30, 0.10);
  const chest = ellipsoid(fur, 0.235, 0.27, 0.225);
  chest.position.set(0, 0.49, -0.04);
  chest.rotation.x = -0.18;
  body.add(haunch, chest);
  // 胸前奶白围兜（侧/正面可见）
  const bib = ellipsoid(cream, 0.15, 0.20, 0.08);
  bib.position.set(0, 0.46, -0.21);
  bib.rotation.x = -0.18;
  body.add(bib);
  body.position.set(0, 0, 0);
  root.add(body as unknown as THREE.Object3D);

  // —— 头部 ——
  const head = new THREE.Group();
  const skull = ellipsoid(fur, 0.255, 0.235, 0.24);
  head.add(skull);
  // 双颊绒毛（让脸更圆更萌）
  [-1, 1].forEach((s) => {
    const cheek = ellipsoid(fur, 0.1, 0.12, 0.1);
    cheek.position.set(s * 0.17, -0.04, -0.12);
    head.add(cheek);
  });
  // 口鼻区奶白
  const muzzle = ellipsoid(cream, 0.12, 0.09, 0.1);
  muzzle.position.set(0, -0.06, -0.2);
  head.add(muzzle);
  const nose = ellipsoid(noseMat, 0.028, 0.022, 0.02);
  nose.position.set(0, -0.03, -0.295);
  head.add(nose);

  // 耳朵（外耳炭灰 + 内耳粉），明显外张，是俯视背影的关键剪影
  [-1, 1].forEach((s) => {
    const ear = createEar(fur, innerEarMat);
    ear.position.set(s * 0.165, 0.205, 0.02);
    ear.rotation.set(-0.12, s * 0.32, s * -0.22);
    head.add(ear);
  });

  // 眼睛（侧/正面可见）
  [-1, 1].forEach((s) => {
    const e = new THREE.Mesh(new THREE.SphereGeometry(0.046, 18, 12), eye);
    e.scale.set(0.82, 1.05, 0.6);
    e.position.set(s * 0.105, 0.01, -0.235);
    head.add(e);
  });
  // 胡须
  [-1, 1].forEach((s) => {
    [-0.03, 0.03].forEach((dy) => {
      const w = box(0.18, 0.006, 0.006, cream, s * 0.2, -0.04 + dy, -0.19);
      w.rotation.y = s * 0.28;
      head.add(w);
    });
  });
  head.position.set(0, 0.74, -0.12);
  root.add(head);

  // —— 前肢（爪搭在桌上/摆动）——
  const leftArm = pawGroup(fur, cream);
  const rightArm = pawGroup(fur, cream);
  root.add(leftArm, rightArm);

  // —— 后脚（坐姿前伸的小白袜）——
  const leftLeg = footMesh(fur, cream);
  const rightLeg = footMesh(fur, cream);
  root.add(leftLeg, rightLeg);

  // —— 尾巴：卷曲，带奶白尾尖 ——
  const tail = new THREE.Group();
  const tailArc = new THREE.Mesh(
    new THREE.TorusGeometry(0.24, 0.055, 14, 48, Math.PI * 1.35),
    fur
  );
  tailArc.castShadow = true;
  const tailTip = ellipsoid(cream, 0.07, 0.07, 0.07);
  tailTip.position.set(0.24, 0.24, 0);
  tail.add(tailArc, tailTip);
  tail.rotation.x = Math.PI / 2;
  tail.rotation.z = TAIL_BASE_ROTATION;
  tail.position.set(0.34, 0.22, 0.28);
  root.add(tail);

  // —— 围巾：绕颈一圈 + 垂结（身份识别色）——
  const scarfRing = new THREE.Mesh(new THREE.TorusGeometry(0.2, 0.052, 14, 40), scarfMat);
  scarfRing.rotation.x = Math.PI / 2 - 0.18;
  scarfRing.position.set(0, 0.6, -0.05);
  root.add(scarfRing);
  // badge 句柄 = 围巾垂结（动画里做轻微弹动）
  const badge = new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.16, 0.06), scarfMat);
  badge.position.set(0.04, 0.5, -0.18);
  badge.rotation.z = 0.2;
  badge.castShadow = true;
  root.add(badge);

  // 隐藏的悬浮屏占位（保留句柄给动画循环，不再渲染）
  const screen = new THREE.Mesh(
    new THREE.BoxGeometry(0.01, 0.01, 0.01),
    new THREE.MeshStandardMaterial({ color: "#9ed8ff", transparent: true, opacity: 0 })
  );
  screen.visible = false;
  root.add(screen);

  const parcel = createParcel(parcelMat);
  root.add(parcel);

  // —— 活动道具（默认隐藏，由 activity 显隐）——
  // 手机：挂右爪，屏面朝猫脸
  const phone = new THREE.Group();
  const phoneBody = new THREE.Mesh(
    new THREE.BoxGeometry(0.07, 0.12, 0.012),
    new THREE.MeshStandardMaterial({ color: "#20242c", roughness: 0.4 })
  );
  const phoneScreen = new THREE.Mesh(
    new THREE.PlaneGeometry(0.06, 0.105),
    new THREE.MeshStandardMaterial({ color: "#cfeaff", emissive: new THREE.Color("#5fb2ff"), emissiveIntensity: 0.5 })
  );
  phoneScreen.position.z = 0.007;
  phone.add(phoneBody, phoneScreen);
  phone.position.set(0, 0, -0.26);
  phone.rotation.x = 1.45;
  phone.visible = false;
  rightArm.add(phone);

  // 咖啡杯：挂右爪
  const cup = new THREE.Group();
  const cupBody = new THREE.Mesh(
    new THREE.CylinderGeometry(0.045, 0.04, 0.08, 16),
    new THREE.MeshStandardMaterial({ color: "#f3ead9", roughness: 0.6 })
  );
  const cupHandle = new THREE.Mesh(
    new THREE.TorusGeometry(0.03, 0.012, 8, 16),
    new THREE.MeshStandardMaterial({ color: "#e3d6bf", roughness: 0.6 })
  );
  cupHandle.position.set(0.05, 0, 0);
  cup.add(cupBody, cupHandle);
  cup.position.set(0, -0.02, -0.24);
  cup.visible = false;
  rightArm.add(cup);

  // 文件纸：平放桌前，挂 root
  const paper = new THREE.Group();
  const sheetMat = new THREE.MeshStandardMaterial({ color: "#f4efe2", roughness: 0.8 });
  const sheet1 = new THREE.Mesh(new THREE.PlaneGeometry(0.16, 0.2), sheetMat);
  const sheet2 = new THREE.Mesh(new THREE.PlaneGeometry(0.16, 0.2), sheetMat);
  sheet2.position.set(0.01, 0.004, 0.006);
  const clip = new THREE.Mesh(
    new THREE.BoxGeometry(0.16, 0.012, 0.02),
    new THREE.MeshStandardMaterial({ color: "#3a4250", roughness: 0.5 })
  );
  clip.position.set(0, 0.1, 0.01);
  paper.add(sheet1, sheet2, clip);
  paper.position.set(0, 0.34, -0.28);
  paper.rotation.x = -1.25;
  paper.visible = false;
  root.add(paper);

  // 主管专属：金色皇冠（俯视角可见，一眼是领导）+ 眼镜 + 领带
  if (isBoss) {
    addSupervisorMarkers(head, root);
  }

  addRoleAccessory(agent, root, scarfMat);

  const rig: CatAgentRig = {
    root,
    body: body as unknown as THREE.Mesh,
    head,
    leftArm,
    rightArm,
    leftLeg,
    rightLeg,
    tail,
    badge,
    parcel,
    screen,
    chair,
    phone,
    cup,
    paper,
  };
  setPose(rig, pose);
  return rig;
}

/**
 * 每帧更新：setPose 写几何基底 → applyBreath 常驻呼吸 → 叠加 activity 的加性 delta。
 * fromActivity/toActivity/blend 由 Office3DScene 状态机给出（blend 仅在切段头部淡入）；
 * 不传则按 pose 退化为默认活动（向后兼容旧调用与头像 Agent3D）。
 */
export function updateCatAgentRig(
  rig: CatAgentRig,
  agent: Agent,
  pose: AgentPose,
  time: number,
  active: boolean,
  reduceMotion: boolean,
  fromActivity?: CatActivity,
  toActivity?: CatActivity,
  blend = 0
) {
  setPose(rig, pose);
  applyBreath(rig, time, active, reduceMotion);

  // 行走段：腿臂由专门摆动处理，不叠活动层
  if (pose === "walking") {
    const walk = Math.sin(time * 8.4) * (reduceMotion ? 0.7 : 1);
    rig.leftLeg.position.z = -0.02 + walk * 0.12;
    rig.rightLeg.position.z = -0.02 - walk * 0.12;
    rig.leftArm.rotation.x = walk * 0.5;
    rig.rightArm.rotation.x = -walk * 0.5;
    rig.tail.rotation.z = TAIL_BASE_ROTATION + Math.sin(time * 2.0) * (reduceMotion ? 0.12 : 0.16);
    rig.parcel.visible = agent.id === "courier" || agent.accessory === "package";
    return;
  }

  const ctx = ctxFor(agent);
  const from = fromActivity ?? defaultActivity(pose);
  const to = toActivity ?? from;
  const pf = ACT[from](time, ctx);
  const pt = ACT[to](time, ctx);
  // 本演示核心就是「猫动起来」，故减少动态时只降幅、不归零（否则全部冻结）
  const amp = reduceMotion ? 0.7 : 1;
  addPatch(rig, blend > 0 ? lerpPatch(pf, pt, blend) : pf, amp);

  // 道具显隐：按 blend 阈值取离散 props（布尔不插值），amp>0 才显示
  const pp = (blend < 0.5 ? pf : pt).props ?? {};
  rig.phone.visible = !!pp.phone && amp > 0;
  rig.cup.visible = !!pp.cup && amp > 0;
  rig.paper.visible = !!pp.paper && amp > 0;
  rig.parcel.visible = agent.id === "courier" || agent.accessory === "package" || (!!pp.parcel && amp > 0);
}

// 常驻呼吸基线（root 起伏 / 胸腔缩放 / 头微仰 / 围巾结弹动）；尾巴交给 activity patch。
function applyBreath(rig: CatAgentRig, time: number, active: boolean, reduceMotion: boolean) {
  const breathe = Math.sin(time * (active ? 3.6 : 1.9)) * (reduceMotion ? 0.6 : 1);
  rig.root.position.y = Math.abs(breathe) * (active ? 0.018 : 0.008);
  rig.body.scale.y = 1 + breathe * 0.025;
  rig.head.position.y = 0.74 + breathe * 0.012;
  rig.head.rotation.z = breathe * 0.03;
  rig.badge.scale.set(1, 1 + Math.abs(breathe) * 0.06, 1);
}

function defaultActivity(pose: AgentPose): CatActivity {
  if (pose === "seatedTyping") return "typing";
  if (pose === "reviewing") return "reviewing";
  if (pose === "supervising") return "supervising";
  if (pose === "carryingParcel") return "packing";
  return "idleBreathe";
}

type Ctx = { phase: number; sideSign: number };

function hashPhase(id: string): number {
  let h = 0;
  for (let i = 0; i < id.length; i += 1) h = (h * 31 + id.charCodeAt(i)) >>> 0;
  return (h % 1000) / 1000;
}

function ctxFor(agent: Agent): Ctx {
  return { phase: hashPhase(agent.id), sideSign: agent.id === "pm" ? -1 : 1 };
}

const fract = (x: number) => x - Math.floor(x);
const smoothstep = (x: number) => (x <= 0 ? 0 : x >= 1 ? 1 : x * x * (3 - 2 * x));

interface PartRot {
  rx?: number;
  ry?: number;
  rz?: number;
  x?: number;
  y?: number;
  z?: number;
}
interface Patch {
  head?: { rx?: number; ry?: number; rz?: number };
  leftArm?: PartRot;
  rightArm?: PartRot;
  body?: { rx?: number; ry?: number; sy?: number };
  tail?: { rz?: number };
  legs?: { lz?: number; rz?: number; ly?: number };
  rootDy?: number;
  props?: { phone?: boolean; cup?: boolean; paper?: boolean; parcel?: boolean };
}

// 活动纯函数：返回相对 setPose 基底的【加性 delta】（绝不写绝对值）。
// 幅度刻意放大——半俯视远景下猫很小，需要大动作才看得出在动。
const ACT: Record<CatActivity, (t: number, c: Ctx) => Patch> = {
  idleBreathe: (t, c) => ({
    head: { ry: Math.sin(t * 0.5 + c.phase * 6) * 0.24, rz: Math.sin(t * 0.32 + c.phase * 6) * 0.07 },
    rootDy: Math.abs(Math.sin(t * 1.0 + c.phase)) * 0.02,
    tail: { rz: Math.sin(t * 2.0) * 0.18 },
  }),
  typing: (t, c) => {
    const tap = Math.sin(t * 12 + c.phase * 6);
    const tap2 = Math.sin(t * 12 + c.phase * 6 + Math.PI);
    return {
      leftArm: { rx: tap * 0.26, rz: tap * 0.07, z: Math.max(0, tap) * 0.022 },
      rightArm: { rx: tap2 * 0.26, rz: -tap2 * 0.07, z: Math.max(0, tap2) * 0.022 },
      head: { rx: -0.06 + Math.abs(Math.sin(t * 2.2)) * 0.1, ry: Math.sin(t * 0.7 + c.phase) * 0.12 },
      rootDy: Math.abs(Math.sin(t * 4.4)) * 0.012,
      tail: { rz: Math.sin(t * 9 + c.phase) * 0.1 },
    };
  },
  checkPhone: (t, c) => {
    const p = fract(t / 2.4 + c.phase);
    const e = p < 0.15 ? smoothstep(p / 0.15) : p < 0.88 ? 1 : 1 - smoothstep((p - 0.88) / 0.12);
    const hold = p >= 0.15 && p < 0.88;
    return {
      rightArm: { rx: e * -0.7 + (hold ? Math.sin(t * 4) * 0.06 : 0), rz: e * 0.38, x: e * -0.1, y: e * 0.07, z: e * -0.05 },
      leftArm: { rx: e * 0.24 },
      head: { rx: e * 0.34, ry: e * Math.sin(t * 0.7) * 0.16 },
      rootDy: e * 0.01,
      tail: { rz: Math.sin(t * 1.2) * 0.13 },
      props: { phone: p > 0.12 && p < 0.92 },
    };
  },
  coffee: (t, c) => {
    const p = fract(t / 4 + c.phase);
    const e = p < 0.25 ? smoothstep(p / 0.25) : p < 0.6 ? 1 : p < 0.8 ? 1 - smoothstep((p - 0.6) / 0.2) : 0;
    const sip = p > 0.35 && p < 0.55 ? 1 : 0;
    return {
      rightArm: { rx: e * -0.82, x: e * -0.1, y: e * 0.13 },
      leftArm: { rx: e * -0.5, x: e * 0.08 },
      head: { rx: e * -0.06 + sip * -0.22 },
      tail: { rz: Math.sin(t * 1.0) * 0.1 },
      props: { cup: p > 0.2 && p < 0.65 },
    };
  },
  talking: (t, c) => {
    const s = c.sideSign;
    const g = Math.sin(t * 2.8);
    return {
      body: { ry: Math.max(-0.6, Math.min(0.6, s * (0.5 + Math.sin(t * 0.5) * 0.12))) },
      head: { ry: s * (0.5 + Math.sin(t * 0.9) * 0.2), rx: Math.sin(t * 2.8) * 0.09, rz: Math.sin(t * 3.1) * 0.06 },
      rightArm: { rx: 0.45 + g * 0.55, rz: 0.22 + g * 0.22 },
      rootDy: Math.abs(Math.sin(t * 2.8)) * 0.012,
      tail: { rz: Math.sin(t * 3.0) * 0.2 },
    };
  },
  reviewing: (t) => {
    const turn = Math.sin(t * 1.7);
    return {
      head: { ry: Math.sin(t * 1.2) * 0.3, rx: -0.12 + Math.sin(t * 0.9) * 0.07 + Math.max(0, Math.sin(t * 0.5)) * 0.07 },
      rightArm: { rx: 0.45 + turn * 0.4, rz: Math.max(0, turn) * 0.22 },
      leftArm: { rx: 0.12 },
      tail: { rz: Math.sin(t * 1.4) * 0.09 },
      props: { paper: true },
    };
  },
  supervising: (t) => ({
    head: { ry: Math.sin(t * 0.7) * 0.45, rx: Math.sin(t * 0.5) * 0.08 },
    body: { rx: -0.05, ry: Math.sin(t * 0.7) * 0.14 },
    leftArm: { rx: Math.sin(t * 0.8) * 0.05 },
    rightArm: { rx: -Math.sin(t * 0.8) * 0.05 },
    tail: { rz: Math.sin(t * 1.4) * 0.12 },
  }),
  stretch: (t, c) => {
    const p = fract(t / 5.5 + c.phase);
    const e = p < 0.35 ? Math.sin((p / 0.35) * Math.PI) : 0;
    return {
      leftArm: { rx: -1.85 * e, rz: 0.42 * e },
      rightArm: { rx: -1.85 * e, rz: -0.42 * e },
      body: { rx: -0.24 * e, sy: 0.07 * e },
      head: { rx: 0.3 * e },
      rootDy: 0.055 * e,
      tail: { rz: 0.5 * e + Math.sin(t * 8) * 0.07 * e },
    };
  },
  packing: (t) => {
    const pat = Math.sin(t * 7);
    return {
      leftArm: { rx: -0.1 + Math.max(0, pat) * 0.7, z: Math.max(0, pat) * 0.03 },
      rightArm: { rx: -0.1 + Math.max(0, -pat) * 0.7, z: Math.max(0, -pat) * 0.03 },
      head: { rx: 0.2 },
      body: { rx: 0.12 + Math.abs(pat) * 0.04 },
      rootDy: Math.abs(pat) * 0.014,
      tail: { rz: Math.sin(t * 7) * 0.1 },
    };
  },
  // 躺沙发休息：身体后仰、双爪松垮搭着、头偶尔点、慢悠悠摆尾
  sofaRest: (t, c) => ({
    body: { rx: 0.24 },
    head: { rx: 0.14 + Math.sin(t * 0.6 + c.phase) * 0.05, rz: Math.sin(t * 0.4) * 0.05 },
    leftArm: { rx: 0.4, rz: -0.16 },
    rightArm: { rx: 0.4, rz: 0.16 },
    rootDy: Math.abs(Math.sin(t * 0.9 + c.phase)) * 0.008,
    tail: { rz: Math.sin(t * 1.0) * 0.12 },
  }),
};

const lerpN = (a: number | undefined, b: number | undefined, t: number) => (a ?? 0) + ((b ?? 0) - (a ?? 0)) * t;

function lerpPart(a: PartRot | undefined, b: PartRot | undefined, t: number): PartRot {
  return {
    rx: lerpN(a?.rx, b?.rx, t),
    ry: lerpN(a?.ry, b?.ry, t),
    rz: lerpN(a?.rz, b?.rz, t),
    x: lerpN(a?.x, b?.x, t),
    y: lerpN(a?.y, b?.y, t),
    z: lerpN(a?.z, b?.z, t),
  };
}

function lerpPatch(a: Patch, b: Patch, t: number): Patch {
  return {
    head: { rx: lerpN(a.head?.rx, b.head?.rx, t), ry: lerpN(a.head?.ry, b.head?.ry, t), rz: lerpN(a.head?.rz, b.head?.rz, t) },
    leftArm: lerpPart(a.leftArm, b.leftArm, t),
    rightArm: lerpPart(a.rightArm, b.rightArm, t),
    body: { rx: lerpN(a.body?.rx, b.body?.rx, t), ry: lerpN(a.body?.ry, b.body?.ry, t), sy: lerpN(a.body?.sy, b.body?.sy, t) },
    tail: { rz: lerpN(a.tail?.rz, b.tail?.rz, t) },
    legs: { lz: lerpN(a.legs?.lz, b.legs?.lz, t), rz: lerpN(a.legs?.rz, b.legs?.rz, t), ly: lerpN(a.legs?.ly, b.legs?.ly, t) },
    rootDy: lerpN(a.rootDy, b.rootDy, t),
  };
}

function applyArm(arm: THREE.Group, p: PartRot | undefined, amp: number) {
  if (!p) return;
  arm.rotation.x += (p.rx ?? 0) * amp;
  arm.rotation.z += (p.rz ?? 0) * amp;
  arm.position.x += (p.x ?? 0) * amp;
  arm.position.y += (p.y ?? 0) * amp;
  arm.position.z += (p.z ?? 0) * amp;
}

function addPatch(rig: CatAgentRig, p: Patch, amp: number) {
  if (p.head) {
    rig.head.rotation.x += (p.head.rx ?? 0) * amp;
    rig.head.rotation.y += (p.head.ry ?? 0) * amp;
    rig.head.rotation.z += (p.head.rz ?? 0) * amp;
  }
  applyArm(rig.leftArm, p.leftArm, amp);
  applyArm(rig.rightArm, p.rightArm, amp);
  if (p.body) {
    rig.body.rotation.x += (p.body.rx ?? 0) * amp;
    rig.body.rotation.y += (p.body.ry ?? 0) * amp;
    rig.body.scale.y *= 1 + (p.body.sy ?? 0) * amp;
  }
  if (p.tail) rig.tail.rotation.z += (p.tail.rz ?? 0) * amp;
  if (p.legs) {
    rig.leftLeg.position.z += (p.legs.lz ?? 0) * amp;
    rig.rightLeg.position.z += (p.legs.rz ?? 0) * amp;
    rig.leftLeg.position.y += (p.legs.ly ?? 0) * amp;
    rig.rightLeg.position.y += (p.legs.ly ?? 0) * amp;
  }
  if (p.rootDy) rig.root.position.y += p.rootDy * amp;
}

function setPose(rig: CatAgentRig, pose: AgentPose) {
  const seated = pose === "seatedTyping" || pose === "supervising" || pose === "reviewing";
  rig.chair.visible = seated;

  // 几何基底（每帧重写绝对值，activity 在其上做加性 delta）
  rig.body.position.set(0, seated ? 0 : 0.04, 0);
  rig.body.scale.set(1, 1, 1);
  rig.body.rotation.set(0, 0, 0);
  rig.head.position.set(0, 0.74, seated ? -0.12 : -0.15);
  rig.head.rotation.set(0, 0, 0);

  rig.leftArm.position.set(-0.2, 0.42, seated ? -0.28 : -0.16);
  rig.rightArm.position.set(0.2, 0.42, seated ? -0.28 : -0.16);
  rig.leftArm.rotation.set(seated ? -0.9 : -0.2, 0, -0.06);
  rig.rightArm.rotation.set(seated ? -0.9 : -0.2, 0, 0.06);

  rig.leftLeg.position.set(-0.12, 0.12, seated ? 0.26 : -0.02);
  rig.rightLeg.position.set(0.12, 0.12, seated ? 0.26 : -0.02);

  rig.tail.rotation.set(Math.PI / 2, 0, TAIL_BASE_ROTATION);
  rig.tail.position.set(0.34, 0.22, seated ? 0.3 : 0.26);

  if (pose === "supervising") {
    rig.leftArm.rotation.set(-0.7, 0, -0.2);
    rig.rightArm.rotation.set(-0.7, 0, 0.2);
  }

  const holdingParcel = pose === "carryingParcel" || pose === "walking";
  rig.parcel.position.set(0, 0.34, holdingParcel ? -0.32 : 0.42);
  rig.parcel.rotation.set(0, holdingParcel ? 0 : 0.25, 0);
  if (holdingParcel) {
    rig.leftArm.position.set(-0.18, 0.4, -0.28);
    rig.rightArm.position.set(0.18, 0.4, -0.28);
    rig.leftArm.rotation.set(-1.2, 0, -0.1);
    rig.rightArm.rotation.set(-1.2, 0, 0.1);
  }
}

function createEar(fur: THREE.Material, inner: THREE.Material) {
  const ear = new THREE.Group();
  const outer = new THREE.Mesh(new THREE.ConeGeometry(0.12, 0.2, 5), fur);
  outer.scale.set(1, 1, 0.55);
  outer.castShadow = true;
  const innerCone = new THREE.Mesh(new THREE.ConeGeometry(0.07, 0.14, 5), inner);
  innerCone.scale.set(1, 1, 0.45);
  innerCone.position.set(0, -0.01, -0.04);
  ear.add(outer, innerCone);
  return ear;
}

function ellipsoid(material: THREE.Material, x: number, y: number, z: number) {
  const mesh = new THREE.Mesh(new THREE.SphereGeometry(1, 30, 18), material);
  mesh.scale.set(x, y, z);
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  return mesh;
}

function box(width: number, height: number, depth: number, material: THREE.Material, x = 0, y = 0, z = 0) {
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(width, height, depth), material);
  mesh.position.set(x, y, z);
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  return mesh;
}

function pawGroup(fur: THREE.Material, cream: THREE.Material) {
  const group = new THREE.Group();
  const arm = ellipsoid(fur, 0.072, 0.072, 0.2);
  arm.position.z = -0.1;
  const paw = ellipsoid(cream, 0.085, 0.075, 0.09);
  paw.position.z = -0.22;
  group.add(arm, paw);
  return group;
}

function footMesh(fur: THREE.Material, cream: THREE.Material) {
  // 用 Group 当作 Mesh 句柄返回（动画只读写 position）
  const group = new THREE.Group() as unknown as THREE.Mesh;
  const leg = ellipsoid(fur, 0.1, 0.085, 0.16);
  const sock = ellipsoid(cream, 0.09, 0.07, 0.08);
  sock.position.z = -0.12;
  (group as unknown as THREE.Group).add(leg, sock);
  return group;
}

function createParcel(material: THREE.Material) {
  const group = new THREE.Group() as unknown as THREE.Mesh;
  const boxMesh = box(0.32, 0.24, 0.26, material);
  boxMesh.castShadow = true;
  // 十字封箱带
  const tapeMat = new THREE.MeshStandardMaterial({ color: "#b3812f", roughness: 0.6 });
  const t1 = box(0.34, 0.245, 0.05, tapeMat);
  const t2 = box(0.05, 0.245, 0.28, tapeMat);
  (group as unknown as THREE.Group).add(boxMesh, t1, t2);
  return group;
}

function createChairModel(accentColor: string, executive = false) {
  // 行政椅用更深沉的皮质色，普通椅用浅灰，强化领导工位的区分
  const shell = new THREE.MeshStandardMaterial({
    color: executive ? "#2b3344" : "#eef1f5",
    roughness: executive ? 0.42 : 0.5,
    metalness: 0.06,
  });
  const cushion = new THREE.MeshStandardMaterial({
    color: executive ? "#39435a" : "#d7dde6",
    roughness: 0.66,
  });
  const chrome = new THREE.MeshStandardMaterial({ color: "#aab3bf", roughness: 0.3, metalness: 0.7 });
  const accent = new THREE.MeshStandardMaterial({
    color: executive ? "#d9b24e" : accentColor,
    roughness: 0.45,
    metalness: executive ? 0.4 : 0,
    emissive: new THREE.Color(executive ? "#7a5a12" : "#000000"),
    emissiveIntensity: executive ? 0.2 : 0,
  });
  const chair = new THREE.Group();

  // 坐垫
  const seat = new THREE.Mesh(new THREE.CylinderGeometry(0.33, 0.33, 0.1, 24), cushion);
  seat.position.set(0, 0.28, 0.06);
  seat.scale.set(1, 1, 1.04);
  seat.castShadow = true;
  // 靠背：行政椅高背 + 头枕，普通椅中背
  const backH = executive ? 0.64 : 0.46;
  const backY = executive ? 0.66 : 0.56;
  const backShape = new THREE.Mesh(new THREE.BoxGeometry(0.52, backH, 0.1), shell);
  backShape.position.set(0, backY, 0.34);
  backShape.rotation.x = 0.14;
  backShape.castShadow = true;
  chair.add(backShape);
  // 靠背配色描边（行政椅为金色）
  const backTrim = new THREE.Mesh(new THREE.BoxGeometry(0.52, 0.06, 0.11), accent);
  backTrim.position.set(0, backY + backH / 2 - 0.02, 0.32);
  backTrim.rotation.x = 0.14;
  chair.add(backTrim);
  if (executive) {
    // 头枕 + 两侧扶手，强化「老板椅」轮廓
    const headrest = new THREE.Mesh(new THREE.BoxGeometry(0.4, 0.16, 0.1), shell);
    headrest.position.set(0, backY + backH / 2 + 0.08, 0.36);
    headrest.rotation.x = 0.14;
    chair.add(headrest);
    [-1, 1].forEach((s) => {
      const arm = new THREE.Mesh(new THREE.BoxGeometry(0.08, 0.07, 0.34), shell);
      arm.position.set(s * 0.34, 0.4, 0.12);
      chair.add(arm);
    });
  }
  // 中柱
  const post = new THREE.Mesh(new THREE.CylinderGeometry(0.045, 0.045, 0.22, 12), chrome);
  post.position.set(0, 0.14, 0.06);
  // 五星脚（简化为多根交叉）
  const base = new THREE.Group();
  for (let i = 0; i < 5; i++) {
    const leg = new THREE.Mesh(new THREE.BoxGeometry(0.06, 0.04, 0.3), chrome);
    leg.position.set(0, 0.03, 0.06);
    leg.rotation.y = (i / 5) * Math.PI * 2;
    leg.geometry.translate(0, 0, 0.13);
    base.add(leg);
  }
  chair.add(seat, post, base);
  return chair;
}

function addSupervisorMarkers(head: THREE.Group, root: THREE.Group) {
  const gold = new THREE.MeshStandardMaterial({
    color: "#f1c544",
    roughness: 0.32,
    metalness: 0.55,
    emissive: new THREE.Color("#6b4e0a"),
    emissiveIntensity: 0.25,
  });
  const dark = new THREE.MeshStandardMaterial({ color: "#1a1d24", roughness: 0.5 });
  const lens = new THREE.MeshStandardMaterial({
    color: "#bfe6ff",
    roughness: 0.15,
    metalness: 0.1,
    transparent: true,
    opacity: 0.7,
  });

  // —— 皇冠：环 + 五个尖角，戴在头顶（俯视可见）——
  const crown = new THREE.Group();
  const band = new THREE.Mesh(new THREE.CylinderGeometry(0.16, 0.18, 0.07, 20, 1, true), gold);
  crown.add(band);
  for (let i = 0; i < 5; i++) {
    const spike = new THREE.Mesh(new THREE.ConeGeometry(0.035, 0.1, 8), gold);
    const a = (i / 5) * Math.PI * 2;
    spike.position.set(Math.sin(a) * 0.16, 0.07, Math.cos(a) * 0.16);
    crown.add(spike);
    const gem = new THREE.Mesh(new THREE.SphereGeometry(0.018, 10, 8), lens);
    gem.position.set(Math.sin(a) * 0.16, 0.11, Math.cos(a) * 0.16);
    crown.add(gem);
  }
  crown.position.set(0, 0.22, 0.02);
  head.add(crown);

  // —— 眼镜：两片镜框 + 鼻梁（脸前，近景/头像可见）——
  const glasses = new THREE.Group();
  [-1, 1].forEach((s) => {
    const frame = new THREE.Mesh(new THREE.TorusGeometry(0.052, 0.012, 10, 20), dark);
    frame.position.set(s * 0.105, 0.01, -0.23);
    glasses.add(frame);
    const glass = new THREE.Mesh(new THREE.CircleGeometry(0.05, 18), lens);
    glass.position.set(s * 0.105, 0.01, -0.232);
    glasses.add(glass);
  });
  const bridge = new THREE.Mesh(new THREE.BoxGeometry(0.06, 0.012, 0.012), dark);
  bridge.position.set(0, 0.01, -0.23);
  glasses.add(bridge);
  head.add(glasses);

  // —— 领带：深红，挂在颈下胸前 ——
  const tieMat = new THREE.MeshStandardMaterial({ color: "#9c2b33", roughness: 0.5 });
  const knot = new THREE.Mesh(new THREE.BoxGeometry(0.06, 0.06, 0.04), tieMat);
  knot.position.set(0, 0.56, -0.2);
  const blade = new THREE.Mesh(new THREE.ConeGeometry(0.05, 0.2, 4), tieMat);
  blade.rotation.x = Math.PI;
  blade.position.set(0, 0.42, -0.2);
  root.add(knot, blade);
}

function addRoleAccessory(agent: Agent, root: THREE.Group, accent: THREE.Material) {
  if (agent.accessory === "shield") {
    const shield = new THREE.Mesh(new THREE.CylinderGeometry(0.1, 0.115, 0.04, 6), accent);
    shield.position.set(0.3, 0.62, -0.18);
    shield.rotation.set(Math.PI / 2, 0, Math.PI / 6);
    root.add(shield);
  }
  if (agent.accessory === "chart") {
    [-0.09, 0, 0.09].forEach((x, index) => {
      const bar = new THREE.Mesh(new THREE.BoxGeometry(0.05, 0.08 + index * 0.06, 0.05), accent);
      bar.position.set(0.26 + x, 0.62 + index * 0.03, -0.16);
      root.add(bar);
    });
  }
  if (agent.accessory === "chat") {
    const bubble = ellipsoid(accent, 0.1, 0.07, 0.1);
    bubble.position.set(0.3, 0.72, -0.2);
    root.add(bubble);
    const dot = ellipsoid(accent, 0.03, 0.03, 0.03);
    dot.position.set(0.24, 0.62, -0.26);
    root.add(dot);
  }
}
