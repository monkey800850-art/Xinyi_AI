# AUXDIM-FIELD-01 辅助核算字段结构级审计（单位/个人/项目/银行账户）

- spec_count: **72**
- model_count: **0**
- db_count: **46**
- missing_in_model_count: **72**
- missing_in_db_count: **70**
- mismatch_count: **0**

## 分维度缺口

### 单位(客户/供应商) (spec=28, source=doc)
- missing_in_model: 28
- missing_in_db: 28

### 个人(员工/往来主体) (spec=17, source=doc)
- missing_in_model: 17
- missing_in_db: 16

### 银行账户 (spec=17, source=doc)
- missing_in_model: 17
- missing_in_db: 16

### 项目 (spec=15, source=assumption)
- missing_in_model: 15
- missing_in_db: 15

## 命名疑似不一致（alias 命中）