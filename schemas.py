from pydantic import BaseModel, Field
from decimal import Decimal
from typing import Literal, Optional

class AsistenciaQRRequest(BaseModel):
    qr_token: str

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