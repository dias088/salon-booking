CREATE TABLE CLIENT (
    ClientID          SERIAL PRIMARY KEY,
    FirstName         VARCHAR(50)  NOT NULL,
    LastName          VARCHAR(50)  NOT NULL,
    Email             VARCHAR(100) NOT NULL UNIQUE,
    Phone             VARCHAR(20)  NOT NULL,
    DateOfBirth       DATE         NOT NULL,
    RegistrationDate  DATE         NOT NULL DEFAULT (CURRENT_DATE),
    Address           VARCHAR(150)
);

CREATE TABLE STYLIST (
    StylistID       SERIAL PRIMARY KEY,
    FirstName       VARCHAR(50)  NOT NULL,
    LastName        VARCHAR(50)  NOT NULL,
    Specialization  VARCHAR(50)  NOT NULL,
    Phone           VARCHAR(20)  NOT NULL,
    Email           VARCHAR(100) NOT NULL UNIQUE,
    HireDate        DATE         NOT NULL
);

CREATE TABLE SERVICE (
    ServiceID        SERIAL PRIMARY KEY,
    ServiceName       VARCHAR(60)  NOT NULL UNIQUE,
    Category          VARCHAR(30)  NOT NULL,
    DurationMinutes   INT          NOT NULL CHECK (DurationMinutes > 0),
    Price             DECIMAL(8,2) NOT NULL CHECK (Price >= 0),
    Description       VARCHAR(255)
);

CREATE TABLE STATION (
    StationID    SERIAL PRIMARY KEY,
    StationName  VARCHAR(50) NOT NULL UNIQUE,
    Type         VARCHAR(30) NOT NULL,
    Location     VARCHAR(50)
);

CREATE TABLE PRODUCT (
    ProductID      SERIAL PRIMARY KEY,
    ProductName    VARCHAR(100) NOT NULL,
    Brand          VARCHAR(50)  NOT NULL,
    ServiceID      INT          NOT NULL,
    StockQuantity  INT          NOT NULL CHECK (StockQuantity >= 0),
    Price          DECIMAL(8,2) NOT NULL CHECK (Price >= 0),
    CONSTRAINT fk_product_service
        FOREIGN KEY (ServiceID) REFERENCES SERVICE(ServiceID) ON DELETE RESTRICT
);

CREATE TABLE APPOINTMENT (
    AppointmentID    SERIAL PRIMARY KEY,
    ClientID         INT NOT NULL,
    StylistID        INT NOT NULL,
    StationID        INT NOT NULL,
    AppointmentDate  DATE NOT NULL,
    AppointmentTime  TIME NOT NULL,
    Status           VARCHAR(20) NOT NULL CHECK (Status IN ('Scheduled','Completed','Cancelled','No-show')),
    CONSTRAINT fk_appointment_client
        FOREIGN KEY (ClientID) REFERENCES CLIENT(ClientID) ON DELETE CASCADE,
    CONSTRAINT fk_appointment_stylist
        FOREIGN KEY (StylistID) REFERENCES STYLIST(StylistID) ON DELETE RESTRICT,
    CONSTRAINT fk_appointment_station
        FOREIGN KEY (StationID) REFERENCES STATION(StationID) ON DELETE RESTRICT
);
CREATE TABLE APPOINTMENT_SERVICE (
    AppointmentServiceID  SERIAL PRIMARY KEY,
    AppointmentID         INT NOT NULL,
    ServiceID             INT NOT NULL,
    PriceAtBooking         DECIMAL(8,2) NOT NULL CHECK (PriceAtBooking >= 0),
    CONSTRAINT fk_apptservice_appointment
        FOREIGN KEY (AppointmentID) REFERENCES APPOINTMENT(AppointmentID) ON DELETE CASCADE,
    CONSTRAINT fk_apptservice_service
        FOREIGN KEY (ServiceID) REFERENCES SERVICE(ServiceID) ON DELETE RESTRICT,
    CONSTRAINT uq_appointment_service UNIQUE (AppointmentID, ServiceID)
);

CREATE TABLE PAYMENT (
    PaymentID      SERIAL PRIMARY KEY,
    AppointmentID  INT NOT NULL,
    Amount         DECIMAL(8,2) NOT NULL CHECK (Amount > 0),
    PaymentDate    DATE NOT NULL,
    PaymentMethod  VARCHAR(20) CHECK (PaymentMethod IN ('Cash','Card','Online')),
    CONSTRAINT fk_payment_appointment
        FOREIGN KEY (AppointmentID) REFERENCES APPOINTMENT(AppointmentID) ON DELETE CASCADE
);
