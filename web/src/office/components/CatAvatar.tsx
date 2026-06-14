// 轻量内联 SVG 猫脸头像（按角色配色），不占用 WebGL 上下文。
// 名册、手机聊天等列表场景复用，替代每实例一个 canvas 的 Agent3D。

export function tintWhite(hex: string, amount: number) {
  const c = hex.replace("#", "");
  const r = parseInt(c.slice(0, 2), 16);
  const g = parseInt(c.slice(2, 4), 16);
  const b = parseInt(c.slice(4, 6), 16);
  const mix = (x: number) => Math.round(x * amount + 255 * (1 - amount));
  return `rgb(${mix(r)}, ${mix(g)}, ${mix(b)})`;
}

interface CatAvatarProps {
  color: string;
  size?: number;
  radius?: number;
}

export function CatAvatar({ color, size = 36, radius = 10 }: CatAvatarProps) {
  return (
    <svg
      viewBox="0 0 36 36"
      width={size}
      height={size}
      aria-hidden="true"
      style={{ display: "block", borderRadius: radius }}
    >
      <rect width="36" height="36" rx={radius} fill={tintWhite(color, 0.2)} />
      <path d="M8 13 L11 4.5 L16.5 11.5 Z" fill="#2f323b" />
      <path d="M28 13 L25 4.5 L19.5 11.5 Z" fill="#2f323b" />
      <path d="M9.5 11.5 L11.3 6.6 L14.4 10.8 Z" fill={color} opacity="0.85" />
      <path d="M26.5 11.5 L24.7 6.6 L21.6 10.8 Z" fill={color} opacity="0.85" />
      <circle cx="18" cy="18.5" r="9.2" fill="#2f323b" />
      <ellipse cx="14.6" cy="17.5" rx="1.7" ry="2.1" fill="#bfe9ff" />
      <ellipse cx="21.4" cy="17.5" rx="1.7" ry="2.1" fill="#bfe9ff" />
      <circle cx="18" cy="20.6" r="0.9" fill="#e8a0ac" />
      <rect x="9.5" y="24.8" width="17" height="3.6" rx="1.8" fill={color} />
    </svg>
  );
}
