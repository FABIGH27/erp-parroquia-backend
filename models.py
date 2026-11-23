from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, BigInteger, Numeric, Enum, TIMESTAMP, func
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime


class Rol(Base):
    __tablename__ = "roles"

    id_rol = Column(Integer, primary_key=True, autoincrement=True)
    nombre_rol = Column(String(50), unique=True, nullable=False)
    nivel_acceso = Column(Integer, nullable=False)

    # Relación bidireccional con la tabla usuarios
    usuarios = relationship("Usuario", back_populates="rol")


class Usuario(Base):
    __tablename__ = "usuarios"

    id_usuario = Column(Integer, primary_key=True, autoincrement=True)
    id_rol = Column(Integer, ForeignKey("roles.id_rol", ondelete="RESTRICT"), nullable=False)
    dni = Column(String(8), unique=True, nullable=False)
    nombres = Column(String(150), nullable=False)
    password_hash = Column(String(255), nullable=False)
    estado = Column(Boolean, default=True)

    # Relación bidireccional con la tabla roles
    rol = relationship("Rol", back_populates="usuarios")

class Catequizando(Base):
    __tablename__ = "catequizandos"

    id_cateq = Column(Integer, primary_key=True, autoincrement=True)
    dni = Column(String(8), unique=True, nullable=False)
    nombres = Column(String(100), nullable=False)
    apellidos = Column(String(100), nullable=False)
    qr_token = Column(String(64), unique=True, index=True)
    colegio = Column(String(60), nullable=True)  # Mercedes, Politécnico, etc.
    estado_bautismo = Column(String(30), default="Bautizado")  # "Bautizado" o "Por bautizar"
    celular_joven = Column(String(20), nullable=True)
    celular_apoderado_1 = Column(String(20), nullable=True)
    parentesco_apoderado_1 = Column(String(40), nullable=True)  # Ej: Mamá, Papá, Tía...
    celular_apoderado_2 = Column(String(20), nullable=True)
    parentesco_apoderado_2 = Column(String(40), nullable=True)
    grupo = Column(String(20), nullable=True)  # Ej: "Grupo A", "Grupo B", "Grupo C", "Grupo D"
    salon = Column(String(20), nullable=True)  # Ej: "Salón 1", "Salón 2", "Salón 3", "Salón 4"


class Asistencia(Base):
    __tablename__ = "asistencias"

    # Cambiamos id_asistencia por id_asis para que coincida con tu SQL
    id_asis = Column(Integer, primary_key=True, autoincrement=True)

    id_cateq = Column(Integer, ForeignKey("catequizandos.id_cateq", ondelete="CASCADE"), nullable=False)
    id_usuario = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="RESTRICT"), nullable=False)

    fecha_hora = Column(DateTime(timezone=True), server_default=func.now())
    estado = Column(String(20), default="Presente")

    # Relación para facilitar consultas
    catequizando = relationship("Catequizando")

    tipo_asistencia = Column(String(50), default="Catequesis", nullable=False)
    detalle_evento = Column(String(100), nullable=True)

    metodo_registro = Column(String(20), default="QR")  # "QR" o "Manual"

class ConceptoPago(Base):
    __tablename__ = "conceptos_pago"

    id_concepto = Column(Integer, primary_key=True, autoincrement=True)
    nombre_conc = Column(String(100), unique=True, nullable=False)
    monto_base = Column(Numeric(10, 2), nullable=False)


class Pago(Base):
    __tablename__ = "pagos"

    id_pago = Column(BigInteger, primary_key=True, autoincrement=True)
    id_cateq = Column(Integer, ForeignKey("catequizandos.id_cateq", ondelete="RESTRICT"), nullable=False)
    id_usuario = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="RESTRICT"), nullable=False)
    id_concepto = Column(Integer, ForeignKey("conceptos_pago.id_concepto", ondelete="RESTRICT"), nullable=False)
    monto = Column(Numeric(10, 2), nullable=False)
    metodo_pago = Column(Enum("Efectivo", "Yape", "Transferencia"), nullable=False)
    fecha_hora = Column(TIMESTAMP, server_default=func.now())

class DocumentoRequisito(Base):
    __tablename__ = "documentos_requisito"

    id_doc = Column(Integer, primary_key=True, autoincrement=True)
    nombre_doc = Column(String(100), unique=True, nullable=False)
    es_obligatorio = Column(Boolean, default=True)


class Expediente(Base):
    __tablename__ = "expedientes"

    id_exp = Column(BigInteger, primary_key=True, autoincrement=True)
    id_cateq = Column(Integer, ForeignKey("catequizandos.id_cateq", ondelete="CASCADE"), nullable=False)
    id_doc = Column(Integer, ForeignKey("documentos_requisito.id_doc", ondelete="RESTRICT"), nullable=False)
    id_usuario = Column(Integer, ForeignKey("usuarios.id_usuario", ondelete="RESTRICT"), nullable=False)
    estado = Column(Enum("Entregado", "Pendiente", "Observado"), nullable=False)
    fecha_rec = Column(TIMESTAMP, nullable=True, default=None)

class ClaveTemporal(Base):
    __tablename__ = "claves_temporales"

    id_clave = Column(Integer, primary_key=True, index=True)
    codigo = Column(String(50), unique=True, nullable=False)
    fecha_expiracion = Column(DateTime, nullable=True)
    activa = Column(Boolean, default=True, nullable=False)
    creado_en = Column(DateTime, default=func.now())

class CodigoServicio(Base):
    __tablename__ = "codigos_servicio"

    id_codigo = Column(Integer, primary_key=True, index=True)
    codigo = Column(String(20), unique=True, nullable=False, index=True)
    tipo_asistencia = Column(String(50), nullable=False)
    detalle_evento = Column(String(100), nullable=True)
    hora_limite_tardanza = Column(String(5), nullable=True)  # Formato "HH:MM" hora Perú, ej: "15:15"
    creado_en = Column(DateTime, default=datetime.utcnow)
    expira_en = Column(DateTime, nullable=False)
    activo = Column(Boolean, default=True)
    colegio_permitido = Column(String(60), default="Todos")  # "Todos" o un colegio específico