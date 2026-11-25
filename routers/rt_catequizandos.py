from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
import models
import schemas
from database import get_db
from routers.rt_deps import _a_hora_peru

router = APIRouter()


@router.post("/api/v1/catequizandos", tags=["Gestión de Catequizandos"])
def crear_catequizando(datos: schemas.CatequizandoCreate, db: Session = Depends(get_db)):
    existe = db.query(models.Catequizando).filter(models.Catequizando.dni == datos.dni).first()
    if existe:
        raise HTTPException(status_code=400, detail="Ya existe un catequizando con ese DNI.")

    qr_generado = f"CAT-{datos.dni.strip()}"
    nuevo = models.Catequizando(
        dni=datos.dni.strip(),
        nombres=datos.nombres.strip(),
        apellidos=datos.apellidos.strip(),
        qr_token=qr_generado,
        colegio=datos.colegio,
        estado_bautismo=datos.estado_bautismo or "Bautizado",
        celular_joven=datos.celular_joven,
        celular_apoderado_1=datos.celular_apoderado_1,
        parentesco_apoderado_1=datos.parentesco_apoderado_1,
        celular_apoderado_2=datos.celular_apoderado_2,
        parentesco_apoderado_2=datos.parentesco_apoderado_2,
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)

    return {
        "mensaje": "Catequizando registrado exitosamente",
        "id": nuevo.id_cateq,
        "qr_token": nuevo.qr_token
    }


@router.get("/api/v1/catequizandos", tags=["Gestión de Catequizandos"])
def listar_catequizandos(db: Session = Depends(get_db)):
    jovenes = db.query(models.Catequizando).all()
    resultado = []
    for j in jovenes:
        cat = db.query(func.count(models.Asistencia.id_asis)).filter(
            models.Asistencia.id_cateq == j.id_cateq,
            models.Asistencia.tipo_asistencia == "Catequesis"
        ).scalar() or 0
        misas = db.query(func.count(models.Asistencia.id_asis)).filter(
            models.Asistencia.id_cateq == j.id_cateq,
            models.Asistencia.tipo_asistencia == "Misa"
        ).scalar() or 0
        acts = db.query(func.count(models.Asistencia.id_asis)).filter(
            models.Asistencia.id_cateq == j.id_cateq,
            models.Asistencia.tipo_asistencia == "Actividad Parroquial"
        ).scalar() or 0

        resultado.append({
            "ID": j.id_cateq,
            "DNI": j.dni,
            "Nombres": j.nombres,
            "Apellidos": j.apellidos,
            "QR Token": j.qr_token,
            "Colegio": j.colegio or "Sin asignar",
            "Grupo": j.grupo or "Sin asignar",
            "Salón": j.salon or "Sin asignar",
            "Bautismo": j.estado_bautismo or "Bautizado",
            "Celular Joven": j.celular_joven or "-",
            "Apoderado 1": f"{j.celular_apoderado_1} ({j.parentesco_apoderado_1 or 'Apoderado'})" if j.celular_apoderado_1 else "-",
            "Apoderado 2": f"{j.celular_apoderado_2} ({j.parentesco_apoderado_2 or 'Apoderado'})" if j.celular_apoderado_2 else "-",
            "Catequesis": cat,
            "Misas": misas,
            "Actividades": acts,
            "celular_joven_raw": j.celular_joven or "",
            "celular_apoderado_1_raw": j.celular_apoderado_1 or "",
            "parentesco_apoderado_1_raw": j.parentesco_apoderado_1 or "",
            "celular_apoderado_2_raw": j.celular_apoderado_2 or "",
            "parentesco_apoderado_2_raw": j.parentesco_apoderado_2 or "",
        })
    return resultado


@router.put("/api/v1/catequizandos/{id_cateq}", tags=["Gestión de Catequizandos"])
def editar_catequizando(id_cateq: int, datos: schemas.CatequizandoUpdate, db: Session = Depends(get_db)):
    alumno = db.query(models.Catequizando).filter(models.Catequizando.id_cateq == id_cateq).first()
    if not alumno:
        raise HTTPException(status_code=404, detail="Catequizando no encontrado.")

    dni_limpio = datos.dni.strip()
    duplicado = db.query(models.Catequizando).filter(
        models.Catequizando.dni == dni_limpio,
        models.Catequizando.id_cateq != id_cateq
    ).first()
    if duplicado:
        raise HTTPException(status_code=400, detail="Ese DNI ya pertenece a otro catequizando.")

    alumno.dni = dni_limpio
    alumno.nombres = datos.nombres.strip()
    alumno.apellidos = datos.apellidos.strip()
    alumno.qr_token = f"CAT-{dni_limpio}"
    alumno.colegio = datos.colegio
    alumno.estado_bautismo = datos.estado_bautismo or "Bautizado"
    alumno.celular_joven = datos.celular_joven
    alumno.celular_apoderado_1 = datos.celular_apoderado_1
    alumno.parentesco_apoderado_1 = datos.parentesco_apoderado_1
    alumno.celular_apoderado_2 = datos.celular_apoderado_2
    alumno.parentesco_apoderado_2 = datos.parentesco_apoderado_2

    db.commit()
    db.refresh(alumno)
    return {"mensaje": "Catequizando actualizado correctamente", "qr_token": alumno.qr_token}


