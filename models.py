# models.py

from extensions import db, bcrypt
from flask_login import UserMixin
from datetime import datetime
from sqlalchemy import event
from flask import current_app
from sqlalchemy import text

class Usuario(db.Model, UserMixin):
    __tablename__ = 'usuarios'
    
    id = db.Column(db.Integer, primary_key=True)
    nombre_usuario = db.Column(db.String(150), unique=True, nullable=False)
    correo = db.Column(db.String(150), unique=True, nullable=False)
    contraseña_hash = db.Column(db.String(128), nullable=False)
    rol = db.Column(db.String(50), nullable=False)  # Roles: usuario, revisor, supervisor, admin, bodeguero

    # Relaciones
    proveedores = db.relationship('Proveedor', back_populates='creador', cascade='all, delete-orphan')
    solicitudes = db.relationship('Solicitud', back_populates='solicitante', cascade='all, delete-orphan')
    aprobaciones = db.relationship('Aprobacion', back_populates='revisador', cascade='all, delete-orphan')
    ordenes_compra_recibidas = db.relationship('OrdenCompra', back_populates='usuario_recepcion', foreign_keys='OrdenCompra.recibido_por')
    recepciones = db.relationship('Recepcion', back_populates='usuario', lazy=True)  # Relación con Recepcion

    def set_password(self, password):
        self.contraseña_hash = bcrypt.generate_password_hash(password).decode('utf-8')
    
    def check_password(self, password):
        return bcrypt.check_password_hash(self.contraseña_hash, password)
    
    def __repr__(self):
        return f"<Usuario {self.nombre_usuario}>"

class Proveedor(db.Model):
    __tablename__ = 'proveedores'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False)
    correo = db.Column(db.String(150), unique=True, nullable=False)
    telefono = db.Column(db.String(20), nullable=False)
    direccion = db.Column(db.String(250), nullable=False)
    descripcion = db.Column(db.Text, nullable=True)  # Campo opcional para descripción
    creado_por = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)

    # Relaciones
    creador = db.relationship('Usuario', back_populates='proveedores')  # Relación inversa
    productos_proveedores = db.relationship('ProductoProveedor', back_populates='proveedor', cascade='all, delete-orphan')
    ordenes_compra = db.relationship('OrdenCompra', back_populates='proveedor')
    
    def __repr__(self):
        return f"<Proveedor {self.nombre}>"

