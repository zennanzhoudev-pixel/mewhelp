-- =============================================================
-- ch12 · 统一登录、账号管理、人工客服工作台
-- 在已有 ch01-ch11 数据库上执行一次。
-- =============================================================
SET NAMES utf8mb4;

ALTER TABLE users
  MODIFY COLUMN role ENUM('admin','agent','viewer','customer')
    NOT NULL DEFAULT 'customer' COMMENT '角色',
  ADD COLUMN phone VARCHAR(32) NULL COMMENT '手机号' AFTER tenant_id,
  ADD COLUMN display_name VARCHAR(64) NULL COMMENT '显示名' AFTER phone,
  ADD COLUMN status ENUM('active','disabled') NOT NULL DEFAULT 'active'
    COMMENT '账号状态' AFTER display_name,
  ADD COLUMN last_login_at DATETIME NULL COMMENT '最近登录' AFTER status,
  ADD UNIQUE KEY uk_users_phone (phone);

ALTER TABLE conversations
  ADD COLUMN assigned_agent_id BIGINT NULL COMMENT '认领客服 users.id' AFTER status,
  ADD COLUMN transfer_reason VARCHAR(300) NULL COMMENT '转人工原因' AFTER assigned_agent_id,
  ADD KEY idx_conversations_support (tenant_id, status, assigned_agent_id);

ALTER TABLE messages
  ADD COLUMN sender_type VARCHAR(16) NOT NULL DEFAULT 'ai'
    COMMENT 'ai/user/agent/system' AFTER tool_call_id,
  ADD COLUMN sender_id BIGINT NULL COMMENT '真人发送者 users.id' AFTER sender_type;

CREATE TABLE IF NOT EXISTS login_codes (
  id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  phone       VARCHAR(32) NOT NULL,
  code_hash   VARCHAR(128) NOT NULL,
  expires_at  DATETIME NOT NULL,
  attempts    INT NOT NULL DEFAULT 0,
  used_at     DATETIME NULL,
  created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_login_codes_phone (phone, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='手机验证码';

CREATE TABLE IF NOT EXISTS qr_login_sessions (
  ticket       VARCHAR(64) NOT NULL,
  status       ENUM('pending','approved','consumed','expired') NOT NULL DEFAULT 'pending',
  user_id      BIGINT UNSIGNED NULL,
  expires_at   DATETIME NOT NULL,
  approved_at  DATETIME NULL,
  consumed_at  DATETIME NULL,
  created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (ticket),
  KEY idx_qr_status (status, expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='二维码登录票据';
