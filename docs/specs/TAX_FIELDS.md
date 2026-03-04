# 税务管理字段规范（按功能模块）

字段来源：用户上传《税务管理功能中必要的数据字段详细列表》  
- 纳税人基础档案：USCC、纳税人类型、主管税务机关、税种认定、征收方式、高新/小微/出口退税标识、税务数字账户授权等 :contentReference[oaicite:5]{index=5}  
- 进项税：发票唯一标识、价税分拆、税率、发票状态、勾选认证状态、用途确认、进项转出原因/金额、XML路径、风险扫描结果 :contentReference[oaicite:6]{index=6} :contentReference[oaicite:7]{index=7}  
- 销项税：开票申请单号、购买方信息、税收分类编码、货物劳务名称、金额/税额、交付轨迹、红字信息表、纳税义务发生时间 :contentReference[oaicite:8]{index=8}  
- 税金计算与申报：税款所属期、税种、税基、税率/速算扣除、减免、应纳税额、预缴、应补退、申报版本、申报状态/回执、扣款、完税证明 :contentReference[oaicite:9]{index=9} :contentReference[oaicite:10]{index=10}  
- 风险预警：税负率/偏差、进销项品名匹配、红冲率、库存差异、零申报、关联交易占比、纳税信用、风险得分、应对记录 :contentReference[oaicite:11]{index=11}  
- 电子档案合规：元数据包ID、原始格式、验签状态、归档路径、保管期限、借阅记录、监管报送状态 :contentReference[oaicite:12]{index=12}  

---

## 1. 数据结构总原则
- 多法人：company_id（纳税主体）必须出现在纳税人档案、银行扣款、申报主表中
- 多账套：ledger_id 作为账套分区键（可选：若你把税务按 company 管，则 ledger_id 可作为附加维度）
- 电子凭证合规：原始文件（XML/OFD/PDF）路径必须结构化存储；验签状态必须可追溯 :contentReference[oaicite:13]{index=13}

---

## 2. 表清单（核心落地版）
- tax_taxpayers（纳税人档案）
- tax_vat_input_invoices（进项发票）
- tax_vat_output_invoices（销项发票）
- tax_returns（申报主表：税种/所属期/状态/回执/扣款/完税证明） :contentReference[oaicite:14]{index=14}
- tax_calculation_lines（计税明细：税基/税率/减免/应纳等） :contentReference[oaicite:15]{index=15}
- tax_risk_metrics（风险指标）
- tax_archives（电子档案元数据）
- tax_archive_access_logs（借阅记录，系统算） :contentReference[oaicite:16]{index=16}


---

## 3. 申报包与凭证穿透口径（阶段性）
本阶段不做真实税局报送，仅生成“申报数据包（JSON）”用于审计穿透与后续对接：

- 申报包 VAT.vat_payable = 凭证行 `vat_payable` 的净贷方（贷 - 借）
- 申报包 VAT.surtax_total = 凭证行 `surtax_payable` 的净贷方

产物：
- `artifacts/tax_return_pack_YYYYMM_vat.json`
- `artifacts/tax_archive_manifest.json`