class CentroCosto(db.Model):
    __tablename__ = 'centros_costo'
    
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False)
    descripcion = db.Column(db.Text, nullable=True)
    
    # Relaciones
    solicitudes = db.relationship('Solicitud', back_populates='centro_costo', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f"<CentroCosto {self.nombre}>"

class Solicitud(db.Model):
    __tablename__ = 'solicitudes'
    
    id = db.Column(db.Integer, primary_key=True)
    solicitante_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    centro_costo_id = db.Column(db.Integer, db.ForeignKey('centros_costo.id'), nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    tiempo_estimado = db.Column(db.Integer, nullable=True)  # Tiempo en días
    estado = db.Column(db.String(20), nullable=False, default='Pendiente')  # Estados: Pendiente, Aprobada, Rechazada, Recepcionado, Completada
    gasto_total = db.Column(db.Float, nullable=False, default=0.0)  # Añadido
    proveedor_seleccionado_id = db.Column(db.Integer, db.ForeignKey('proveedores.id'), nullable=True)
    proveedor_seleccionado = db.relationship('Proveedor', foreign_keys=[proveedor_seleccionado_id])
    fecha_aprobacion = db.Column(db.DateTime, nullable=True)
    
    # Relaciones
    solicitante = db.relationship('Usuario', back_populates='solicitudes')
    centro_costo = db.relationship('CentroCosto', back_populates='solicitudes')

    productos_solicitudes = db.relationship('ProductoSolicitud', back_populates='solicitud', cascade='all, delete-orphan')
    productos_proveedores = db.relationship('ProductoProveedor', back_populates='solicitud', cascade='all, delete-orphan')
    aprobaciones = db.relationship('Aprobacion', back_populates='solicitud', cascade='all, delete-orphan')
    ordenes_compra = db.relationship('OrdenCompra', back_populates='solicitud', cascade="all, delete-orphan")
    recepciones = db.relationship('Recepcion', back_populates='solicitud', cascade="all, delete-orphan")
    def calcular_gasto_total(self):
        self.gasto_total = sum(
            pp.cantidad * pp.precio_ofrecido
            for pp in self.productos_proveedores
            if pp.precio_ofrecido is not None
        )
    
    def __repr__(self):
        return f"<Solicitud {self.id} - {self.estado}>"
  
class Producto(db.Model):
    __tablename__ = 'productos'
    
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False, unique=True, index=True)
    descripcion = db.Column(db.Text, nullable=True)
    especificaciones = db.Column(db.Text, nullable=True)
    cantidad = db.Column(db.Integer, nullable=False, default=1)
    categoria_id = db.Column(db.Integer, db.ForeignKey('categorias.id'), nullable=False)
    inventario = db.relationship('Inventario', backref='producto', uselist=False)
    # Relaciones
    categoria = db.relationship('Categoria', back_populates='productos')
    # Relaciones
    productos_solicitudes = db.relationship('ProductoSolicitud', back_populates='producto', cascade='all, delete-orphan')
    productos_proveedores = db.relationship('ProductoProveedor', back_populates='producto', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f"<Producto {self.nombre}>"
    
    
class Categoria(db.Model):
    __tablename__ = 'categorias'
    
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False, unique=True)
    descripcion = db.Column(db.Text, nullable=True)
    
    # Relaciones
    productos = db.relationship('Producto', back_populates='categoria', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f"<Categoria {self.nombre}>"
    
class ProductoSolicitud(db.Model):
    __tablename__ = 'productos_solicitudes'
    
    id = db.Column(db.Integer, primary_key=True)
    solicitud_id = db.Column(db.Integer, db.ForeignKey('solicitudes.id'), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False, default=1)
    cantidad_recibida = db.Column(
        db.Integer,
        nullable=False,
        server_default=text('0')  # Valor por defecto a nivel de base de datos
    )
    
    # Relaciones
    solicitud = db.relationship('Solicitud', back_populates='productos_solicitudes')
    producto = db.relationship('Producto', back_populates='productos_solicitudes')
    
    def __repr__(self):
        return f"<ProductoSolicitud Solicitud {self.solicitud_id} - Producto {self.producto_id}>"

class ProductoProveedor(db.Model):
    __tablename__ = 'productos_proveedores'
    
    id = db.Column(db.Integer, primary_key=True)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False)  # Corregido
    proveedor_id = db.Column(db.Integer, db.ForeignKey('proveedores.id'), nullable=False)
    solicitud_id = db.Column(db.Integer, db.ForeignKey('solicitudes.id'), nullable=False)
    correo_enviado = db.Column(db.Boolean, default=False)
    cantidad = db.Column(db.Integer, nullable=False, default=1)
    precio_ofrecido = db.Column(db.Float, nullable=True)
    tiempo_estimado_envio = db.Column(db.Integer, nullable=True)
    
    # Relaciones
    solicitud = db.relationship('Solicitud', back_populates='productos_proveedores')
    producto = db.relationship('Producto', back_populates='productos_proveedores')
    proveedor = db.relationship('Proveedor', back_populates='productos_proveedores')
    
    def __repr__(self):
        return f"<ProductoProveedor Solicitud {self.solicitud_id} - Producto {self.producto_id} - Proveedor {self.proveedor_id}>"

class Aprobacion(db.Model):
    __tablename__ = 'aprobaciones'
    
    id = db.Column(db.Integer, primary_key=True)
    solicitud_id = db.Column(db.Integer, db.ForeignKey('solicitudes.id'), nullable=False)
    revisador_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    estado = db.Column(db.String(20), nullable=False, default='Pendiente')  # Estados: Pendiente, Aprobada, Rechazada
    comentario = db.Column(db.Text, nullable=True)
    fecha_aprobacion = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    tiempo_estimado_envio = db.Column(db.Integer, nullable=True)  # Tiempo en días
    
    # Relaciones
    solicitud = db.relationship('Solicitud', back_populates='aprobaciones')
    revisador = db.relationship('Usuario', back_populates='aprobaciones')
    
    def __repr__(self):
        return f"<Aprobacion {self.id} - Solicitud {self.solicitud_id} - {self.estado}>"

class OrdenCompra(db.Model):
    __tablename__ = 'ordenes_compra'
    id = db.Column(db.Integer, primary_key=True)
    solicitud_id = db.Column(db.Integer, db.ForeignKey('solicitudes.id'), nullable=False)
    proveedor_id = db.Column(db.Integer, db.ForeignKey('proveedores.id'), nullable=False)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    estado = db.Column(db.String(20), nullable=False, default='Generada')  # Estados: Generada, Enviada, Recepcionada, etc.
    fecha_recepcion = db.Column(db.DateTime, nullable=True)
    recibido_por = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)

    # Relaciones
    solicitud = db.relationship('Solicitud', back_populates='ordenes_compra')
    proveedor = db.relationship('Proveedor', back_populates='ordenes_compra')
    usuario_recepcion = db.relationship('Usuario', back_populates='ordenes_compra_recibidas', foreign_keys=[recibido_por])
    productos_orden = db.relationship('ProductoOrdenCompra', backref='orden_compra', lazy=True)
    recepcion = db.relationship('Recepcion', back_populates='orden_compra', uselist=False)
    def __repr__(self):
        return f"<OrdenCompra {self.id}>"

