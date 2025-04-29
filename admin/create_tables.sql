CREATE TABLE ls_xgboost(
   lsid bigint PRIMARY KEY,
   ra double precision,
   dec double precision,
   white_mag real,
   xgboost real,
   is_bailout bool default false
);
ALTER TABLE ls_xgboost ADD INDEX ix_ls_xgboost_q3c ON ls_xgboost(q3c_ang2ipix(ra,dec));
ALTER TABLE ls_xgboost ADD INDEX ix_ls_xgboost_mag ON ls_xgboost(white_mag);
ALTER TABLE ls_xgboost ADD INDEX ix_ls_xgboost_xgboost ON ls_xgboost(xgboost);
