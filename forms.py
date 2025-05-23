# forms.py
from datetime import datetime
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, TextAreaField, IntegerField, SelectField, SelectMultipleField
from wtforms.validators import DataRequired, Email, EqualTo, ValidationError, NumberRange
from models import Usuario, CentroCosto, Producto, Proveedor
from wtforms import HiddenField, RadioField, BooleanField, FloatField
from flask_login import current_user
from wtforms.validators import Optional, Length
from flask_wtf import FlaskForm
from wtforms import Form, SelectField, IntegerField, SubmitField,FieldList,FormField
from wtforms.validators import DataRequired, NumberRange
from wtforms import DateField

class RegisterForm(FlaskForm):
    nombre_usuario = StringField('Nombre de Usuario', validators=[DataRequired(), Length(min=4, max=150)])
    correo = StringField('Correo Electrónico', validators=[DataRequired(), Email(), Length(max=150)])
    contraseña = PasswordField('Contraseña', validators=[DataRequired(), Length(min=6)])
    confirmar_contraseña = PasswordField('Confirmar Contraseña', validators=[DataRequired(), EqualTo('contraseña')])
    rol = StringField('Rol', validators=[DataRequired(), Length(max=50)])  # Ejemplo: solicitante, revisor, supervisor
    submit = SubmitField('Registrar')
    
    def validate_nombre_usuario(self, nombre_usuario):
        usuario = Usuario.query.filter_by(nombre_usuario=nombre_usuario.data).first()
        if usuario:
            raise ValidationError('Este nombre de usuario ya está en uso. Por favor, elige otro.')
    
    def validate_correo(self, correo):
        usuario = Usuario.query.filter_by(correo=correo.data).first()
        if usuario:
            raise ValidationError('Este correo ya está registrado. Por favor, usa otro correo.')


class LoginForm(FlaskForm):
    nombre_usuario = StringField('Nombre de Usuario', validators=[DataRequired(), Length(min=4, max=150)])
    contraseña = PasswordField('Contraseña', validators=[DataRequired(), Length(min=6)])
    remember_me = BooleanField('Recuérdame')  # Campo agregado
    submit = SubmitField('Iniciar Sesión')




class ProductoForm(FlaskForm):
    nombre = StringField('Nombre', validators=[DataRequired(), Length(max=150)])
    descripcion = TextAreaField('Descripción', validators=[Length(max=500)])
    especificaciones = TextAreaField('Especificaciones', validators=[Length(max=1000)])
    cantidad = IntegerField('Cantidad', validators=[DataRequired(), NumberRange(min=1)])
    submit = SubmitField('Crear Producto')
    categoria = SelectField('Categoría', validators=[DataRequired()], coerce=int)
    def validate_nombre(self, nombre):
        producto = Producto.query.filter_by(nombre=nombre.data).first()
        if producto:
            raise ValidationError('Ya existe un producto con este nombre. Por favor, elige otro nombre.')

class EliminarProductoForm(FlaskForm):
    submit = SubmitField('Eliminar')
# forms.py



class DeleteForm(FlaskForm):
    id = HiddenField('ID', validators=[DataRequired()])
    submit = SubmitField('Eliminar')


class CategoriaForm(FlaskForm):
    id = HiddenField('ID')  # Para operaciones de edición y eliminación
    nombre = StringField('Nombre de la Categoría', validators=[DataRequired(), Length(max=150)])
    descripcion = TextAreaField('Descripción', validators=[Length(max=500)])
    submit = SubmitField('Guardar')


class DeleteCategoriaForm(FlaskForm):
    id = HiddenField('ID', validators=[DataRequired()])
    submit = SubmitField('Eliminar')

class ProductoCantidadForm(FlaskForm):
    categoria = SelectField(
        'Categoría',
        validators=[DataRequired(message="Seleccione una categoría.")],
        coerce=int  # Convierte el valor seleccionado a entero
    )
    producto = SelectField(
        'Producto',
        validators=[DataRequired(message="Seleccione un producto.")],
        coerce=int
    )
    cantidad = IntegerField(
        'Cantidad',
        validators=[
            DataRequired(message="Ingrese una cantidad."),
            NumberRange(min=1, message="La cantidad debe ser al menos 1.")
        ]
    )
    eliminar = SubmitField('Eliminar')