@router.delete("/api/v1/catequizandos/{id_cateq}", tags=["Gestión de Catequizandos"])
def eliminar_catequizando(id_cateq: int, db: Session = Depends(get_db)):
    alumno = db.query(models.Catequizando).filter(models.Catequizando.id_cateq == id_cateq).first()
    if not alumno:
        raise HTTPException(status_code=404, detail="Catequizando no encontrado.")
    try:
        db.delete(alumno)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="No se puede eliminar porque tiene pagos registrados. Anula sus pagos primero."
        )
    return {"mensaje": "Catequizando eliminado correctamente."}


@router.get("/api/v1/catequizandos/{id_cateq}/ficha-completa", tags=["Gestión de Catequizandos"])
def obtener_ficha_completa(id_cateq: int, db: Session = Depends(get_db)):
    alumno = db.query(models.Catequizando).filter(models.Catequizando.id_cateq == id_cateq).first()
    if not alumno:
        raise HTTPException(status_code=404, detail="Catequizando no encontrado.")

    asistencias_db = (
        db.query(
            models.Asistencia.tipo_asistencia,
            models.Asistencia.detalle_evento,
            models.Asistencia.estado,
            models.Asistencia.metodo_registro,
            models.Asistencia.fecha_hora,
            models.Usuario.nombres.label("registrado_por")
        )
        .outerjoin(models.Usuario, models.Asistencia.id_usuario == models.Usuario.id_usuario)
        .filter(models.Asistencia.id_cateq == id_cateq)
        .order_by(models.Asistencia.fecha_hora.asc())
        .all()
    )

    asistencias_lista = [
        {
            "tipo": a.tipo_asistencia,
            "detalle": a.detalle_evento or "-",
            "estado": a.estado or "Presente",
            "metodo": a.metodo_registro or "QR",
            "fecha_hora": _a_hora_peru(a.fecha_hora),
            "registrado_por": a.registrado_por or "Sistema"
        }
        for a in asistencias_db
    ]

    conceptos = db.query(models.ConceptoPago).all()
    pagos_db = (
        db.query(
            models.Pago.id_pago,
            models.Pago.id_concepto,
            models.ConceptoPago.nombre_conc,
            models.Pago.codigo_boleta,
            models.Pago.monto,
            models.Pago.metodo_pago,
            models.Pago.fecha_hora,
            models.Usuario.nombres.label("registrado_por")
        )
        .join(models.ConceptoPago, models.Pago.id_concepto == models.ConceptoPago.id_concepto)
        .outerjoin(models.Usuario, models.Pago.id_usuario == models.Usuario.id_usuario)
        .filter(models.Pago.id_cateq == id_cateq)
        .order_by(models.Pago.fecha_hora.desc())
        .all()
    )

    pagos_por_concepto = {}
    for p in pagos_db:
        pagos_por_concepto[p.id_concepto] = pagos_por_concepto.get(p.id_concepto, 0.0) + float(p.monto)

    resumen_pagos = []
    for c in conceptos:
        base = float(c.monto_base)
        pagado = pagos_por_concepto.get(c.id_concepto, 0.0)
        debe = max(0.0, round(base - pagado, 2))
        estado_p = "Pagado" if debe == 0 else ("Parcial" if pagado > 0 else "Pendiente")
        resumen_pagos.append({
            "Concepto": c.nombre_conc,
            "Monto Base (S/)": base,
            "Pagado (S/)": pagado,
            "Debe (S/)": debe,
            "Estado": estado_p
        })

    historial_pagos = [
        {
            "ID": p.id_pago,
            "Concepto": p.nombre_conc,
            "Boleta": p.codigo_boleta or "-",
            "Monto (S/)": float(p.monto),
            "Método": p.metodo_pago,
            "Fecha y Hora": _a_hora_peru(p.fecha_hora),
            "Registrado por": p.registrado_por or "Sistema"
        }
        for p in pagos_db
    ]

    docs_catalogo = db.query(models.DocumentoRequisito).all()
    exp_db = (
        db.query(
            models.Expediente.id_doc,
            models.Expediente.estado,
            models.Expediente.fecha_rec,
            models.Usuario.nombres.label("registrado_por")
        )
        .outerjoin(models.Usuario, models.Expediente.id_usuario == models.Usuario.id_usuario)
        .filter(models.Expediente.id_cateq == id_cateq)
        .all()
    )
    mapa_exp = {e.id_doc: e for e in exp_db}

    documentos_lista = []
    for d in docs_catalogo:
        reg = mapa_exp.get(d.id_doc)
        documentos_lista.append({
            "Documento": d.nombre_doc,
            "Obligatorio": "Sí" if d.es_obligatorio else "No",
            "Estado": reg.estado if reg else "Sin entregar",
            "Fecha Recepción": reg.fecha_rec.strftime("%d/%m/%Y %H:%M") if (reg and reg.fecha_rec) else "-",
            "Registrado por": (reg.registrado_por or "Sistema") if reg else "-"
        })

    return {
        "datos": {
            "ID": alumno.id_cateq,
            "DNI": alumno.dni,
            "Nombres": alumno.nombres,
            "Apellidos": alumno.apellidos,
            "QR Token": alumno.qr_token,
            "Colegio": alumno.colegio or "Sin asignar",
            "Grupo": alumno.grupo or "Sin asignar",
            "Salón": alumno.salon or "Sin asignar",
            "Bautismo": alumno.estado_bautismo or "Bautizado",
            "Celular Joven": alumno.celular_joven or "-",
            "Apoderado 1": f"{alumno.celular_apoderado_1} ({alumno.parentesco_apoderado_1 or 'Apoderado'})" if alumno.celular_apoderado_1 else "-",
            "Apoderado 2": f"{alumno.celular_apoderado_2} ({alumno.parentesco_apoderado_2 or 'Apoderado'})" if alumno.celular_apoderado_2 else "-",
        },
        "asistencias": asistencias_lista,
        "pagos": {
            "resumen": resumen_pagos,
            "historial": historial_pagos
        },
        "documentos": documentos_lista
    }


