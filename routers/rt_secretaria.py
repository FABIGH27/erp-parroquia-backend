from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
import models
import schemas
from database import get_db

router = APIRouter()


@router.post("/api/v1/secretaria/documentos", tags=["Secretaría"])
def crear_documento_requisito(doc: schemas.DocumentoRequisitoCreate, db: Session = Depends(get_db)):
    existe = db.query(models.DocumentoRequisito).filter(
        models.DocumentoRequisito.nombre_doc == doc.nombre_doc
    ).first()
    if existe:
        raise HTTPException(status_code=400, detail="Ese documento requisito ya existe")

    nuevo = models.DocumentoRequisito(
        nombre_doc=doc.nombre_doc,
        es_obligatorio=doc.es_obligatorio
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return {"mensaje": "Documento creado", "id_doc": nuevo.id_doc, "nombre_doc": nuevo.nombre_doc}


@router.get("/api/v1/secretaria/documentos", tags=["Secretaría"])
def listar_documentos_requisito(db: Session = Depends(get_db)):
    return db.query(models.DocumentoRequisito).all()


@router.delete("/api/v1/secretaria/documentos/{id_doc}", tags=["Secretaría"])
def eliminar_documento_requisito(id_doc: int, db: Session = Depends(get_db)):
    doc = db.query(models.DocumentoRequisito).filter(models.DocumentoRequisito.id_doc == id_doc).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Documento no encontrado.")
    try:
        db.delete(doc)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="No se puede eliminar porque ya hay catequizandos con este documento registrado."
        )
    return {"mensaje": "Documento eliminado del catálogo."}


@router.post("/api/v1/secretaria/expedientes", tags=["Secretaría"])
def registrar_o_actualizar_expediente(exp: schemas.ExpedienteCreate, db: Session = Depends(get_db)):
    alumno = db.query(models.Catequizando).filter(
        models.Catequizando.dni == exp.dni_catequizando
    ).first()
    if not alumno:
        raise HTTPException(status_code=404, detail="Catequizando no encontrado con ese DNI")

    documento = db.query(models.DocumentoRequisito).filter(
        models.DocumentoRequisito.id_doc == exp.id_doc
    ).first()
    if not documento:
        raise HTTPException(status_code=404, detail="Documento requisito no encontrado")

    registro = db.query(models.Expediente).filter(
        models.Expediente.id_cateq == alumno.id_cateq,
        models.Expediente.id_doc == documento.id_doc
    ).first()

    fecha_recepcion = func.now() if exp.estado == "Entregado" else None

    if registro:
        registro.estado = exp.estado
        registro.id_usuario = exp.id_usuario
        registro.fecha_rec = fecha_recepcion
        accion = "actualizado"
    else:
        registro = models.Expediente(
            id_cateq=alumno.id_cateq,
            id_doc=documento.id_doc,
            id_usuario=exp.id_usuario,
            estado=exp.estado,
            fecha_rec=fecha_recepcion
        )
        db.add(registro)
        accion = "registrado"

    db.commit()
    db.refresh(registro)

    return {
        "mensaje": f"Expediente {accion} correctamente",
        "alumno": f"{alumno.nombres} {alumno.apellidos}",
        "documento": documento.nombre_doc,
        "estado": registro.estado,
        "fecha_rec": registro.fecha_rec
    }


@router.get("/api/v1/secretaria/expedientes/{dni}", tags=["Secretaría"])
def consultar_expediente_alumno(dni: str, db: Session = Depends(get_db)):
    alumno = db.query(models.Catequizando).filter(models.Catequizando.dni == dni).first()
    if not alumno:
        raise HTTPException(status_code=404, detail="Catequizando no encontrado")

    registros = (
        db.query(
            models.Expediente.id_exp,
            models.DocumentoRequisito.nombre_doc,
            models.DocumentoRequisito.es_obligatorio,
            models.Expediente.estado,
            models.Expediente.fecha_rec,
            models.Usuario.nombres.label("registrado_por")
        )
        .join(models.DocumentoRequisito, models.Expediente.id_doc == models.DocumentoRequisito.id_doc)
        .outerjoin(models.Usuario, models.Expediente.id_usuario == models.Usuario.id_usuario)
        .filter(models.Expediente.id_cateq == alumno.id_cateq)
        .all()
    )

    return {
        "dni": alumno.dni,
        "alumno": f"{alumno.nombres} {alumno.apellidos}",
        "documentos": [
            {
                "id_exp": r.id_exp,
                "documento": r.nombre_doc,
                "obligatorio": r.es_obligatorio,
                "estado": r.estado,
                "fecha_recepcion": r.fecha_rec,
                "registrado_por": r.registrado_por or "Sistema"
            }
            for r in registros
        ]
    }


@router.delete("/api/v1/secretaria/expedientes/{id_exp}", tags=["Secretaría"])
def eliminar_expediente(id_exp: int, db: Session = Depends(get_db)):
    exp = db.query(models.Expediente).filter(models.Expediente.id_exp == id_exp).first()
    if not exp:
        raise HTTPException(status_code=404, detail="Registro de expediente no encontrado.")
    db.delete(exp)
    db.commit()
    return {"mensaje": "Registro eliminado correctamente."}