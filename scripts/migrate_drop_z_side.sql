-- 模板去 A/Z 端化迁移脚本
-- 模板只管 A 端配置，去掉 has_z_side / config_z 这两列
-- 破坏性变更：config_z 列删除后数据不可恢复，执行前请确认现网无依赖 Z 端配置的历史模板在用，
-- 必要时先对 arch_template / arch_template_config / arch_template_snapshot 三张表做备份

ALTER TABLE `arch_template` DROP COLUMN `has_z_side`;
ALTER TABLE `arch_template_config` DROP COLUMN `config_z`;
ALTER TABLE `arch_template_snapshot` DROP COLUMN `config_z`;
