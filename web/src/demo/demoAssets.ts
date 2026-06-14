// 一键演示：内联两个 demo 资料 CSV（来自 demo_artifacts/w4_demo_assets/*），
// 运行时构造 File 走与真人上传完全相同的 apiClient.uploadDataSource 路径。
// CSV 极小（~1KB/9 行），内联最稳：无需 public 拷贝/网络请求，离线与后端未起也能跑。

export type DemoScenario = "network" | "finance";

export const NETWORK_FILENAME = "netflow_rule_anomaly_upload.csv";
export const FINANCE_FILENAME = "huaxin_audit_package.csv";

export const NETWORK_CSV = [
  "DateFirstSeen,Duration,Proto,SrcIpAddr,SrcPt,DstIpAddr,DstPt,Packets,Bytes,Flows,Flags,Tos,DemoNote",
  "2017-03-23 09:21:12.103,0.003,UDP,192.168.220.8,34358,DNS,53,2,164,1,......,0,clean_dns_udp_baseline",
  "2017-03-23 09:22:45.870,0.004,UDP,192.168.220.12,51413,DNS,53,2,196,1,.AP.SF,0,anomaly_udp_with_tcp_flags",
  "2017-03-23 09:23:02.444,0.310,TCP,192.168.220.16,37922,10082_43,443,1,90000,1,.AP.SF,0,anomaly_bytes_above_packet_upper_bound",
  "2017-03-23 09:24:18.009,0.000,TCP,192.168.220.4,57656,10056_105,443,10,200,1,.A....,0,anomaly_bytes_below_packet_lower_bound",
  "2017-03-23 09:25:33.512,0.002,UDP,192.168.220.14,41608,10081_164,53,2,178,1,......,0,anomaly_dns_port_identity_mismatch",
  "2017-03-23 09:26:01.220,1.840,TCP,192.168.220.5,49152,192.168.100.3,8000,12,6480,1,.AP.SF,0,clean_tcp_application_flow",
  "2017-03-23 09:27:54.781,0.000,UDP,192.168.220.9,137,192.168.220.255,137,1,92,1,......,0,clean_udp_broadcast",
  "2017-03-23 09:28:27.336,0.460,TCP,192.168.210.5,445,192.168.220.15,52174,9,4122,1,.AP.SF,0,clean_tcp_file_service",
].join("\n");

// 财务 CSV 首字节保留 UTF-8 BOM（﻿），与原文件一致。
export const FINANCE_CSV =
  "﻿" +
  [
    "CompanyId,Industry,PeriodIndex,Revenue,COGS,GrossProfit,NetProfit,Purchases,Cash_Begin,Cash_End,Inventory_Begin,Inventory_End,AccountsReceivable,OtherAssets,TotalAssets,TotalLiabilities,TotalEquity,InventoryNetInflow,InventoryToAssetsBp,ReceivableToRevenueBp",
    "HX001,consulting,1,80000,2000,78000,23400,2500,7500,8000,9000,9500,20000,762500,800000,360000,440000,500,119,2500",
    "HX001,consulting,2,82000,2200,79800,24000,2700,8500,8600,9500,10000,20500,768900,808000,363600,444400,500,124,2500",
    "HX001,consulting,3,84000,3000,81000,24600,4000,8600,9200,10000,12000,21000,773800,816000,367200,448800,1000,147,2500",
    "HX001,consulting,4,86000,2400,83600,25100,1900,9200,9800,12000,11500,21500,781200,824000,370800,453200,-500,140,2500",
    "HX001,consulting,5,88000,2500,85500,25700,2800,9800,10900,11500,11800,22000,787800,832500,374400,457600,300,142,2500",
    "HX001,consulting,6,90000,2600,87400,26200,2800,10900,11000,11800,12000,22500,794500,840000,378000,462000,200,143,2500",
    "HX001,consulting,7,96600,2800,93800,28100,3000,11000,11600,12000,12200,84000,740200,848000,381600,466400,200,144,8696",
    "HX001,consulting,8,98000,3000,95000,28500,290400,11600,12200,12200,299600,24500,519700,856000,385200,470800,287400,3500,2500",
  ].join("\n");

// 与 demo_artifacts/w4_demo_assets/*/prompts.md「报告输入框问题」逐字一致
export const NETWORK_QUESTION =
  "请基于我上传的待核查 NetFlow 资料，生成或抽取 10 条 CIDDS 风格记录，并说明哪些记录违反 UDP Flags、Packets/Bytes 物理上下界或 DNS 端口身份规则；同时给出规则约束后的合规版本。";
export const FINANCE_QUESTION =
  "请基于华信咨询待审资料包，生成一份年度财务分析与审阅报告，并指出营业成本、资产负债配平、现金跨期、存货占比和应收增长是否存在异常。";

export function demoQuestion(scenario: DemoScenario): string {
  return scenario === "network" ? NETWORK_QUESTION : FINANCE_QUESTION;
}

export function makeDemoFile(scenario: DemoScenario): File {
  const csv = scenario === "network" ? NETWORK_CSV : FINANCE_CSV;
  const name = scenario === "network" ? NETWORK_FILENAME : FINANCE_FILENAME;
  return new File([csv], name, { type: "text/csv" });
}
