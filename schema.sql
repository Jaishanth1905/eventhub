-- ============================================================
--  EventHub — Database Schema
--  Run this once before starting the app:
--      mysql -u root -p < schema.sql
-- ============================================================

CREATE DATABASE IF NOT EXISTS eventhub
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE eventhub;

-- ============================================================
--  USERS  (admin / organizer / participant)
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(120)  NOT NULL,
    email           VARCHAR(150)  NOT NULL UNIQUE,
    phone           VARCHAR(20)   DEFAULT NULL,
    password_hash   VARCHAR(255)  NOT NULL,
    role            ENUM('admin', 'organizer', 'participant') NOT NULL DEFAULT 'participant',
    created_at      TIMESTAMP     DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ============================================================
--  VENUES
-- ============================================================
CREATE TABLE IF NOT EXISTS venues (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(150) NOT NULL UNIQUE,
    location    VARCHAR(255) DEFAULT NULL,
    capacity    INT DEFAULT NULL,
    is_active   TINYINT(1)   NOT NULL DEFAULT 1,
    created_at  TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ============================================================
--  EVENTS
-- ============================================================
CREATE TABLE IF NOT EXISTS events (
    id                      INT AUTO_INCREMENT PRIMARY KEY,
    organizer_id            INT NOT NULL,
    title                   VARCHAR(200) NOT NULL,
    category                VARCHAR(80)  DEFAULT NULL,
    description             TEXT,
    venue                   VARCHAR(150) DEFAULT NULL,   -- free-text venue name (matched against venues.name)
    poster                  VARCHAR(255) DEFAULT NULL,   -- filename in static/uploads/
    start_datetime          DATETIME     DEFAULT NULL,
    registration_deadline   DATE         DEFAULT NULL,
    capacity                INT          DEFAULT NULL,
    fee_type                ENUM('free', 'paid') NOT NULL DEFAULT 'free',
    fee                     DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    approval_state          ENUM('draft', 'pending', 'approved', 'rejected') NOT NULL DEFAULT 'draft',
    submitted_at            DATETIME DEFAULT NULL,
    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (organizer_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_events_state (approval_state),
    INDEX idx_events_organizer (organizer_id)
) ENGINE=InnoDB;

-- ============================================================
--  EVENT SESSIONS (schedule)
-- ============================================================
CREATE TABLE IF NOT EXISTS event_sessions (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    event_id        INT NOT NULL,
    session_name    VARCHAR(200) NOT NULL,
    speaker         VARCHAR(150) DEFAULT NULL,
    session_date    DATE NOT NULL,
    start_time      TIME NOT NULL,
    end_time        TIME NOT NULL,
    venue           VARCHAR(150) DEFAULT NULL,
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
    INDEX idx_sessions_event (event_id)
) ENGINE=InnoDB;

-- ============================================================
--  REGISTRATIONS
-- ============================================================
CREATE TABLE IF NOT EXISTS registrations (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    event_id            INT NOT NULL,
    user_id             INT NOT NULL,
    status              ENUM('pending', 'confirmed', 'cancelled') NOT NULL DEFAULT 'confirmed',
    ticket_code         VARCHAR(40)  NOT NULL UNIQUE,
    qr_code             VARCHAR(255) DEFAULT NULL,       -- filename in static/uploads/qr/
    payment_status      ENUM('not_required', 'pending', 'paid', 'failed') NOT NULL DEFAULT 'not_required',
    attendance_status   ENUM('not_marked', 'present') NOT NULL DEFAULT 'not_marked',
    attendance_time      DATETIME DEFAULT NULL,
    feedback_given       TINYINT(1) NOT NULL DEFAULT 0,
    certificate_issued   TINYINT(1) NOT NULL DEFAULT 0,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id)  REFERENCES users(id)  ON DELETE CASCADE,
    UNIQUE KEY uniq_event_user (event_id, user_id),
    INDEX idx_reg_event (event_id),
    INDEX idx_reg_user (user_id)
) ENGINE=InnoDB;

-- ============================================================
--  PAYMENTS  (sandbox)
-- ============================================================
CREATE TABLE IF NOT EXISTS payments (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    registration_id     INT NOT NULL,
    payment_id          VARCHAR(60) NOT NULL UNIQUE,
    amount              DECIMAL(10,2) NOT NULL,
    status              ENUM('success', 'failed') NOT NULL,
    transaction_date    DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (registration_id) REFERENCES registrations(id) ON DELETE CASCADE,
    INDEX idx_payments_reg (registration_id)
) ENGINE=InnoDB;

-- ============================================================
--  FEEDBACK
-- ============================================================
CREATE TABLE IF NOT EXISTS feedback (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    registration_id     INT NOT NULL UNIQUE,
    rating              TINYINT NOT NULL,     -- 1 to 5
    comments            TEXT,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (registration_id) REFERENCES registrations(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ============================================================
--  CERTIFICATES
-- ============================================================
CREATE TABLE IF NOT EXISTS certificates (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    registration_id     INT NOT NULL UNIQUE,
    file_path           VARCHAR(255) DEFAULT NULL,
    issued_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (registration_id) REFERENCES registrations(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ============================================================
--  NOTIFICATIONS  (optional module)
-- ============================================================
CREATE TABLE IF NOT EXISTS notifications (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    user_id     INT NOT NULL,
    title       VARCHAR(200) NOT NULL,
    message     TEXT,
    is_read     TINYINT(1) NOT NULL DEFAULT 0,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_notif_user (user_id)
) ENGINE=InnoDB;