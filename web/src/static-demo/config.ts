function envFlag(value: unknown): boolean {
  return /^(1|true|yes|on)$/i.test(String(value ?? "").trim());
}

export const STATIC_DEMO = envFlag(import.meta.env.VITE_STATIC_DEMO);

export const STATIC_DEMO_LABEL = "GitHub Pages 静态概念演示";

export const STATIC_DEMO_NOTICE =
  "当前页面不连接 FastAPI 后端，不保存上传文件，不执行真实训练；所有 workflow、SSE、报告和问答均由前端静态样例复刻。";
