CREATE TABLE IF NOT EXISTS busan_policies (
  plcy_no TEXT PRIMARY KEY,
  plcy_nm TEXT,
  plcy_expln_cn TEXT,
  plcy_sprt_cn TEXT,
  lclsf_nm TEXT,
  mclsf_nm TEXT,
  plcy_kywd_nm TEXT[] NOT NULL DEFAULT '{}',
  pvsn_inst_group_cd TEXT,
  sprt_trgt_min_age INTEGER,
  sprt_trgt_max_age INTEGER,
  sprt_trgt_age_lmt TEXT,
  zip_cd TEXT[] NOT NULL DEFAULT '{}',
  job_cd TEXT[] NOT NULL DEFAULT '{}',
  school_cd TEXT[] NOT NULL DEFAULT '{}',
  plcy_major_cd TEXT[] NOT NULL DEFAULT '{}',
  sbiz_cd TEXT[] NOT NULL DEFAULT '{}',
  mrg_stts_cd TEXT,
  earn_cnd_se_cd TEXT,
  earn_min_amt BIGINT,
  earn_max_amt BIGINT,
  earn_etc_cn TEXT,
  add_aply_qlfc_cn TEXT,
  ptcp_prp_trgt_cn TEXT,
  aply_prd_se_cd TEXT,
  aply_bgng_ymd DATE,
  aply_end_ymd DATE,
  plcy_aprv_stts_cd TEXT,
  ref_url_addr1 TEXT,
  aply_url_addr TEXT,
  raw JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS code_labels (
  group_name TEXT NOT NULL,
  code TEXT NOT NULL,
  label TEXT NOT NULL,
  PRIMARY KEY (group_name, code)
);

CREATE TABLE IF NOT EXISTS policy_meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_bp_status ON busan_policies(plcy_aprv_stts_cd);
CREATE INDEX IF NOT EXISTS ix_bp_age ON busan_policies(sprt_trgt_min_age, sprt_trgt_max_age);
CREATE INDEX IF NOT EXISTS ix_bp_period ON busan_policies(aply_prd_se_cd, aply_bgng_ymd, aply_end_ymd);
CREATE INDEX IF NOT EXISTS ix_bp_category ON busan_policies(lclsf_nm);
CREATE INDEX IF NOT EXISTS ix_bp_job_gin ON busan_policies USING GIN(job_cd);
CREATE INDEX IF NOT EXISTS ix_bp_school_gin ON busan_policies USING GIN(school_cd);
CREATE INDEX IF NOT EXISTS ix_bp_sbiz_gin ON busan_policies USING GIN(sbiz_cd);
CREATE INDEX IF NOT EXISTS ix_bp_zip_gin ON busan_policies USING GIN(zip_cd);
