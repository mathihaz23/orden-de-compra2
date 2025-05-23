# utils.py (Crea este archivo para funciones utilitarias)

from flask_mail import Message
from extensions import mail
from flask import current_app
from jinja2 import Template

def enviar_correo(destinatario, asunto, plantilla, **kwargs):
    """
    Envia un correo electrónico utilizando una plantilla HTML.
    """
    try:
        msg = Message(asunto, recipients=[destinatario])
        msg.body = Template("Este es un correo de prueba. Por favor, utiliza un cliente que soporte HTML para ver el contenido.")
        msg.html = Template(plantilla).render(**kwargs)
        mail.send(msg)
    except Exception as e:
        current_app.logger.error(f"Error al enviar correo: {e}")




# utils.py

def calcular_precio_total(solicitud, proveedor):
    """
    Calcula el precio total de todos los productos asignados a un proveedor específico en una solicitud.
    """
    total = 0
    for pp in solicitud.productos_proveedores:
        if pp.proveedor_id == proveedor.id:
            total += pp.precio_ofrecido * pp.cantidad
    return total

def calcular_tiempo_entrega(solicitud, proveedor):
    """
    Calcula el tiempo de entrega más largo entre todos los productos asignados a un proveedor específico en una solicitud.
    """
    tiempos = []
    for pp in solicitud.productos_proveedores:
        if pp.proveedor_id == proveedor.id and pp.tiempo_estimado_envio is not None:
            tiempos.append(pp.tiempo_estimado_envio)
    return max(tiempos) if tiempos else "N/A"


def calcular_precio_total(solicitud, proveedor):
    total = 0
    for pp in solicitud.productos_proveedores:
        if pp.proveedor_id == proveedor.id:
            total += pp.precio_ofrecido * pp.cantidad
    return total


def calcular_tiempo_entrega(solicitud, proveedor):
    tiempos = [pp.tiempo_estimado_envio for pp in solicitud.productos_proveedores if pp.proveedor_id == proveedor.id]
    return max(tiempos) if tiempos else 'N/A'
