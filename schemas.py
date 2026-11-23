from pydantic import BaseModel, Field
from decimal import Decimal
from typing import Literal, Optional

class AsistenciaQRRequest(BaseModel):
    qr_token: Optional[str] = None
    dni: Optional[str] = None
    tipo_asistencia: str = "Catequesis"
    detalle_evento: Optional[str] = None
    id_usuario: int = 1
    metodo_registro: str = "QR"                 # "QR" o "Manual"
    codigo_servicio: Optional[str] = None       # Código de turno de 4h
    fecha_hora_cliente: Optional[str] = None    # Para sincronizar cola offline
    forzar_duplicado: bool = False  # Nuevo: confirmación explícita del Admin

class ConceptoPagoCreate(BaseModel):
    nombre_conc: str = Field(..., max_length=100, example="Matrícula Catequesis 2026")
    monto_base: Decimal = Field(..., gt=0, example=50.00)

class PagoCreate(BaseModel):
    dni_catequizando: str = Field(..., min_length=8, max_length=8, example="24216557")
    id_concepto: int = Field(..., example=1)
    metodo_pago: Literal["Efectivo", "Yape", "Transferencia"]
    monto: Optional[Decimal] = Field(None, gt=0, description="Si se omite, se cobra el monto_base del concepto")
    id_usuario: int = Field(default=1, description="ID del tesorero que registra el cobro")

class DocumentoRequisitoCreate(BaseModel):
    nombre_doc: str = Field(..., max_length=100, example="Partida de Bautismo")
    es_obligatorio: bool = Field(default=True)


class ExpedienteCreate(BaseModel):
    dni_catequizando: str = Field(..., min_length=8, max_length=8, example="24216557")
    id_doc: int = Field(..., example=1)
    estado: Literal["Entregado", "Pendiente", "Observado"]
    id_usuario: int = Field(default=1, description="ID del secretario que valida el documento")

class CatequizandoCreate(BaseModel):
    dni: str
    nombres: str
    apellidos: str
    colegio: Optional[str] = "Particulares"
    estado_bautismo: Optional[str] = "Bautizado"
    celular_joven: Optional[str] = None
    celular_apoderado_1: Optional[str] = None
    parentesco_apoderado_1: Optional[str] = None
    celular_apoderado_2: Optional[str] = None
    parentesco_apoderado_2: Optional[str] = None

class ClaveTemporalCreate(BaseModel):
    duracion: str  # "24h", "48h", "7d", "indeterminado"

class ClaveTemporalValidar(BaseModel):
    codigo: str

class UsuarioCreate(BaseModel):
    dni: str
    nombre: str
    password: str
    rol: str

class CatequizandoUpdate(BaseModel):
    dni: str
    nombres: str
    apellidos: str
    colegio: Optional[str] = "Particulares"
    estado_bautismo: Optional[str] = "Bautizado"
    celular_joven: Optional[str] = None
    celular_apoderado_1: Optional[str] = None
    parentesco_apoderado_1: Optional[str] = None
    celular_apoderado_2: Optional[str] = None
    parentesco_apoderado_2: Optional[str] = None

class CodigoServicioCreate(BaseModel):
    tipo_asistencia: str
    detalle_evento: Optional[str] = None
    duracion_horas: int = 4                     # Máximo 4 horas
    hora_limite_tardanza: Optional[str] = None  # Ej: "15:15" o None
    colegio_permitido: Optional[str] = "Todos"

class LoginMovilRequest(BaseModel):
    dni: str
    password: str
    codigo_servicio: Optional[str] = None
