CREATE TABLE IF NOT EXISTS consolidation_members (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    group_id BIGINT NOT NULL,
    book_id BIGINT NOT NULL,
    member_book_id BIGINT NULL,
    child_book_id BIGINT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_cons_members_group_book (group_id, book_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