@router.put("/api/v1/admin/catequizandos/asignar-masivo", tags=["Gestión de Catequizandos"])
def asignar_grupos_y_salones_masivo(
    items: List[schemas.AsignacionMasivaItem],
    db: Session = Depends(get_db)
):
    actualizados = 0
    for item in items:
        alumno = db.query(models.Catequizando).filter(
            models.Catequizando.id_cateq == item.id_cateq
        ).first()
        if alumno:
            if item.grupo is not None:
                alumno.grupo = item.grupo if item.grupo != "Sin asignar" else None
            if item.salon is not None:
                alumno.salon = item.salon if item.salon != "Sin asignar" else None
            actualizados += 1
    db.commit()
    return {"mensaje": f"Se actualizaron {actualizados} catequizandos correctamente.", "actualizados": actualizados}


@router.post("/api/v1/admin/importar/catequizandos", tags=["Gestión de Catequizandos"])
def importar_catequizandos_masivo(lista: List[schemas.CatequizandoCreate], db: Session = Depends(get_db)):
    creados = 0
    omitidos = 0
    for item in lista:
        dni_limpio = item.dni.strip()
        if len(dni_limpio) != 8:
            omitidos += 1
            continue
        existe = db.query(models.Catequizando).filter(models.Catequizando.dni == dni_limpio).first()
        if existe:
            omitidos += 1
            continue
        nuevo = models.Catequizando(
            dni=dni_limpio,
            nombres=item.nombres.strip(),
            apellidos=item.apellidos.strip(),
            qr_token=f"CAT-{dni_limpio}",
            colegio=(item.colegio or "").strip() or None,
            estado_bautismo=(item.estado_bautismo or "").strip() or "Bautizado",
            celular_joven=(item.celular_joven or "").strip() or None,
            celular_apoderado_1=(item.celular_apoderado_1 or "").strip() or None,
            parentesco_apoderado_1=(item.parentesco_apoderado_1 or "").strip() or None,
            celular_apoderado_2=(item.celular_apoderado_2 or "").strip() or None,
            parentesco_apoderado_2=(item.parentesco_apoderado_2 or "").strip() or None,
            grupo=(item.grupo or "").strip() or None,
            salon=(item.salon or "").strip() or None,
        )
        db.add(nuevo)
        creados += 1
    db.commit()
    return {"mensaje": "Importación finalizada", "creados": creados, "omitidos": omitidos}