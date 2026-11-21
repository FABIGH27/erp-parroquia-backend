-- ==============================================================================
-- CREACIÓN DE LA BASE DE DATOS
-- ==============================================================================
-- Crea la base de datos solo si no existe en el motor local o en la nube.
-- utf8mb4 garantiza el almacenamiento correcto de caracteres en español (tildes, 'ñ').
CREATE DATABASE IF NOT EXISTS erp_parroquia CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE erp_parroquia;

-- ==============================================================================
-- 1. MÓDULO DE SEGURIDAD (Control de Acceso Basado en Roles - RBAC)
-- ==============================================================================

-- La tabla 'roles' define las jerarquías de autorización del sistema.
-- ENGINE=InnoDB es obligatorio en MySQL para habilitar llaves foráneas y propiedades ACID.
CREATE TABLE roles (
    id_rol INT AUTO_INCREMENT PRIMARY KEY,
    nombre_rol VARCHAR(50) UNIQUE NOT NULL, -- UNIQUE previene la duplicidad accidental de roles.
    nivel_acceso INT NOT NULL               -- Valor numérico usado en Python/FastAPI para jerarquizar permisos.
) ENGINE=InnoDB;

-- La tabla 'usuarios' almacena al personal administrativo y operativo.
CREATE TABLE usuarios (
    id_usuario INT AUTO_INCREMENT PRIMARY KEY,
    id_rol INT NOT NULL,
    dni CHAR(8) UNIQUE NOT NULL,            -- CHAR(8) ahorra espacio y exige longitud exacta para el documento.
    nombres VARCHAR(150) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,    -- Regla de ciberseguridad: las contraseñas siempre se encriptan (Bcrypt).
    estado BOOLEAN DEFAULT TRUE,            -- "Soft delete": Permite dar de baja usuarios sin borrar su historial operativo.
    -- ON DELETE RESTRICT: Mecanismo de protección. Impide borrar un rol si hay usuarios vinculados a él.
    FOREIGN KEY (id_rol) REFERENCES roles(id_rol) ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ==============================================================================
-- 2. MÓDULO LOGÍSTICO Y ASISTENCIA (Alta Concurrencia y Códigos QR)
-- ==============================================================================

-- La tabla 'catequizandos' gestiona la matrícula del programa.
CREATE TABLE catequizandos (
    id_cateq INT AUTO_INCREMENT PRIMARY KEY,
    dni CHAR(8) UNIQUE NOT NULL,
    nombres VARCHAR(100) NOT NULL,
    apellidos VARCHAR(100) NOT NULL,
    qr_token VARCHAR(64) UNIQUE,            -- Cadena de texto generada por el backend que se imprimirá como QR.
    INDEX (qr_token)                        -- INDEX es vital: agiliza la búsqueda en milisegundos durante la lectura masiva.
) ENGINE=InnoDB;

-- La tabla 'asistencias' registra cada petición de escaneo que llega desde la app móvil en Flutter.
CREATE TABLE asistencias (
    id_asis BIGINT AUTO_INCREMENT PRIMARY KEY,      -- BIGINT se usa porque 600 alumnos semanales generarán miles de filas.
    id_cateq INT NOT NULL,
    id_usuario INT NOT NULL,                        -- Trazabilidad: ¿Qué catequista escaneó a este alumno?
    fecha_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- El servidor marca la hora exacta para evitar manipulaciones.
    estado ENUM('Presente', 'Tardanza', 'Falta') NOT NULL,
    -- ON DELETE CASCADE: Si se expulsa o borra a un joven del sistema, sus registros de asistencia se limpian solos.
    FOREIGN KEY (id_cateq) REFERENCES catequizandos(id_cateq) ON DELETE CASCADE,
    -- ON DELETE RESTRICT: Impide borrar a un catequista si ya tomó lista (mantiene el histórico intacto).
    FOREIGN KEY (id_usuario) REFERENCES usuarios(id_usuario) ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ==============================================================================
-- 3. MÓDULO DE TESORERÍA (Transacciones Financieras ACID)
-- ==============================================================================

-- 'conceptos_pago' actúa como un catálogo centralizado de cobros.
CREATE TABLE conceptos_pago (
    id_concepto INT AUTO_INCREMENT PRIMARY KEY,
    nombre_conc VARCHAR(100) UNIQUE NOT NULL,
    monto_base DECIMAL(10,2) NOT NULL       -- DECIMAL(10,2) es el estándar financiero; evita redondeos flotantes de MySQL.
) ENGINE=InnoDB;

-- 'pagos' es el libro mayor contable irrefutable.
CREATE TABLE pagos (
    id_pago BIGINT AUTO_INCREMENT PRIMARY KEY,
    id_cateq INT NOT NULL,
    id_usuario INT NOT NULL,                -- Trazabilidad: ¿Qué tesorero procesó este cobro?
    id_concepto INT NOT NULL,
    monto DECIMAL(10,2) NOT NULL,
    metodo_pago ENUM('Efectivo', 'Yape', 'Transferencia') NOT NULL,
    fecha_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- REGLA DE TESORERÍA (RESTRICT): Las transacciones financieras nunca se borran en cascada.
    -- Bloquear la eliminación asegura una auditoría transparente y previene descuadres de caja.
    FOREIGN KEY (id_cateq) REFERENCES catequizandos(id_cateq) ON DELETE RESTRICT,
    FOREIGN KEY (id_usuario) REFERENCES usuarios(id_usuario) ON DELETE RESTRICT,
    FOREIGN KEY (id_concepto) REFERENCES conceptos_pago(id_concepto) ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ==============================================================================
-- 4. MÓDULO DE SECRETARÍA (Gestión Documental)
-- ==============================================================================

-- 'documentos_requisito' define qué papeles se deben entregar.
CREATE TABLE documentos_requisito (
    id_doc INT AUTO_INCREMENT PRIMARY KEY,
    nombre_doc VARCHAR(100) UNIQUE NOT NULL,
    es_obligatorio BOOLEAN DEFAULT TRUE     -- Lógica de negocio: Indica si su falta bloquea el sacramento.
) ENGINE=InnoDB;

-- 'expedientes' registra el estado individual de cada documento por catequizando.
CREATE TABLE expedientes (
    id_exp BIGINT AUTO_INCREMENT PRIMARY KEY,
    id_cateq INT NOT NULL,
    id_doc INT NOT NULL,
    id_usuario INT NOT NULL,                -- Secretaria que validó físicamente el papel.
    estado ENUM('Entregado', 'Pendiente', 'Observado') NOT NULL,
    fecha_rec TIMESTAMP NULL DEFAULT NULL,  -- NULL indica que el documento aún no ha sido recepcionado.
    FOREIGN KEY (id_cateq) REFERENCES catequizandos(id_cateq) ON DELETE CASCADE,
    FOREIGN KEY (id_doc) REFERENCES documentos_requisito(id_doc) ON DELETE RESTRICT,
    FOREIGN KEY (id_usuario) REFERENCES usuarios(id_usuario) ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ==============================================================================
-- INSERCIÓN DE DATOS INICIALES (SEEDERS)
-- ==============================================================================
-- Inyección de la matriz de roles base. Esto prepara el sistema para que al
-- codificar la seguridad en FastAPI, los endpoints reconozcan estas jerarquías.
INSERT INTO roles (nombre_rol, nivel_acceso) VALUES
('Administrador', 1),
('Secretario', 2),
('Tesorero', 3),
('Catequista', 4);