class ProductoOrdenCompra(db.Model):
    __tablename__ = 'producto_orden_compra'  # Nombre de tabla en minúsculas y con guiones bajos

    id = db.Column(db.Integer, primary_key=True)
    orden_compra_id = db.Column(db.Integer, db.ForeignKey('ordenes_compra.id'), nullable=False)  # Corregido
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False)  # Corregido
    cantidad = db.Column(db.Integer, nullable=False)
    precio = db.Column(db.Float, nullable=False)
    
    # Relaciones
    producto = db.relationship('Producto', backref=db.backref('productos_orden_compra', lazy=True))


class ProductoRecepcion(db.Model):
    __tablename__ = 'productos_recepcionados'
    
    id = db.Column(db.Integer, primary_key=True)
    recepcion_id = db.Column(db.Integer, db.ForeignKey('recepciones.id'), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False)
    cantidad_recibida = db.Column(db.Integer, nullable=False, default=0)
    
    # Relaciones
    recepcion = db.relationship('Recepcion', back_populates='productos_recepcionados')
    producto = db.relationship('Producto', backref='productos_recepcionados')
    
    def __repr__(self):
        return f"<ProductoRecepcion Recepcion {self.recepcion_id} - Producto {self.producto_id}>"
class Recepcion(db.Model):
    __tablename__ = 'recepciones'
    
    id = db.Column(db.Integer, primary_key=True)
    orden_compra_id = db.Column(db.Integer, db.ForeignKey('ordenes_compra.id'), nullable=False)
    fecha_recepcion = db.Column(db.DateTime, default=datetime.utcnow)
    comentario_general = db.Column(db.Text, nullable=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    solicitud_id = db.Column(db.Integer, db.ForeignKey('solicitudes.id'), nullable=False)
    
    # Relaciones
    orden_compra = db.relationship('OrdenCompra', back_populates='recepcion')
    usuario = db.relationship('Usuario', back_populates='recepciones')
    productos_recepcionados = db.relationship('ProductoRecepcion', back_populates='recepcion', cascade="all, delete-orphan")
    solicitud = db.relationship('Solicitud', back_populates='recepciones')
    
    def __repr__(self):
        return f"<Recepcion {self.id} - OrdenCompra {self.orden_compra_id}>"




class Inventario(db.Model):
    __tablename__ = 'inventario'
    id = db.Column(db.Integer, primary_key=True)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False, unique=True)

    cantidad = db.Column(db.Integer, nullable=False, default=0)
    fecha_actualizacion = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    umbral_minimo = db.Column(db.Integer, nullable=False, default=10)  # Umbral para alertas

class MovimientoInventario(db.Model):
    __tablename__ = 'movimiento_inventario'
    id = db.Column(db.Integer, primary_key=True)
    inventario_id = db.Column(db.Integer, db.ForeignKey('inventario.id'), nullable=False)
    tipo = db.Column(db.String(10), nullable=False)  # 'entrada' o 'salida'
    cantidad = db.Column(db.Integer, nullable=False)
    fecha = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    descripcion = db.Column(db.String(255))  # Opcional: Razón del movimiento

    inventario = db.relationship('Inventario', backref=db.backref('movimientos', lazy=True))

# Evento para actualizar gasto_total al modificar ProductoSolicitud
@event.listens_for(ProductoSolicitud, 'after_insert')
@event.listens_for(ProductoSolicitud, 'after_update')
@event.listens_for(ProductoSolicitud, 'after_delete')
def actualizar_gasto_total(mapper, connection, target):
    solicitud_id = target.solicitud_id
    solicitud = Solicitud.query.get(solicitud_id)
    if solicitud:
        solicitud.calcular_gasto_total()
        # No realices un commit aquí
        current_app.logger.info(f"Gasto Total recalculado para Solicitud ID: {solicitud_id}")
