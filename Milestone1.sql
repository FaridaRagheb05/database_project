
DROP DATABASE IF EXISTS properties;

CREATE DATABASE properties
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;      -- utf8mb4: site data contains Arabic text
USE properties;

CREATE TABLE location (
    area_name  VARCHAR(100) NOT NULL,
    CONSTRAINT pk_location PRIMARY KEY (area_name)
) ENGINE=InnoDB;


CREATE TABLE developer (
    developer_name  VARCHAR(150) NOT NULL,   -- normalized by the crawler
    CONSTRAINT pk_developer PRIMARY KEY (developer_name)
) ENGINE=InnoDB;


CREATE TABLE app_user (
    email       VARCHAR(255) NOT NULL,
    username    VARCHAR(50)  NOT NULL,
    gender      ENUM('Male','Female','Other') NOT NULL,
    birthdate   DATE         NOT NULL,
    created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_app_user PRIMARY KEY (email),
    CONSTRAINT uq_app_user_username UNIQUE (username),
    CONSTRAINT chk_user_email CHECK (email LIKE '%_@_%._%')
) ENGINE=InnoDB;

-- Age is derived from birthdate (CURDATE() cannot be used in a generated
-- column), so it is exposed through a view instead of being stored.
CREATE VIEW v_user AS
SELECT email, username, gender, birthdate,
       TIMESTAMPDIFF(YEAR, birthdate, CURDATE()) AS age,
       created_at
FROM app_user;


CREATE TABLE development (
    development_id  INT          NOT NULL AUTO_INCREMENT,
    project_name    VARCHAR(150) NOT NULL,
    description     TEXT         NULL,
    developer_name  VARCHAR(150) NULL,      -- NULL if developer not listed
    area_name       VARCHAR(100) NOT NULL,
    CONSTRAINT pk_development PRIMARY KEY (development_id),
    CONSTRAINT uq_development UNIQUE (project_name, area_name),
    CONSTRAINT fk_development_location
        FOREIGN KEY (area_name) REFERENCES location (area_name)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_development_developer
        FOREIGN KEY (developer_name) REFERENCES developer (developer_name)
        ON UPDATE CASCADE ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE INDEX idx_development_developer ON development (developer_name);


CREATE TABLE property (
    listing_ref         VARCHAR(30)   NOT NULL,   -- AqarExit id, e.g. U-16437
    listing_url         VARCHAR(500)  NULL,
    title               VARCHAR(255)  NULL,
    description         TEXT          NULL,
    type                VARCHAR(50)   NOT NULL,   -- Apartment, Villa, Townhouse, ...
    area_name           VARCHAR(100)  NOT NULL,
    development_id      INT           NULL,       -- NULL if not in a development
    area_sqm            DECIMAL(10,2) NULL,
    bedrooms            TINYINT UNSIGNED NULL,
    bathrooms           TINYINT UNSIGNED NULL,
    payment_method      VARCHAR(50)   NULL,
    contract_year       SMALLINT      NULL,
    delivery_year       SMALLINT      NULL,
    down_payment        DECIMAL(15,2) NULL,       -- "Cash required now"
    remaining_amount    DECIMAL(15,2) NULL,       -- "Remaining with developer"
    installment_amount  DECIMAL(15,2) NULL,
    installment_freq    VARCHAR(20)   NULL,       -- Quarterly / Semi-annual / ...
    market_price        DECIMAL(15,2) NULL,
    commission_pct      DECIMAL(5,2)  NULL,
    gain_amount         DECIMAL(15,2) NULL,
    is_negotiable       BOOLEAN       NOT NULL DEFAULT FALSE,
    docs_verified       BOOLEAN       NOT NULL DEFAULT FALSE,
    is_featured         BOOLEAN       NOT NULL DEFAULT FALSE,
    scraped_at          TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_property PRIMARY KEY (listing_ref),
    CONSTRAINT fk_property_location
        FOREIGN KEY (area_name) REFERENCES location (area_name)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_property_development
        FOREIGN KEY (development_id) REFERENCES development (development_id)
        ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT chk_property_area     CHECK (area_sqm IS NULL OR area_sqm > 0),
    CONSTRAINT chk_property_contract CHECK (contract_year IS NULL OR contract_year BETWEEN 1990 AND 2100),
    CONSTRAINT chk_property_delivery CHECK (delivery_year IS NULL OR delivery_year BETWEEN 1990 AND 2100),
    CONSTRAINT chk_property_commis   CHECK (commission_pct IS NULL OR commission_pct BETWEEN 0 AND 100),
    CONSTRAINT chk_property_amounts  CHECK (
        (down_payment       IS NULL OR down_payment       >= 0) AND
        (installment_amount IS NULL OR installment_amount >= 0) AND
        (market_price       IS NULL OR market_price       >= 0))
) ENGINE=InnoDB;

CREATE INDEX idx_property_area_type ON property (area_name, type);
CREATE INDEX idx_property_development ON property (development_id);
CREATE INDEX idx_property_contract ON property (contract_year);


CREATE TABLE property_amenity (
    listing_ref  VARCHAR(30)  NOT NULL,
    amenity      VARCHAR(100) NOT NULL,
    CONSTRAINT pk_property_amenity PRIMARY KEY (listing_ref, amenity),
    CONSTRAINT fk_pa_property
        FOREIGN KEY (listing_ref) REFERENCES property (listing_ref)
        ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE INDEX idx_pa_amenity ON property_amenity (amenity);


CREATE TABLE review (
    review_id       INT          NOT NULL AUTO_INCREMENT,
    rating          TINYINT UNSIGNED NOT NULL,
    review_text     TEXT         NULL,
    posted_at       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    development_id  INT          NOT NULL,
    email           VARCHAR(255) NOT NULL,
    CONSTRAINT pk_review PRIMARY KEY (review_id),
    CONSTRAINT uq_review_app_user_dev UNIQUE (email, development_id),  -- one review per app_user per project
    CONSTRAINT chk_review_rating CHECK (rating BETWEEN 1 AND 10),
    CONSTRAINT fk_review_development
        FOREIGN KEY (development_id) REFERENCES development (development_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_review_app_user
        FOREIGN KEY (email) REFERENCES app_user (email)
        ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE INDEX idx_review_development ON review (development_id);


CREATE TABLE user_focuses_location (
    email      VARCHAR(255) NOT NULL,
    area_name  VARCHAR(100) NOT NULL,
    CONSTRAINT pk_user_focuses_location PRIMARY KEY (email, area_name),
    CONSTRAINT fk_ufl_app_user
        FOREIGN KEY (email) REFERENCES app_user (email)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_ufl_location
        FOREIGN KEY (area_name) REFERENCES location (area_name)
        ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Verification
-- ---------------------------------------------------------------------
SHOW TABLES;
DESCRIBE location;
DESCRIBE developer;
DESCRIBE development;
DESCRIBE property;
DESCRIBE property_amenity;
DESCRIBE app_user;
DESCRIBE review;
DESCRIBE user_focuses_location;