class SolicitudForm(FlaskForm):
    fecha = DateField(
        'Fecha',
        format='%Y-%m-%d',
        default=datetime.utcnow,
        render_kw={"readonly": True}
    )
    centro_costo = SelectField(
        'Centro de Costo',
        validators=[DataRequired(message="Seleccione un centro de costo.")],
        coerce=int
    )
    productos = FieldList(
        FormField(ProductoCantidadForm),
        min_entries=1,
        max_entries=10
    )
    submit = SubmitField('Crear Solicitud')


class ProductoSeleccionadoForm(FlaskForm):
    producto_id = HiddenField('ID del Producto', validators=[DataRequired()])
    nombre_producto = HiddenField('Nombre del Producto', validators=[DataRequired()])
    precio_unitario = HiddenField('Precio Unitario', validators=[DataRequired()])
    cantidad = IntegerField('Cantidad', validators=[DataRequired(), NumberRange(min=1)], default=1)    

    def __init__(self, *args, **kwargs):
        super(SolicitudForm, self).__init__(*args, **kwargs)
        self.centro_costo.choices = [(cc.id, cc.nombre) for cc in CentroCosto.query.all()]
        self.productos.choices = [(p.id, p.nombre) for p in Producto.query.all()]

class CentroCostoForm(FlaskForm):
    nombre = StringField('Nombre', validators=[DataRequired()])
    descripcion = TextAreaField('Descripción')
    submit = SubmitField('Crear Centro de Costo')

class ProveedorForm(FlaskForm):
    nombre = StringField('Nombre', validators=[DataRequired(), Length(min=2, max=150)])
    correo = StringField('Correo Electrónico', validators=[DataRequired(), Email(), Length(max=150)])
    telefono = StringField('Teléfono', validators=[DataRequired(), Length(min=7, max=20)])
    direccion = StringField('Dirección', validators=[DataRequired(), Length(min=5, max=200)])
    descripcion = TextAreaField('Descripción', validators=[DataRequired(), Length(min=10)])
    submit = SubmitField('Crear Proveedor')
    
    def validate_correo(self, correo):
        proveedor = Proveedor.query.filter_by(correo=correo.data).first()
        if proveedor:
            raise ValidationError('Este correo ya está registrado para otro proveedor. Por favor, usa otro correo.')

class EliminarProveedorForm(FlaskForm):
    proveedor_id = HiddenField('Proveedor ID')
    producto_id = HiddenField('Producto ID')
    submit = SubmitField('Eliminar')

# forms.py

class AsignarProveedoresForm(FlaskForm):
    proveedor_id = SelectField('Proveedor', coerce=int, validators=[DataRequired()])
    cantidad = IntegerField('Cantidad', validators=[DataRequired(), NumberRange(min=1)])
    submit = SubmitField('Asignar Proveedor')

class AprobacionForm(FlaskForm):
    proveedor_seleccionado_1 = SelectField(
        'Seleccionar Primer Proveedor',
        validators=[DataRequired()],
        coerce=int
    )
    proveedor_seleccionado_2 = SelectField(
        'Seleccionar Segundo Proveedor (Opcional)',
        validators=[Optional()],
        coerce=int,
        choices=[(0, 'Ninguno')]
    )
    comentario = StringField('Comentario', validators=[Optional()])
    submit = SubmitField('Aprobar Solicitud')

    def validate_proveedor_seleccionado_2(self, field):
        if field.data != 0 and field.data == self.proveedor_seleccionado_1.data:
            raise ValidationError('El segundo proveedor debe ser diferente al primero.')
        
class RechazarForm(FlaskForm):
    comentario = StringField('Comentario', validators=[DataRequired()])
    submit = SubmitField('Rechazar Solicitud')        

from flask_wtf import FlaskForm
from wtforms import SelectField, IntegerField, FloatField, SubmitField, DecimalField
from wtforms.validators import DataRequired, NumberRange

class AprobarSolicitudForm(FlaskForm):
    comentario = TextAreaField('Comentario de Aprobación', validators=[DataRequired()])
    submit = SubmitField('Aprobar Solicitud')
class AsignarPreciosForm(FlaskForm):
    proveedor_id = SelectField('Proveedor', coerce=int, validators=[DataRequired()])
    cantidad = IntegerField('Cantidad', validators=[DataRequired(), NumberRange(min=1, message="La cantidad debe ser al menos 1.")])
    precio_ofrecido = DecimalField('Precio Ofrecido', validators=[Optional()])  # Cambiado a Optional
    tiempo_estimado_envio = IntegerField('Tiempo Estimado de Envío (días)', validators=[DataRequired(), NumberRange(min=1, message="El tiempo estimado debe ser al menos 1 día.")])
    submit = SubmitField('Asignar')

class EnviarCorreoForm(FlaskForm):
    submit = SubmitField('Enviar Correo')

class EditarProductoProveedorForm(FlaskForm):
    precio_ofrecido = FloatField('Precio Ofrecido ($)', validators=[
        DataRequired(message="El precio es obligatorio."),
        NumberRange(min=0.0, message="El precio debe ser un número positivo.")
    ])
    tiempo_estimado_envio = IntegerField('Tiempo Estimado de Envío (días)', validators=[
        DataRequired(message="El tiempo estimado es obligatorio."),
        NumberRange(min=1, message="El tiempo estimado debe ser al menos 1 día.")
    ])
    submit = SubmitField('Guardar Cambios')

class SeleccionarProveedorForm(FlaskForm):
    proveedor = SelectField('Proveedor', coerce=int, validators=[DataRequired(message="Debes seleccionar un proveedor.")])
    submit = SubmitField('Seleccionar Proveedor')


class ProductoRecepcionForm(FlaskForm):
    producto_id = HiddenField('Producto ID', validators=[DataRequired()])
    recibido = BooleanField('Recibido')

class RecepcionarOrdenForm(FlaskForm):
    productos = FieldList(FormField(ProductoRecepcionForm))
    comentario_general = TextAreaField('Comentarios Generales', validators=[Optional()])
    submit = SubmitField('Confirmar Recepción')


class SeleccionarProveedorForm(FlaskForm):
    proveedor_seleccionado = RadioField('Proveedor', coerce=int, validators=[DataRequired(message="Debes seleccionar un proveedor.")])
    submit = SubmitField('Seleccionar Proveedor')


# forms.py

class IngresarCotizacionForm(FlaskForm):
    precio_ofrecido = DecimalField('Precio Ofrecido', validators=[DataRequired(), NumberRange(min=0)])
    tiempo_estimado_envio = IntegerField('Tiempo Estimado de Envío (días)', validators=[DataRequired(), NumberRange(min=0)])
    submit = SubmitField('Guardar Cotización')

class AjusteInventarioForm(FlaskForm):
    producto_id = IntegerField('ID Producto', validators=[DataRequired()])
    cantidad = IntegerField('Cantidad', validators=[DataRequired(), NumberRange(min=0)])
    descripcion = StringField('Descripción')  # Opcional
    submit = SubmitField('Actualizar Inventario')


class ReporteInventarioForm(FlaskForm):
    fecha_inicio = DateField('Fecha de Inicio', format='%Y-%m-%d', validators=[DataRequired()])
    fecha_fin = DateField('Fecha de Fin', format='%Y-%m-%d', validators=[DataRequired()])
    submit = SubmitField('Generar Reporte')


class EditarInventarioForm(FlaskForm):
    cantidad = IntegerField('Cantidad Disponible', validators=[
        DataRequired(message="La cantidad es requerida."),
        NumberRange(min=0, message="La cantidad debe ser positiva.")
    ])
    umbral_minimo = IntegerField('Umbral Mínimo', validators=[
        DataRequired(message="El umbral mínimo es requerido."),
        NumberRange(min=0, message="El umbral mínimo debe ser positivo.")
    ])
    submit = SubmitField('Guardar Cambios')



class EliminarInventarioForm(FlaskForm):
    pass