import io
from io import BytesIO
from flask import Blueprint, render_template, redirect, send_file, url_for, flash, request, make_response,current_app
from flask_login import login_user, current_user, logout_user, login_required
from extensions import db
from models import ProductoOrdenCompra, Usuario, Producto, Solicitud, CentroCosto, Proveedor, ProductoSolicitud, ProductoProveedor, Aprobacion, OrdenCompra, Recepcion, Categoria, Inventario, MovimientoInventario
from forms import  LoginForm, ProductoForm, SolicitudForm, CentroCostoForm, ProveedorForm, AsignarProveedoresForm, EliminarProveedorForm, AprobacionForm, EliminarProductoForm, RegisterForm, EnviarCorreoForm, EditarProductoProveedorForm, AsignarPreciosForm, SeleccionarProveedorForm, RecepcionarOrdenForm, ProductoRecepcionForm, IngresarCotizacionForm, CategoriaForm, DeleteCategoriaForm, DeleteForm, AjusteInventarioForm, ReporteInventarioForm, EliminarInventarioForm, EditarInventarioForm, RechazarForm
from datetime import datetime
import pandas as pd
from flask_mail import Message
from flask_mail import Message
from sqlalchemy.orm import joinedload
from sqlalchemy import func, and_
from sqlalchemy.exc import SQLAlchemyError
from extensions import mail
import os
# from helpers import slugify # Comentado si no se usa directamente en este archivo
from flask import jsonify
from datetime import datetime, timedelta
import base64
from decorators import roles_required
from forms import AprobacionForm
from sqlalchemy.exc import IntegrityError
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
# import io # Ya importado desde BytesIO
from flask_paginate import Pagination




main = Blueprint('main', __name__)


@main.app_context_processor
def add_calculation_functions():
    def calcular_precio_total(solicitud, proveedor):
        total = sum(
            pp.precio_ofrecido * pp.cantidad
            for pp in solicitud.productos_proveedores
            if pp.proveedor_id == proveedor.id and pp.precio_ofrecido is not None
        )
        return total

    def calcular_tiempo_entrega(solicitud, proveedor):
        tiempos = [
            pp.tiempo_estimado_envio
            for pp in solicitud.productos_proveedores
            if pp.proveedor_id == proveedor.id and pp.tiempo_estimado_envio is not None
        ]
        return max(tiempos) if tiempos else None

    return dict(
        calcular_precio_total=calcular_precio_total,
        calcular_tiempo_entrega=calcular_tiempo_entrega
    )

    






@main.route('/')
@main.route('/index')
@login_required
def index():
    # Verificar roles si es necesario
    if current_user.rol not in ['admin', 'supervisor', 'revisor','solicitante']:
        flash('No tienes permisos para acceder al dashboard.', 'danger')
        return redirect(url_for('main.perfil'))  # Esto puede causar un bucle si no se maneja correctamente
    
    # Consulta para obtener gastos totales
    gastos_totales = db.session.query(func.sum(Solicitud.gasto_total)).scalar() or 0
    
    # Consulta para obtener número total de solicitudes
    total_solicitudes = db.session.query(func.count(Solicitud.id)).scalar() or 0
    
    # Consulta para obtener productos más comprados (top 5)
    productos_mas_comprados_query = db.session.query(
        Producto.nombre,
        func.count(ProductoSolicitud.solicitud_id)
    ).join(ProductoSolicitud).join(Solicitud).group_by(Producto.nombre).order_by(func.count(ProductoSolicitud.solicitud_id).desc()).limit(5).all()
    
    productos_mas_comprados = [{'nombre': item[0], 'cantidad': item[1]} for item in productos_mas_comprados_query]
    
    return render_template(
        'index.html',
        active_page='inicio',
        gastos_totales=gastos_totales,
        total_solicitudes=total_solicitudes,
        productos_mas_comprados=productos_mas_comprados
    )


@main.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        flash('Ya estás registrado y autenticado.', 'info')
        return redirect(url_for('main.index'))
    
    form = RegisterForm()
    if form.validate_on_submit():
        try:
            nuevo_usuario = Usuario(
                nombre_usuario=form.nombre_usuario.data,
                correo=form.correo.data,
                rol=form.rol.data
            )
            nuevo_usuario.set_password(form.contraseña.data)

            db.session.add(nuevo_usuario)
            db.session.commit()
            flash('Cuenta creada exitosamente. Ahora puedes iniciar sesión.', 'success')
            return redirect(url_for('main.login'))
        except IntegrityError as e:
            db.session.rollback()
            # Manejar errores específicos, como correo o nombre de usuario duplicado
            if 'unique constraint' in str(e).lower():
                flash('El correo o nombre de usuario ya existe. Por favor, usa otros valores.', 'danger')
            else:
                flash('Error al crear la cuenta. Por favor, verifica los datos ingresados.', 'danger')
    
    return render_template('register.html', form=form)



@main.route('/list_routes')
def list_routes():
    import urllib
    output = []
    for rule in current_app.url_map.iter_rules():
        methods = ','.join(sorted(rule.methods))
        url = url_for(rule.endpoint, **(rule.defaults or {}))
        line = f'{rule.endpoint:50s} {methods:20s} {url}'
        output.append(urllib.parse.quote(line))
    return '<br>'.join(output)


@main.route('/dashboard')
@login_required
def dashboard():
    # Verificar roles si es necesario
    if current_user.rol not in ['admin', 'supervisor', 'revisor']:
        flash('No tienes permisos para acceder al dashboard.', 'danger')
        return redirect(url_for('main.index'))
    
    return render_template('dashboard.html', active_page='dashboard')

@main.route('/test_route')
def test_route():
    return "Ruta de prueba funcionando correctamente."

@main.route('/api/dashboard-data')
@login_required
def dashboard_data():
    try:
        # Gastos totales
        gastos_totales = db.session.query(func.sum(Solicitud.gasto_total)).scalar() or 0
        current_app.logger.info(f'Gastos Totales: {gastos_totales}')
    
        # Compras por centro de costo
        compras_por_centro = db.session.query(
            CentroCosto.nombre,
            func.sum(Solicitud.gasto_total)
        ).join(Solicitud, CentroCosto.id == Solicitud.centro_costo_id).group_by(CentroCosto.nombre).all()
        centros = [item[0] for item in compras_por_centro]
        gastos_centros = [float(item[1]) for item in compras_por_centro]
        current_app.logger.info(f'Compras por Centro: {centros} - {gastos_centros}')
    
        # Gastos mensuales (últimos 12 meses)
        hace_12_meses = datetime.utcnow() - timedelta(days=365)
        gastos_mensuales_query = db.session.query(
            func.concat(
                func.extract('year', Solicitud.fecha), '-',
                func.lpad(func.extract('month', Solicitud.fecha), 2, '0')
            ).label('mes'),
            func.sum(Solicitud.gasto_total)
        ).filter(
            Solicitud.fecha >= hace_12_meses
        ).group_by('mes').order_by('mes').all()
        
        meses = [item[0] for item in gastos_mensuales_query]
        gastos_mensuales = [float(item[1]) for item in gastos_mensuales_query]
        current_app.logger.info(f'Gastos Mensuales: {meses} - {gastos_mensuales}')
    
        # Número total de solicitudes
        total_solicitudes = db.session.query(func.count(Solicitud.id)).scalar() or 0
        current_app.logger.info(f'Total Solicitudes: {total_solicitudes}')
    
        return jsonify({
            'gastos_totales': gastos_totales,
            'compras_por_centro': {
                'centros': centros,
                'gastos': gastos_centros
            },
            'gastos_mensuales': {
                'meses': meses,
                'gastos': gastos_mensuales
            },
            'total_solicitudes': total_solicitudes,
        })
    except Exception as e:
        current_app.logger.error(f'Error en dashboard_data: {e}')
        return jsonify({'error': 'Ocurrió un error al obtener los datos del dashboard.'}), 500
@main.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        flash('Ya estás autenticado.', 'info')
        return redirect(url_for('main.index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        usuario = Usuario.query.filter_by(nombre_usuario=form.nombre_usuario.data).first()
        if usuario and usuario.check_password(form.contraseña.data):
            login_user(usuario, remember=form.remember_me.data)
            flash('Has iniciado sesión exitosamente.', 'success')
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('main.index'))
        else:
            flash('Nombre de usuario o contraseña incorrectos.', 'danger')
    
    return render_template('login.html', form=form)

@main.route('/logout')
def logout():
    logout_user()
    flash('Has cerrado sesión correctamente.', 'info')
    return redirect(url_for('main.index'))

@main.route('/perfil')
@login_required
def perfil():
    return render_template('perfil.html')


# routes.py
@main.route('/obtener_productos_por_categoria', methods=['GET'])
@login_required
def obtener_productos_por_categoria():
    categoria_id = request.args.get('categoria_id', type=int)
    productos = []
    if categoria_id:
        productos_bd = Producto.query.filter_by(categoria_id=categoria_id).all()
        for producto in productos_bd:
            productos.append({'id': producto.id, 'nombre': producto.nombre})
    return jsonify({'productos': productos})

@main.route('/editar_producto/<int:producto_id>', methods=['GET', 'POST'])
@login_required
def editar_producto(producto_id):
    if current_user.rol not in ['admin', 'supervisor', 'revisor']:
        flash('No tienes permisos para editar este producto.', 'danger')
        return redirect(url_for('main.crear_producto'))
    
    producto = Producto.query.get_or_404(producto_id)
    form = ProductoForm(obj=producto)
    eliminar_form = EliminarProductoForm()

    if form.validate_on_submit():
        producto.nombre = form.nombre.data
        producto.descripcion = form.descripcion.data
        producto.especificaciones = form.especificaciones.data
        producto.cantidad = form.cantidad.data
        try:
            db.session.commit()
            flash('Producto actualizado exitosamente.', 'success')
            return redirect(url_for('main.crear_producto'))
        except IntegrityError as e:
            db.session.rollback()
            if 'uix_nombre' in str(e):
                flash('Ya existe un producto con este nombre. Por favor, elige otro nombre.', 'danger')
            else:
                flash('Error al actualizar el producto. Por favor, verifica los datos ingresados.', 'danger')
    
    return render_template('editar_producto.html', form=form, producto=producto, eliminar_form=eliminar_form)

@main.route('/crear_producto', methods=['GET', 'POST'])
@login_required
@roles_required('solicitante', 'revisor', 'admin','bodeguero')  # Permite creación para estos roles
def crear_producto():
    form = ProductoForm()
    eliminar_form = DeleteForm()  # Instanciar DeleteForm
    
    # Poblar las opciones de categoría
    categorias = Categoria.query.order_by(Categoria.nombre).all()
    form.categoria.choices = [(c.id, c.nombre) for c in categorias]
    
    if form.validate_on_submit():
        try:
            nuevo_producto = Producto(
                nombre=form.nombre.data.strip(),
                descripcion=form.descripcion.data.strip() if form.descripcion.data else None,
                especificaciones=form.especificaciones.data.strip() if form.especificaciones.data else None,
                cantidad=form.cantidad.data,
                categoria_id=form.categoria.data
            )
            db.session.add(nuevo_producto)
            db.session.commit()
            flash('Producto creado exitosamente.', 'success')
            return redirect(url_for('main.crear_producto'))
        except IntegrityError:
            db.session.rollback()
            flash('El nombre del producto ya existe. Por favor, elige otro nombre.', 'danger')
        except Exception as e:
            db.session.rollback()
            flash('Ocurrió un error al crear el producto. Por favor, inténtalo de nuevo.', 'danger')
            print(f"Error al crear producto: {e}")
    
    # Obtener todos los productos para mostrar en la tabla
    productos = Producto.query.order_by(Producto.id.desc()).all()
    
    return render_template('crear_producto.html', form=form, productos=productos, eliminar_form=eliminar_form)




@main.route('/ver_detalle_solicitud/<int:solicitud_id>', methods=['GET', 'POST'])
@login_required
def ver_detalle_solicitud(solicitud_id):
    solicitud = Solicitud.query.options(
        db.joinedload(Solicitud.productos_solicitudes).joinedload(ProductoSolicitud.producto),
        db.joinedload(Solicitud.productos_proveedores).joinedload(ProductoProveedor.proveedor),
        db.joinedload(Solicitud.productos_proveedores).joinedload(ProductoProveedor.producto),
        db.joinedload(Solicitud.aprobaciones).joinedload(Aprobacion.revisador)
    ).get_or_404(solicitud_id)

    # Verificar permisos adicionales si es necesario
    if solicitud.solicitante_id != current_user.id and current_user.rol not in ['revisor', 'supervisor', 'admin']:
        flash('No tienes permisos para ver esta solicitud.', 'danger')
        return redirect(url_for('main.index'))

    productos = solicitud.productos_solicitudes

    # Formularios
    asignar_form = AsignarProveedoresForm()
    asignar_form.proveedor_id.choices = [(p.id, p.nombre) for p in Proveedor.query.all()]

    eliminar_form = EliminarProveedorForm()
    aprobar_form = AprobacionForm()
    rechazar_form = RechazarForm()
    enviar_correo_form = EnviarCorreoForm()

    # Obtener proveedores asignados únicos
    proveedores_asignados = list({pp.proveedor for pp in solicitud.productos_proveedores if pp.proveedor})

    # Configurar los choices para ambos campos de proveedores en el formulario de aprobación
    aprobar_form.proveedor_seleccionado_1.choices = [(p.id, p.nombre) for p in proveedores_asignados]
    # Añadir la opción "Ninguno" al segundo campo
    aprobar_form.proveedor_seleccionado_2.choices = [(0, 'Ninguno')] + [(p.id, p.nombre) for p in proveedores_asignados]

    # Preparar detalles de los proveedores con sus ofertas
    proveedores_con_detalles = []
    for proveedor in proveedores_asignados:
        productos_proveedor = [pp for pp in solicitud.productos_proveedores if pp.proveedor_id == proveedor.id]
        total_precio = sum(pp.precio_ofrecido * pp.cantidad for pp in productos_proveedor if pp.precio_ofrecido)
        max_tiempo_envio = max([pp.tiempo_estimado_envio for pp in productos_proveedor if pp.tiempo_estimado_envio], default=0)
        proveedores_con_detalles.append({
            'proveedor': proveedor,
            'total_precio': total_precio,
            'tiempo_estimado_envio': max_tiempo_envio
        })

    # Crear una instancia de IngresarCotizacionForm para cada ProductoProveedor
    ingresar_cotizacion_forms = {}
    for pp in solicitud.productos_proveedores:
        if current_user.rol in ['revisor', 'supervisor', 'admin']:
            form = IngresarCotizacionForm(obj=pp)
            ingresar_cotizacion_forms[pp.id] = form

    # Manejar la sumisión de formularios de ingreso de cotizaciones
    if request.method == 'POST':
        if 'pp_id' in request.form:
            pp_id = int(request.form['pp_id'])
            pp = ProductoProveedor.query.get_or_404(pp_id)
            form = ingresar_cotizacion_forms[pp_id]

            if form.validate_on_submit():
                pp.precio_ofrecido = form.precio_ofrecido.data
                pp.tiempo_estimado_envio = form.tiempo_estimado_envio.data
                db.session.commit()
                flash('Cotización actualizada correctamente.', 'success')
                return redirect(url_for('main.ver_detalle_solicitud', solicitud_id=solicitud_id))
            else:
                flash('Error al actualizar la cotización.', 'danger')

    return render_template(
        'ver_detalle_solicitud.html',
        solicitud=solicitud,
        productos=productos,
        asignar_form=asignar_form,
        eliminar_form=eliminar_form,
        aprobar_form=aprobar_form,
        rechazar_form=rechazar_form,
        enviar_correo_form=enviar_correo_form,
        proveedores_asignados=proveedores_asignados,
        proveedores_con_detalles=proveedores_con_detalles,
        ingresar_cotizacion_forms=ingresar_cotizacion_forms
    )
# routes.py

@main.route('/seleccionar_proveedor/<int:solicitud_id>', methods=['POST'])
@login_required
@roles_required('revisor', 'supervisor', 'admin')  # Ajusta según tus roles
def seleccionar_proveedor_modal(solicitud_id):
    solicitud = Solicitud.query.get_or_404(solicitud_id)

    # Verificar permisos
    if current_user.rol not in ['revisor', 'supervisor', 'admin']:
        flash('No tienes permisos para seleccionar un proveedor.', 'danger')
        return redirect(url_for('main.index'))

    form = SeleccionarProveedorForm()
    form.proveedor_seleccionado.choices = [
        (pp.proveedor.id, pp.proveedor.nombre) for pp in solicitud.productos_proveedores
    ]

    if form.validate_on_submit():
        proveedor_id = form.proveedor_seleccionado.data

        # Actualizar la solicitud con el proveedor seleccionado
        solicitud.proveedor_seleccionado_id = proveedor_id
        solicitud.estado = 'Proveedor Seleccionado'

        try:
            db.session.commit()
            flash('Proveedor seleccionado correctamente.', 'success')
        except Exception as e:
            db.session.rollback()
            flash('Ocurrió un error al seleccionar el proveedor.', 'danger')
            print(f"Error al seleccionar proveedor: {e}")

    else:
        flash('Por favor, selecciona un proveedor.', 'danger')
        print(form.errors)

    return redirect(url_for('main.ver_detalle_solicitud', solicitud_id=solicitud_id))


@main.route('/crear_solicitud', methods=['GET', 'POST'])
@login_required
@roles_required('revisor', 'solicitante')  # Permitir ambos roles
def crear_solicitud():
    form = SolicitudForm()
    
    # Asignar choices al campo centro_costo
    centros_costo = CentroCosto.query.all()
    form.centro_costo.choices = [(cc.id, cc.nombre) for cc in centros_costo]
    
    # Obtener todas las categorías
    categorias = Categoria.query.all()
    
    form.productos.max_entries = 10  # Mantener max_entries si es necesario
    
    # Asignar categorías y productos a cada producto_form en productos
    for producto_form in form.productos:
        # Asignar choices de categorías
        producto_form.categoria.choices = [(c.id, c.nombre) for c in categorias]
        
        # Si hay una categoría seleccionada, filtrar los productos
        if producto_form.categoria.data:
            productos_filtrados = Producto.query.filter_by(categoria_id=producto_form.categoria.data).all()
        else:
            productos_filtrados = []
        producto_form.producto.choices = [(p.id, p.nombre) for p in productos_filtrados]
    
    if request.method == 'POST':
        # Actualizar los choices basados en la categoría seleccionada en el POST
        for producto_form in form.productos:
            if producto_form.categoria.data:
                productos_filtrados = Producto.query.filter_by(categoria_id=producto_form.categoria.data).all()
                producto_form.producto.choices = [(p.id, p.nombre) for p in productos_filtrados]
            else:
                producto_form.producto.choices = []
        
        if form.validate_on_submit():
            try:
                # Crear una nueva solicitud con estado 'Pendiente'
                nueva_solicitud = Solicitud(
                    solicitante_id=current_user.id,
                    centro_costo_id=form.centro_costo.data,
                    fecha=form.fecha.data,  # Asigna la fecha desde el formulario
                    estado='Pendiente',
                    gasto_total=0.0
                )
                db.session.add(nueva_solicitud)
                db.session.commit()
                
                # Añadir productos a la solicitud
                for producto_form in form.productos:
                    producto_id = producto_form.producto.data
                    cantidad = producto_form.cantidad.data
                    producto_solicitud = ProductoSolicitud(
                        solicitud_id=nueva_solicitud.id,
                        producto_id=producto_id,
                        cantidad=cantidad
                    )
                    db.session.add(producto_solicitud)
                
                # Calcular y actualizar gasto_total basado en los productos
                nueva_solicitud.calcular_gasto_total()
                db.session.commit()
                
                flash('Solicitud creada exitosamente.', 'success')
                return redirect(url_for('main.crear_solicitud'))
            
            except SQLAlchemyError as e:
                db.session.rollback()
                flash(f'Ocurrió un error al crear la solicitud: {str(e)}', 'danger')
    
    return render_template('crear_solicitud.html', form=form)


@main.route('/asignar_proveedor_modal/<int:solicitud_id>/<int:producto_id>', methods=['POST'])
@login_required
@roles_required('revisor', 'supervisor', 'admin')
def asignar_proveedor_modal(solicitud_id, producto_id):
    solicitud = Solicitud.query.get_or_404(solicitud_id)
    
    # Verificar si la solicitud ya está aprobada
    if solicitud.estado == 'Aprobada':
        flash('No se puede asignar un proveedor a una solicitud aprobada.', 'danger')
        return redirect(url_for('main.ver_detalle_solicitud', solicitud_id=solicitud_id))
    
    form = AsignarProveedoresForm()
    form.proveedor_id.choices = [(p.id, p.nombre) for p in Proveedor.query.all()]

    if form.validate_on_submit():
        proveedor_id = form.proveedor_id.data
        cantidad = form.cantidad.data

        # Verificar si ya existe la asociación
        existente = ProductoProveedor.query.filter_by(
            producto_id=producto_id,
            proveedor_id=proveedor_id,
            solicitud_id=solicitud_id
        ).first()
        if not existente:
            nueva_asociacion = ProductoProveedor(
                producto_id=producto_id,
                proveedor_id=proveedor_id,
                cantidad=cantidad,
                solicitud_id=solicitud_id
            )
            db.session.add(nueva_asociacion)
            db.session.commit()
            flash('Proveedor asignado exitosamente.', 'success')
        else:
            flash(f'El proveedor {existente.proveedor.nombre} ya está asignado a este producto en esta solicitud.', 'warning')
    else:
        flash('Error al asignar proveedor. Por favor, verifica los datos ingresados.', 'danger')
        print("Errores de validación del formulario:")
        print(form.errors)

    return redirect(url_for('main.ver_detalle_solicitud', solicitud_id=solicitud_id))




@main.route('/revisar_solicitudes')
@login_required
def revisar_solicitudes():
    # Obtener parámetros de filtros desde la URL
    solicitante_id = request.args.get('solicitante_id', type=int)
    proveedor_id = request.args.get('proveedor_id', type=int)
    fecha_inicio = request.args.get('fecha_inicio')
    fecha_fin = request.args.get('fecha_fin')
    
    # Obtener el número de página
    page = request.args.get('page', 1, type=int)
    per_page = 10  # Número de solicitudes por página

    # Base query para aplicar filtros comunes
    base_query = Solicitud.query.options(
        joinedload(Solicitud.solicitante),
        joinedload(Solicitud.centro_costo),
        joinedload(Solicitud.proveedor_seleccionado)
    )

    # Aplicar filtros si existen
    if solicitante_id:
        base_query = base_query.filter(Solicitud.solicitante_id == solicitante_id)
    if proveedor_id:
        base_query = base_query.filter(Solicitud.proveedor_seleccionado_id == proveedor_id)
    if fecha_inicio:
        try:
            fecha_inicio_dt = datetime.strptime(fecha_inicio, '%Y-%m-%d')
            base_query = base_query.filter(Solicitud.fecha_aprobacion >= fecha_inicio_dt)
        except ValueError:
            flash('Formato de fecha de inicio inválido. Utiliza YYYY-MM-DD.', 'danger')
    if fecha_fin:
        try:
            fecha_fin_dt = datetime.strptime(fecha_fin, '%Y-%m-%d')
            base_query = base_query.filter(Solicitud.fecha_aprobacion <= fecha_fin_dt)
        except ValueError:
            flash('Formato de fecha fin inválido. Utiliza YYYY-MM-DD.', 'danger')

    # Obtener solicitudes pendientes
    solicitudes_pendientes = base_query.filter(Solicitud.estado == 'Pendiente').order_by(Solicitud.fecha.desc()).all()

    # Construir la consulta para solicitudes aprobadas
    if current_user.rol in ['admin', 'revisor']:
        query_aprobadas = base_query.filter(Solicitud.estado == 'Aprobada')
    else:
        # Supervisores ven solo las solicitudes aprobadas por ellos mismos
        query_aprobadas = base_query.join(
            Aprobacion, Solicitud.id == Aprobacion.solicitud_id
        ).filter(
            Solicitud.estado == 'Aprobada',
            Aprobacion.revisador_id == current_user.id,
            Aprobacion.estado == 'Aprobada'
        )

    # Paginación para solicitudes aprobadas
    solicitudes_aprobadas_pagination = query_aprobadas.order_by(Solicitud.fecha_aprobacion.desc()) \
                                                   .paginate(page=page, per_page=per_page, error_out=False)
    solicitudes_aprobadas = solicitudes_aprobadas_pagination.items

    # Construir la consulta para solicitudes en proceso
    query_en_proceso = base_query.filter(Solicitud.estado == 'En proceso')

    # Paginación para solicitudes en proceso
    solicitudes_en_proceso_pagination = query_en_proceso.order_by(Solicitud.fecha.desc()) \
                                                     .paginate(page=page, per_page=per_page, error_out=False)
    solicitudes_en_proceso = solicitudes_en_proceso_pagination.items

    # Obtener listas para los filtros
    solicitantes = Usuario.query.filter_by(rol='solicitante').all()
    proveedores = Proveedor.query.all()

    return render_template(
        'revisar_solicitudes.html',
        solicitudes_pendientes=solicitudes_pendientes,
        solicitudes_en_proceso=solicitudes_en_proceso,
        solicitudes_aprobadas=solicitudes_aprobadas,
        solicitantes=solicitantes,
        proveedores=proveedores,
        pagination_aprobadas=solicitudes_aprobadas_pagination,
        pagination_en_proceso=solicitudes_en_proceso_pagination
    )
import logging

@main.route('/generar_oc/<int:solicitud_id>', methods=['POST'])
@login_required
@roles_required('revisor', 'supervisor', 'admin')
def generar_orden_compra(solicitud_id):
    solicitud = Solicitud.query.get_or_404(solicitud_id)
    
    if solicitud.estado != 'Aprobada':
        flash('La solicitud debe estar aprobada antes de generar una orden de compra.', 'danger')
        return redirect(url_for('main.ver_detalle_solicitud', solicitud_id=solicitud_id))
    
    # Obtener todos los proveedores asignados a esta solicitud a través de ProductoProveedor
    proveedores_asignados = Proveedor.query.join(ProductoProveedor).filter(
        ProductoProveedor.solicitud_id == solicitud.id
    ).distinct().all()
    
    if not proveedores_asignados:
        flash('No hay proveedores asignados a esta solicitud.', 'warning')
        return redirect(url_for('main.ver_detalle_solicitud', solicitud_id=solicitud_id))
    
    try:
        for proveedor in proveedores_asignados:
            # Crear una nueva Orden de Compra para cada proveedor
            oc = OrdenCompra(
                solicitud_id=solicitud.id,
                proveedor_id=proveedor.id,
                estado='Generada',
                fecha_creacion=datetime.utcnow()
            )
            db.session.add(oc)
            db.session.flush()  # Obtener el ID de la orden de compra antes de agregar productos
            
            # Obtener los productos asignados a este proveedor en la solicitud
            productos_asignados = ProductoProveedor.query.filter_by(
                solicitud_id=solicitud.id,
                proveedor_id=proveedor.id
            ).all()
            
            # Loguear los productos asignados
            logging.info(f"Generando Orden de Compra {oc.id} para Proveedor {proveedor.nombre} con productos:")
            for pp in productos_asignados:
                logging.info(f"- Producto ID: {pp.producto_id}, Cantidad: {pp.cantidad}, Precio Ofrecido: {pp.precio_ofrecido}")
                
                # Crear una entrada en ProductoOrdenCompra para cada producto asignado
                producto_orden = ProductoOrdenCompra(
                    orden_compra_id=oc.id,
                    producto_id=pp.producto_id,
                    cantidad=pp.cantidad,
                    precio=pp.precio_ofrecido if pp.precio_ofrecido else 0.0  # Manejar precios nulos
                )
                db.session.add(producto_orden)
        
        # Actualizar el estado de la solicitud
        solicitud.estado = 'Ordenes de Compra Generadas'
        
        db.session.commit()
        flash('Órdenes de compra generadas exitosamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error al generar las órdenes de compra.', 'danger')
        current_app.logger.error(f"Error al generar OC para Solicitud {solicitud_id}: {e}")
    
    return redirect(url_for('main.ver_detalle_solicitud', solicitud_id=solicitud_id))




@main.route('/eliminar_producto/<int:producto_id>', methods=['POST'])
@login_required
def eliminar_producto(producto_id):
    if current_user.rol not in ['admin', 'supervisor', 'revisor']:
        flash('No tienes permisos para eliminar este producto.', 'danger')
        return redirect(url_for('main.crear_producto'))
    
    producto = Producto.query.get_or_404(producto_id)
    db.session.delete(producto)
    db.session.commit()
    flash('Producto eliminado exitosamente.', 'success')
    return redirect(url_for('main.crear_producto'))



@main.route('/crear_centro_costo', methods=['GET', 'POST'])
@login_required
def crear_centro_costo():
    if current_user.rol not in ['revisor', 'supervisor']:
        flash('Acceso denegado.', 'danger')
        return redirect(url_for('main.index'))
    
    form = CentroCostoForm()
    if form.validate_on_submit():
        nuevo_centro_costo = CentroCosto(
            nombre=form.nombre.data,
            descripcion=form.descripcion.data
        )
        try:
            db.session.add(nuevo_centro_costo)
            db.session.commit()
            flash('Centro de Costo creado exitosamente.', 'success')
            return redirect(url_for('main.lista_centros_costo'))  # Redirige a la lista de centros de costo
        except Exception as e:
            db.session.rollback()
            flash('Error al crear el Centro de Costo. Por favor, inténtalo de nuevo.', 'danger')
            print(f"Error al crear Centro de Costo: {e}")  # Mensaje de depuración
    
    # Obtener la lista de Centros de Costo para mostrarla en la plantilla
    centros_costo = CentroCosto.query.order_by(CentroCosto.nombre.asc()).all()
    print(f"Centros de Costo recuperados en /crear_centro_costo: {centros_costo}")  # Mensaje de depuración
    
    return render_template('crear_centro_costo.html', centros_costo=centros_costo, form=form)

@main.route('/centros_costo', methods=['GET', 'POST'])
@login_required
@roles_required('admin', 'revisor', 'supervisor')
def lista_centros_costo():
    form = CentroCostoForm()

    # Si se recibe un POST y el usuario tiene permiso para crear, intentamos crear un nuevo centro de costo
    if request.method == 'POST' and form.validate_on_submit():
        nuevo_centro_costo = CentroCosto(
            nombre=form.nombre.data,
            descripcion=form.descripcion.data
        )
        try:
            db.session.add(nuevo_centro_costo)
            db.session.commit()
            flash('Centro de Costo creado exitosamente.', 'success')
            return redirect(url_for('main.lista_centros_costo'))  # Redirige a la lista de centros de costo
        except Exception as e:
            db.session.rollback()
            flash('Error al crear el Centro de Costo. Por favor, inténtalo de nuevo.', 'danger')
            print(f"Error al crear Centro de Costo en /centros_costo: {e}")  # Mensaje de depuración

    # Si es una solicitud GET o después del POST, obtener la lista de centros de costo
    centros_costo = CentroCosto.query.order_by(CentroCosto.nombre.asc()).all()
    print(f"Centros de Costo recuperados en /centros_costo: {centros_costo}")  # Mensaje de depuración

    # Renderiza la plantilla pasando los centros de costo y el formulario
    return render_template('crear_centro_costo.html', centros_costo=centros_costo, form=form)

@main.route('/editar_centro_costo/<int:centro_id>', methods=['POST'])
@login_required
@roles_required('admin', 'revisor', 'supervisor')
def editar_centro_costo(centro_id):
    centro = CentroCosto.query.get_or_404(centro_id)
    form = CentroCostoForm(obj=centro)
    if form.validate_on_submit():
        form.populate_obj(centro)
        try:
            db.session.commit()
            flash('Centro de Costo actualizado exitosamente.', 'success')
            print(f"Centro de Costo actualizado: {centro}")  # Mensaje de depuración
        except Exception as e:
            db.session.rollback()
            flash('Error al actualizar el Centro de Costo. Por favor, inténtalo de nuevo.', 'danger')
            print(f"Error al actualizar Centro de Costo: {e}")  # Mensaje de depuración
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'Error en el campo {getattr(form, field).label.text}: {error}', 'danger')
                print(f"Error en el campo {field}: {error}")  # Mensaje de depuración
    
    return redirect(url_for('main.lista_centros_costo'))





# Rutas para Proveedores
@main.route('/proveedores', methods=['GET', 'POST'])
@login_required
@roles_required('admin', 'revisor', 'supervisor')  # Ajusta según tus roles
def lista_proveedores():
    form = ProveedorForm()
    if form.validate_on_submit():
        try:
            nuevo_proveedor = Proveedor(
                nombre=form.nombre.data,
                correo=form.correo.data,
                telefono=form.telefono.data,
                direccion=form.direccion.data,
                descripcion=form.descripcion.data if form.descripcion.data else None,
                creado_por=current_user.id  # Asociar el proveedor al usuario actual
            )
            db.session.add(nuevo_proveedor)
            db.session.commit()
            flash('Proveedor creado exitosamente.', 'success')
            return redirect(url_for('main.lista_proveedores'))  # Redirige a la misma página para ver la lista actualizada
        except IntegrityError as e:
            db.session.rollback()
            # Manejar errores específicos, como correo duplicado
            if 'unique constraint' in str(e).lower():
                flash('El correo del proveedor ya existe. Por favor, usa otro correo.', 'danger')
            else:
                flash('Error al crear el proveedor. Por favor, verifica los datos ingresados.', 'danger')
            print(f"Error al crear Proveedor: {e}")  # Mensaje de depuración
        except Exception as e:
            db.session.rollback()
            flash('Error al crear el proveedor. Por favor, inténtalo de nuevo.', 'danger')
            print(f"Error al crear Proveedor: {e}")  # Mensaje de depuración

    proveedores = Proveedor.query.order_by(Proveedor.nombre.asc()).all()
    print(f"Proveedores recuperados: {proveedores}")  # Mensaje de depuración
    return render_template('crear_proveedor.html', proveedores=proveedores, form=form)

@main.route('/editar_proveedor/<int:proveedor_id>', methods=['GET', 'POST'])
@login_required
@roles_required('admin', 'revisor', 'supervisor')
def editar_proveedor(proveedor_id):
    proveedor = Proveedor.query.get_or_404(proveedor_id)
    form = ProveedorForm(obj=proveedor)
    if form.validate_on_submit():
        proveedor.nombre = form.nombre.data
        proveedor.correo = form.correo.data
        proveedor.telefono = form.telefono.data
        proveedor.direccion = form.direccion.data
        proveedor.descripcion = form.descripcion.data
        try:
            db.session.commit()
            flash('Proveedor actualizado exitosamente.', 'success')
            return redirect(url_for('main.lista_proveedores'))
        except IntegrityError as e:
            db.session.rollback()
            if 'unique constraint' in str(e).lower():
                flash('El correo del proveedor ya existe. Por favor, usa otro correo.', 'danger')
            else:
                flash('Error al actualizar el proveedor. Por favor, inténtalo de nuevo.', 'danger')
            print(f"Error al actualizar Proveedor: {e}")  # Mensaje de depuración
        except Exception as e:
            db.session.rollback()
            flash('Error al actualizar el proveedor. Por favor, inténtalo de nuevo.', 'danger')
            print(f"Error al actualizar Proveedor: {e}")  # Mensaje de depuración
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'Error en el campo {getattr(form, field).label.text}: {error}', 'danger')
                print(f"Error en el campo {field}: {error}")  # Mensaje de depuración

    return render_template('editar_proveedor.html', form=form, proveedor=proveedor)

@main.route('/eliminar_proveedor/<int:solicitud_id>/<int:proveedor_id>/<int:producto_id>', methods=['POST'])
@login_required
def eliminar_proveedor(solicitud_id, proveedor_id, producto_id):
    if current_user.rol not in ['revisor', 'supervisor']:
        flash('Acceso denegado.', 'danger')
        return redirect(url_for('main.index'))

    # Buscar la asociación específica
    asociacion = ProductoProveedor.query.filter_by(
        solicitud_id=solicitud_id,
        proveedor_id=proveedor_id,
        producto_id=producto_id
    ).first_or_404()

    db.session.delete(asociacion)
    db.session.commit()
    flash('Proveedor eliminado exitosamente.', 'success')
    return redirect(url_for('main.ver_detalle_solicitud', solicitud_id=solicitud_id))





@main.route('/seleccionar_proveedor/<int:solicitud_id>', methods=['POST'])
@login_required
@roles_required('revisor', 'supervisor', 'admin')  # Ajusta según tus roles
def seleccionar_proveedor(solicitud_id):
    solicitud = Solicitud.query.get_or_404(solicitud_id)

    # Verificar permisos
    if current_user.rol not in ['revisor', 'supervisor', 'admin']:
        flash('No tienes permisos para seleccionar un proveedor.', 'danger')
        return redirect(url_for('main.index'))

    form = SeleccionarProveedorForm()
    form.proveedor_seleccionado.choices = [
        (pp.proveedor.id, pp.proveedor.nombre) for pp in solicitud.productos_proveedores
    ]

    if form.validate_on_submit():
        proveedor_id = form.proveedor_seleccionado.data

        # Actualizar la solicitud con el proveedor seleccionado
        solicitud.proveedor_seleccionado_id = proveedor_id
        solicitud.estado = 'Proveedor Seleccionado'

        # Crear la orden de compra asociada
        orden_compra = OrdenCompra(
            solicitud_id=solicitud.id,
            proveedor_id=proveedor_id,
            estado='Generada'  # Estado inicial de la orden de compra
        )
        db.session.add(orden_compra)

        try:
            db.session.commit()
            flash('Proveedor seleccionado y orden de compra generada.', 'success')
        except Exception as e:
            db.session.rollback()
            flash('Ocurrió un error al seleccionar el proveedor y generar la orden de compra.', 'danger')
            print(f"Error al seleccionar proveedor: {e}")

    else:
        flash('Por favor, selecciona un proveedor.', 'danger')
        print(form.errors)

    return redirect(url_for('main.ver_detalle_solicitud', solicitud_id=solicitud_id))


@main.route('/bodega/orden_compra/<int:oc_id>')
@login_required
@roles_required('bodeguero', 'admin')
def detalle_orden_compra(oc_id):
    oc = OrdenCompra.query.get_or_404(oc_id)
    return render_template('bodega/detalle_orden_compra.html', oc=oc)




@main.route('/bodega/ordenes_pendientes')
@login_required
@roles_required('bodeguero', 'admin')
def ordenes_pendientes():
    ordenes = OrdenCompra.query.filter(OrdenCompra.estado.in_(['Generada', 'Enviada'])).all()
    print(f"Órdenes Pendientes Encontradas: {len(ordenes)}")  # Depuración
    if not ordenes:
        flash('No hay órdenes pendientes para mostrar.', 'info')
    else:
        flash(f'Total de órdenes pendientes: {len(ordenes)}', 'success')
    form = RecepcionarOrdenForm()
    return render_template('bodega/ordenes_pendientes.html', ordenes=ordenes, form=form)






@main.route('/historial_aprobaciones/<int:solicitud_id>', methods=['GET'])
@login_required
def historial_aprobaciones(solicitud_id):
    solicitud = Solicitud.query.get_or_404(solicitud_id)

    # Solo el solicitante, aprobadores y administradores pueden ver el historial
    if current_user.rol not in ['solicitante', 'revisor', 'supervisor']:
        flash('Acceso denegado.', 'danger')
        return redirect(url_for('main.index'))

    historial = Aprobacion.query.filter_by(solicitud_id=solicitud_id).order_by(Aprobacion.fecha.desc()).all()
    return render_template('historial_aprobaciones.html', solicitud=solicitud, historial=historial)


@main.route('/enviar_orden_compra/<int:oc_id>', methods=['POST'])
@login_required
@roles_required('revisor', 'supervisor', 'admin')
def enviar_orden_compra(oc_id):
    oc = OrdenCompra.query.get_or_404(oc_id)
    if oc.estado != 'Generada':
        flash('La orden de compra ya ha sido enviada.', 'warning')
        return redirect(url_for('main.detalle_orden_compra', oc_id=oc_id))

    oc.estado = 'Enviada'
    try:
        db.session.commit()
        flash('Orden de compra enviada exitosamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error al enviar la orden de compra.', 'danger')
        print(f"Error: {e}")

    return redirect(url_for('main.detalle_orden_compra', oc_id=oc_id))



@main.route('/generar_pdf/<int:solicitud_id>/<int:proveedor_id>')
@login_required
def generar_pdf_con_reportlab(solicitud_id, proveedor_id):
    solicitud = Solicitud.query.get_or_404(solicitud_id)
    proveedor = Proveedor.query.get_or_404(proveedor_id)
    productos_proveedor = ProductoProveedor.query.filter_by(
        solicitud_id=solicitud_id,
        proveedor_id=proveedor_id
    ).all()

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)

    # --- Aquí empezarías a "dibujar" tu PDF ---
    # Por ejemplo, el logo:
    logo_path = os.path.join(current_app.root_path, 'static', 'logo.png')
    if os.path.exists(logo_path):
        p.drawImage(logo_path, inch, 10 * inch, width=2*inch, preserveAspectRatio=True) # Coordenadas y tamaño

    # Título
    p.setFont("Helvetica-Bold", 16)
    p.drawString(inch, 9.5 * inch, f"Solicitud de Cotización #{solicitud.id}")

    # Datos del proveedor
    p.setFont("Helvetica", 10)
    p.drawString(inch, 9 * inch, f"Proveedor: {proveedor.nombre}")
    # ... más datos del proveedor ...

    # Tabla de productos (esto es más complejo con ReportLab, usualmente se usa Platypus)
    y_position = 8 * inch
    for prod_prov in productos_proveedor:
        p.drawString(inch, y_position, f"Producto: {prod_prov.producto.nombre}, Cantidad: {prod_prov.cantidad}, Precio: {prod_prov.precio_ofrecido}")
        y_position -= 0.25 * inch # Mover hacia abajo para el siguiente ítem

    # ... más elementos del PDF ...

    p.showPage()
    p.save()

    buffer.seek(0)
    
    response = make_response(buffer.getvalue())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=solicitud_{solicitud.id}_proveedor_{proveedor.nombre}_reportlab.pdf'
    return response


@main.route('/enviar_correo_proveedor/<int:solicitud_id>/<int:proveedor_id>', methods=['POST'])
@login_required
@roles_required('revisor', 'supervisor')
def enviar_correo_proveedor(solicitud_id, proveedor_id):
    if current_user.rol not in ['revisor', 'supervisor']:
        flash('Acceso denegado.', 'danger')
        return redirect(url_for('main.index'))

    try:
        solicitud = Solicitud.query.get_or_404(solicitud_id)
        proveedor = Proveedor.query.get_or_404(proveedor_id)

        producto_proveedor = ProductoProveedor.query.filter_by(
            solicitud_id=solicitud_id,
            proveedor_id=proveedor_id
        ).first()

        if not producto_proveedor:
            flash('Este proveedor no está asignado a la solicitud.', 'danger')
            return redirect(url_for('main.ver_detalle_solicitud', solicitud_id=solicitud_id))

        if producto_proveedor.correo_enviado:
            flash(f'El correo ya fue enviado a {proveedor.nombre}.', 'warning')
            return redirect(url_for('main.ver_detalle_solicitud', solicitud_id=solicitud_id))

        # Generar el PDF con ReportLab
        # Deberías llamar a una función similar a generar_pdf_con_reportlab
        # o adaptar/crear una nueva que tome los datos necesarios y devuelva los bytes del PDF.
        # Ejemplo conceptual (necesitarás implementar la lógica real de ReportLab aquí o en una función helper):
        pdf_buffer = generar_pdf_con_reportlab(solicitud_id, proveedor_id) # Reutilizando o adaptando
        if not isinstance(pdf_buffer, BytesIO): # Si la función devuelve una Response
            pdf_bytes = pdf_buffer.get_data()
        else: # Si devuelve directamente BytesIO
            pdf_bytes = pdf_buffer.getvalue()

        # Crear el mensaje
        subject = f'Cotización para Solicitud #{solicitud.id}'
        body = f"""
        Estimado/a {proveedor.nombre},

        Adjunto encontrará la cotización para la solicitud #{solicitud.id}.

        Saludos cordiales.
        """

        msg = Message(
            subject=subject,
            recipients=[proveedor.correo],
            body=body
        )

        # Adjuntar el PDF
        msg.attach(
            filename=f'solicitud_{solicitud.id}_proveedor_{proveedor.nombre}.pdf',
            content_type='application/pdf',
            data=pdf_bytes
        )

        # Enviar el correo
        mail.send(msg)
        
        # Marcar como enviado
        producto_proveedor.correo_enviado = True
        solicitud.estado = 'En proceso'  # Comentada para mantener el estado 'Pendiente'
        db.session.commit()

        flash(f'Correo enviado exitosamente a {proveedor.nombre}.', 'success')

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        current_app.logger.error(f'Error al enviar el correo: {str(e)}\n{error_details}')
        flash('Error al enviar el correo electrónico. Por favor, inténtelo de nuevo más tarde.', 'danger')

    return redirect(url_for('main.ver_detalle_solicitud', solicitud_id=solicitud_id))







from utils import enviar_correo





# routes.py

@main.route('/historial_recepciones')
@login_required
@roles_required('bodeguero', 'admin')
def historial_recepciones():
    recepciones = Recepcion.query.options(
        joinedload(Recepcion.solicitud)
        .joinedload(Solicitud.productos_solicitudes)
        .joinedload(ProductoSolicitud.producto),
        joinedload(Recepcion.solicitud)
        .joinedload(Solicitud.aprobaciones)
        .joinedload(Aprobacion.revisador),
        joinedload(Recepcion.solicitud)
        .joinedload(Solicitud.proveedor_seleccionado),
        joinedload(Recepcion.usuario)
    ).order_by(Recepcion.fecha_recepcion.desc()).all()
    return render_template('bodega/historial_recepciones.html', recepciones=recepciones)



@main.route('/generar_pdf_recepcion/<int:recepcion_id>', methods=['GET'])
@login_required
@roles_required('bodeguero', 'admin')  # Ajusta según tus roles
def generar_pdf_recepcion(recepcion_id):
    recepcion = Recepcion.query.options(
        db.joinedload(Recepcion.solicitud)
        .joinedload(Solicitud.productos_solicitudes)
        .joinedload(ProductoSolicitud.producto),
        db.joinedload(Recepcion.solicitud)
        .joinedload(Solicitud.aprobaciones)
        .joinedload(Aprobacion.revisador),
        db.joinedload(Recepcion.solicitud)
        .joinedload(Solicitud.proveedor_seleccionado),
        db.joinedload(Recepcion.usuario)
    ).get_or_404(recepcion_id)

    # Obtener la ruta absoluta del logo
    logo_path = os.path.join(current_app.root_path, 'static', 'logo.png')
    if not os.path.exists(logo_path):
        flash('Logo no encontrado.', 'danger')
        return redirect(url_for('main.historial_recepciones'))
    
    # Leer y codificar la imagen en Base64
    with open(logo_path, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode('utf-8')

    # Renderizar la plantilla con la imagen en Base64
    html = render_template(
        'pdf_recepcion.html',
        recepcion=recepcion,
        logo_base64=encoded_string
    )

    # Generar el PDF con ReportLab
    # Necesitarás una función que tome 'recepcion' y 'logo_base64' (o la ruta del logo)
    # y genere el PDF usando ReportLab.
    # Ejemplo conceptual:
    # pdf_bytes = generar_pdf_recepcion_reportlab(recepcion, logo_path) # Necesitarías crear esta función
    pdf_bytes = b"PDF content from ReportLab here" # Placeholder - Reemplazar con la llamada real

    response = make_response(pdf_bytes)
    response.headers['Content-Type'] = 'application/pdf'
    filename = f'recepcion_{recepcion.id}.pdf'
    response.headers['Content-Disposition'] = f'attachment; filename={filename}'

    return response


def notificar_solicitante_recepcion(solicitud):
    solicitante = solicitud.solicitante
    msg = Message(
        subject=f'Recepción de Orden # {solicitud.id}',
        sender='tu_email@example.com',  # Reemplaza con tu email real
        recipients=[solicitante.correo]
    )
    if solicitud.estado == 'Recepcionada':  # Cambiado de 'Recepcionado' a 'Recepcionada'
        cuerpo = f"""
        Hola {solicitante.nombre_usuario},

        La orden # {solicitud.id} ha sido recepcionada completamente por bodega.

        Saludos,
        Equipo de Bodega
        """
    elif solicitud.estado == 'Recepción Parcial':
        cuerpo = f"""
        Hola {solicitante.nombre_usuario},

        La orden # {solicitud.id} ha sido recepcionada parcialmente. Algunos productos faltan o tienen comentarios específicos.

        Por favor, revisa los detalles en el sistema para más información.

        Saludos,
        Equipo de Bodega
        """
    else:
        cuerpo = f"""
        Hola {solicitante.nombre_usuario},

        Ha ocurrido un error al recepcionar la orden # {solicitud.id}.

        Saludos,
        Equipo de Bodega
        """

    msg.body = cuerpo

    try:
        mail.send(msg)
        current_app.logger.info(f'Correo de recepción enviado a {solicitante.correo}')
    except Exception as e:
        current_app.logger.error(f'Error al enviar correo de recepción: {e}')
# routes.py

@main.route('/recepcionar_orden/<int:oc_id>', methods=['GET', 'POST'])
@login_required
@roles_required('bodeguero', 'admin')
def recepcionar_orden(oc_id):
    orden_compra = OrdenCompra.query.get_or_404(oc_id)
    solicitud = orden_compra.solicitud  # Asumiendo que tienes una relación 'solicitud' en OrdenCompra

    form = RecepcionarOrdenForm()

    if request.method == 'GET':
        for producto_orden in orden_compra.productos_orden:
            producto_form = ProductoRecepcionForm()
            producto_form.producto_id.data = producto_orden.producto.id
            producto_form.recibido.data = False  # Por defecto, no recibido
            form.productos.append_entry(producto_form)

    if form.validate_on_submit():
        recepciones_correctas = True

        for idx, producto_form in enumerate(form.productos):
            producto_id = producto_form.producto_id.data
            recibido = producto_form.recibido.data

            producto_orden = ProductoOrdenCompra.query.filter_by(
                orden_compra_id=oc_id,
                producto_id=producto_id
            ).first()

            if producto_orden:
                if recibido:
                    producto_orden.cantidad_recibida = producto_orden.cantidad

                    # Actualizar Inventario
                    inventario = Inventario.query.filter_by(producto_id=producto_id).first()
                    if inventario:
                        inventario.cantidad += producto_orden.cantidad_recibida
                        inventario.fecha_actualizacion = datetime.utcnow()
                    else:
                        inventario = Inventario(
                            producto_id=producto_id,
                            cantidad=producto_orden.cantidad_recibida,
                            fecha_actualizacion=datetime.utcnow()
                        )
                        db.session.add(inventario)

                    # Registrar Movimiento de Inventario
                    movimiento = MovimientoInventario(
                        inventario=inventario,
                        tipo='entrada',
                        cantidad=producto_orden.cantidad_recibida,
                        descripcion=f'Recepción de Orden de Compra #{oc_id}'
                    )
                    db.session.add(movimiento)
                else:
                    recepciones_correctas = False

        if recepciones_correctas:
            solicitud.estado = 'Recepcionada'
            orden_compra.estado = 'Recepcionada'
        else:
            solicitud.estado = 'Recepción Parcial'
            orden_compra.estado = 'Recepción Parcial'

        recepcion = Recepcion(
            solicitud_id=solicitud.id,
            orden_compra_id=orden_compra.id,  # Asignación correcta
            comentario_general=form.comentario_general.data,
            usuario_id=current_user.id
        )
        db.session.add(recepcion)

        try:
            db.session.commit()
            flash('Recepción de orden actualizada correctamente.', 'success')
            notificar_solicitante_recepcion(solicitud)
            return redirect(url_for('main.ordenes_pendientes'))
        except Exception as e:
            db.session.rollback()
            flash('Error al actualizar la recepción de la orden.', 'danger')
            current_app.logger.error(f'Error en recepcionar_orden: {e}')

    if request.method == 'POST' and not form.validate_on_submit():
        flash('Por favor, revisa los errores en el formulario.', 'danger')

    return render_template('bodega/recepcionar_orden.html', solicitud=solicitud, orden_compra=orden_compra, form=form)


@main.route('/editar_producto_proveedor/<int:pp_id>', methods=['POST'])
@roles_required('admin', 'revisor', 'supervisor')  # Ajusta según tus roles
def editar_producto_proveedor(pp_id):
    pp = ProductoProveedor.query.get_or_404(pp_id)
    form = EditarProductoProveedorForm()

    if form.validate_on_submit():
        pp.precio_ofrecido = form.precio_ofrecido.data
        pp.tiempo_estimado_envio = form.tiempo_estimado_envio.data
        try:
            db.session.commit()
            flash('Precio y tiempo de envío actualizados correctamente.', 'success')
        except Exception as e:
            db.session.rollback()
            flash('Ocurrió un error al actualizar los datos.', 'danger')
            print(f"Error al actualizar ProductoProveedor {pp_id}: {e}")
    else:
        flash('Por favor, corrige los errores en el formulario.', 'danger')
        print(form.errors)

    return redirect(url_for('main.ver_detalle_solicitud', solicitud_id=pp.solicitud_id))





def enviar_notificacion_aprobacion(solicitud):
    solicitante = solicitud.solicitante
    proveedor = Proveedor.query.get(solicitud.proveedor_seleccionado_id)
    msg = Message(
        subject=f'Su solicitud #{solicitud.id} ha sido aprobada',
        sender='tu_email@example.com',
        recipients = [solicitante.correo]
    )
    msg.body = f"""
    Hola {solicitante.nombre_usuario},

    Su solicitud #{solicitud.id} ha sido aprobada.
    Proveedor seleccionado: {proveedor.nombre}
    Tiempo estimado de envío: {solicitud.tiempo_estimado} días

    Puede ver los detalles en su panel de usuario.

    Saludos,
    El equipo de compras
    """
    try:
        mail.send(msg)
        print(f"Correo de notificación enviado a {solicitante.email}")
    except Exception as e:
        print(f"Error al enviar correo de notificación: {e}")
# routes.py

@main.route('/aprobar_solicitud/<int:solicitud_id>', methods=['POST'])
@login_required
@roles_required('supervisor', 'admin')
def aprobar_solicitud(solicitud_id):
    solicitud = Solicitud.query.get_or_404(solicitud_id)

    if solicitud.estado not in ['Pendiente', 'En proceso']:
        flash('La solicitud ya ha sido procesada.', 'warning')
        return redirect(url_for('main.ver_detalle_solicitud', solicitud_id=solicitud_id))

    aprobar_form = AprobacionForm()
    proveedores_asignados = list({pp.proveedor for pp in solicitud.productos_proveedores if pp.proveedor})

    # Configurar los choices para ambos campos de proveedores en el formulario de aprobación
    aprobar_form.proveedor_seleccionado_1.choices = [(p.id, p.nombre) for p in proveedores_asignados]
    aprobar_form.proveedor_seleccionado_2.choices += [(p.id, p.nombre) for p in proveedores_asignados if p.id != 0]

    if aprobar_form.validate_on_submit():
        proveedor_id_1 = aprobar_form.proveedor_seleccionado_1.data
        proveedor_id_2 = aprobar_form.proveedor_seleccionado_2.data
        comentario = aprobar_form.comentario.data

        # Actualizar el estado de la solicitud
        solicitud.estado = 'Aprobada'
        solicitud.fecha_aprobacion = datetime.utcnow()

        proveedores_ids = [proveedor_id_1]
        if proveedor_id_2 and proveedor_id_2 != 0:
            proveedores_ids.append(proveedor_id_2)

        try:
            for proveedor_id in proveedores_ids:
                # Crear un registro en la tabla Aprobacion
                aprobacion = Aprobacion(
                    solicitud_id=solicitud.id,
                    revisador_id=current_user.id,
                    estado='Aprobada',
                    comentario=comentario,
                    fecha_aprobacion=datetime.utcnow()
                )
                db.session.add(aprobacion)

                # Crear la Orden de Compra asociada
                orden_compra = OrdenCompra(
                    solicitud_id=solicitud.id,
                    proveedor_id=proveedor_id,
                    estado='Generada',
                    fecha_creacion=datetime.utcnow()
                )
                db.session.add(orden_compra)
                db.session.flush()  # Obtener el ID de la orden de compra antes de agregar productos

                # Obtener los productos asignados a este proveedor en la solicitud
                productos_asignados = ProductoProveedor.query.filter_by(
                    solicitud_id=solicitud.id,
                    proveedor_id=proveedor_id
                ).all()

                for pp in productos_asignados:
                    # Crear una entrada en ProductoOrdenCompra para cada producto asignado
                    producto_orden = ProductoOrdenCompra(
                        orden_compra_id=orden_compra.id,
                        producto_id=pp.producto_id,
                        cantidad=pp.cantidad,
                        precio=pp.precio_ofrecido if pp.precio_ofrecido else 0.0  # Asegúrate de manejar precios nulos
                    )
                    db.session.add(producto_orden)

            db.session.commit()
            flash('Solicitud aprobada exitosamente y órdenes de compra generadas.', 'success')
        except SQLAlchemyError as e:
            db.session.rollback()
            flash('Ocurrió un error al aprobar la solicitud. Por favor, inténtalo de nuevo.', 'danger')
            current_app.logger.error(f'Error al aprobar solicitud {solicitud_id}: {e}')
            return redirect(url_for('main.ver_detalle_solicitud', solicitud_id=solicitud_id))

        return redirect(url_for('main.ver_detalle_solicitud', solicitud_id=solicitud_id))
    else:
        # Mostrar errores de validación específicos si es necesario
        for field, errors in aprobar_form.errors.items():
            for error in errors:
                flash(f'Error en {getattr(aprobar_form, field).label.text}: {error}', 'danger')
        return redirect(url_for('main.ver_detalle_solicitud', solicitud_id=solicitud_id))



@main.route('/rechazar_solicitud/<int:solicitud_id>', methods=['POST'])
@login_required
@roles_required('supervisor', 'admin')
def rechazar_solicitud(solicitud_id):
    solicitud = Solicitud.query.get_or_404(solicitud_id)
    
    if solicitud.estado not in ['Pendiente', 'En proceso']:
        flash('La solicitud ya ha sido procesada.', 'warning')
        return redirect(url_for('main.revisar_solicitudes'))
    
    rechazar_form = RechazarForm()
    
    if rechazar_form.validate_on_submit():
        comentario = rechazar_form.comentario.data
        
        # Actualizar el estado de la solicitud
        solicitud.estado = 'Rechazada'
        solicitud.fecha_aprobacion = datetime.utcnow()
        
        # Crear un registro en la tabla Aprobacion
        aprobacion = Aprobacion(
            solicitud_id=solicitud.id,
            revisador_id=current_user.id,
            estado='Rechazada',
            comentario=comentario,
            fecha_aprobacion=datetime.utcnow()
        )
        db.session.add(aprobacion)
        
        try:
            db.session.commit()
            flash('Solicitud rechazada exitosamente.', 'success')
        except SQLAlchemyError as e:
            db.session.rollback()
            flash('Ocurrió un error al rechazar la solicitud. Por favor, inténtalo de nuevo.', 'danger')
            current_app.logger.error(f'Error al rechazar solicitud {solicitud_id}: {e}')
            return redirect(url_for('main.ver_detalle_solicitud', solicitud_id=solicitud_id))
        
        return redirect(url_for('main.ver_detalle_solicitud', solicitud_id=solicitud_id))
    else:
        # Mostrar errores de validación específicos si es necesario
        for field, errors in rechazar_form.errors.items():
            for error in errors:
                flash(f'Error en {getattr(rechazar_form, field).label.text}: {error}', 'danger')
        return redirect(url_for('main.ver_detalle_solicitud', solicitud_id=solicitud_id))

@main.route('/mis_solicitudes')
@login_required
@roles_required('solicitante', 'admin', 'revisor', 'supervisor', 'bodeguero')  # Ajusta según tus roles
def mis_solicitudes():
    # Obtener todas las solicitudes creadas por el usuario actual con sus relaciones
    solicitudes = Solicitud.query.options(
        joinedload(Solicitud.centro_costo),
        joinedload(Solicitud.proveedor_seleccionado),
        joinedload(Solicitud.productos_solicitudes).joinedload(ProductoSolicitud.producto),
        joinedload(Solicitud.productos_proveedores).joinedload(ProductoProveedor.proveedor),
        joinedload(Solicitud.aprobaciones).joinedload(Aprobacion.revisador),
        joinedload(Solicitud.recepciones).joinedload(Recepcion.usuario)
    ).filter_by(solicitante_id=current_user.id).order_by(Solicitud.fecha.desc()).all()

    # Crear formularios de edición para cada ProductoProveedor
    editar_forms = {
        pp.id: EditarProductoProveedorForm(obj=pp)
        for solicitud in solicitudes
        for pp in solicitud.productos_proveedores
    }

    # Crear una lista de eventos por solicitud
    solicitudes_eventos = {}
    for solicitud in solicitudes:
        eventos = []
        # Aprobaciones
        for aprobacion in solicitud.aprobaciones:
            eventos.append({
                'tipo': 'aprobacion',
                'fecha': aprobacion.fecha_aprobacion,
                'estado': aprobacion.estado,
                'usuario': aprobacion.revisador.nombre_usuario,
                'comentario': aprobacion.comentario
            })
        # Recepciones
        for recepcion in solicitud.recepciones:
            eventos.append({
                'tipo': 'recepcion',
                'fecha': recepcion.fecha_recepcion,
                'estado': solicitud.estado,  # Estado actual de la solicitud
                'usuario': recepcion.usuario.nombre_usuario,
                'comentario': recepcion.comentario_general
            })
        # Ordenar los eventos por fecha descendente
        eventos_sorted = sorted(
            eventos,
            key=lambda x: x['fecha'],
            reverse=True
        )
        solicitudes_eventos[solicitud.id] = eventos_sorted

    return render_template(
        'mis_solicitudes.html',
        solicitudes=solicitudes,
        editar_forms=editar_forms,
        solicitudes_eventos=solicitudes_eventos  # Pasar los eventos organizados por solicitud
    )
# routes.py

# routes.py


@main.route('/categorias', methods=['GET', 'POST'])
@login_required
@roles_required('revisor', 'admin')  # Restringir a 'revisor' y 'admin'
def categorias():
    form = CategoriaForm()
    delete_form = DeleteCategoriaForm()
    
    # Manejo de creación de categoría
    if form.validate_on_submit() and 'guardar_categoria' in request.form:
        try:
            nueva_categoria = Categoria(
                nombre=form.nombre.data.strip(),
                descripcion=form.descripcion.data.strip() if form.descripcion.data else None
            )
            db.session.add(nueva_categoria)
            db.session.commit()
            flash('Categoría creada exitosamente.', 'success')
            return redirect(url_for('main.categorias'))
        except IntegrityError:
            db.session.rollback()
            flash('El nombre de la categoría ya existe. Por favor, elige otro nombre.', 'danger')
        except Exception as e:
            db.session.rollback()
            flash('Ocurrió un error al crear la categoría. Por favor, inténtalo de nuevo.', 'danger')
            print(f"Error al crear categoría: {e}")
    
    # Manejo de edición de categoría
    if form.validate_on_submit() and 'editar_categoria' in request.form:
        categoria_id = form.id.data
        categoria = Categoria.query.get_or_404(categoria_id)
        try:
            categoria.nombre = form.nombre.data.strip()
            categoria.descripcion = form.descripcion.data.strip() if form.descripcion.data else None
            db.session.commit()
            flash('Categoría actualizada exitosamente.', 'success')
            return redirect(url_for('main.categorias'))
        except IntegrityError:
            db.session.rollback()
            flash('El nombre de la categoría ya existe. Por favor, elige otro nombre.', 'danger')
        except Exception as e:
            db.session.rollback()
            flash('Ocurrió un error al actualizar la categoría. Por favor, inténtalo de nuevo.', 'danger')
            print(f"Error al actualizar categoría: {e}")
    
    # Manejo de eliminación de categoría
    if delete_form.validate_on_submit():
        categoria_id = delete_form.id.data
        categoria = Categoria.query.get_or_404(categoria_id)
        try:
            db.session.delete(categoria)
            db.session.commit()
            flash('Categoría eliminada exitosamente.', 'success')
            return redirect(url_for('main.categorias'))
        except IntegrityError:
            db.session.rollback()
            flash('No se puede eliminar esta categoría porque está asociada a otros productos.', 'danger')
        except Exception as e:
            db.session.rollback()
            flash('Ocurrió un error al eliminar la categoría. Por favor, inténtalo de nuevo.', 'danger')
            print(f"Error al eliminar categoría: {e}")
    
    # Obtener todas las categorías para mostrar
    categorias = Categoria.query.order_by(Categoria.nombre.asc()).all()
    
    return render_template('categorias.html', form=form, delete_form=delete_form, categorias=categorias)


@main.route('/buscar_productos', methods=['GET'])
@login_required
def buscar_productos():
    """
    Ruta para buscar productos por nombre.
    Retorna datos en formato JSON para Select2.
    """
    query = request.args.get('q', '')
    productos = Producto.query.filter(Producto.nombre.ilike(f'%{query}%')).limit(20).all()
    
    resultados = []
    for producto in productos:
        resultados.append({
            'id': producto.id,
            'text': producto.nombre
        })
    
    return jsonify({'results': resultados})


@main.route('/inventario')
@login_required
@roles_required('admin', 'revisor', 'bodeguero')
def inventario():
    # Obtener el parámetro de página de la URL, por defecto 1
    page = request.args.get('page', type=int, default=1)
    per_page = 10  # Número de ítems por página

    # Opcional: Filtrado por búsqueda
    search = request.args.get('search', '', type=str)

    # Construir la consulta base
    query = Inventario.query.join(Producto).add_columns(
        Producto.nombre.label('nombre_producto'),
        Inventario.cantidad,
        Inventario.umbral_minimo,
   
        Inventario.fecha_actualizacion,
        Inventario.id
    )

    # Aplicar filtro de búsqueda si existe
    if search:
        query = query.filter(Producto.nombre.ilike(f'%{search}%'))

    # Aplicar paginación utilizando argumentos de palabra clave
    inventarios_paginated = query.paginate(page=page, per_page=per_page, error_out=False)

    # Crear formularios de eliminación para cada inventario
    eliminar_forms = {inventario.id: EliminarInventarioForm() for inventario in inventarios_paginated.items}

    # Crear formularios de edición para cada inventario
    editar_forms = {inventario.id: EditarInventarioForm(obj=inventario) for inventario in inventarios_paginated.items}

    # Configurar la paginación para la plantilla
    pagination = Pagination(page=page, total=inventarios_paginated.total, per_page=per_page, css_framework='bootstrap4')

    # Obtener todos los productos para posibles usos futuros (si es necesario)
    productos = Producto.query.all()

    return render_template('inventario/inventario.html',
                           inventarios=inventarios_paginated.items,
                           pagination=pagination,
                           search=search,
                           eliminar_forms=eliminar_forms,
                           editar_forms=editar_forms,
                           productos=productos)



@main.route('/inventario/ajustar', methods=['GET', 'POST'])
@login_required
@roles_required('admin', 'revisor', 'bodeguero')  # Ajusta según tus roles
def ajustar_inventario():
    form = AjusteInventarioForm()
    if form.validate_on_submit():
        producto = Producto.query.get(form.producto_id.data)
        if not producto:
            flash('Producto no encontrado.', 'danger')
            return redirect(url_for('main.ajustar_inventario'))
        
        inventario = Inventario.query.filter_by(producto_id=producto.id).first()
        if inventario:
            inventario.cantidad = form.cantidad.data
            inventario.fecha_actualizacion = datetime.utcnow()
        else:
            inventario = Inventario(
                producto_id=producto.id,
                cantidad=form.cantidad.data,
                fecha_actualizacion=datetime.utcnow()
            )
            db.session.add(inventario)
        
        # Registrar Movimiento de Inventario
        movimiento = MovimientoInventario(
            inventario=inventario,
            tipo='entrada' if form.cantidad.data >= 0 else 'salida',
            cantidad=abs(form.cantidad.data),
            descripcion=form.descripcion.data or 'Ajuste manual de inventario'
        )
        db.session.add(movimiento)
        
        try:
            db.session.commit()
            flash('Inventario actualizado correctamente.', 'success')
            return redirect(url_for('main.inventario'))
        except Exception as e:
            db.session.rollback()
            flash('Error al actualizar el inventario.', 'danger')
            current_app.logger.error(f'Error al ajustar inventario: {e}')
    
    return render_template('inventario/ajustar_inventario.html', form=form)


@main.route('/inventario/reportes', methods=['GET', 'POST'])
@login_required
@roles_required('admin', 'revisor', 'bodeguero')
def reportes_inventario():
    form = ReporteInventarioForm()
    report_data = None

    if form.validate_on_submit():
        fecha_inicio = form.fecha_inicio.data
        fecha_fin = form.fecha_fin.data

        report_data = MovimientoInventario.query.join(Inventario).join(Producto).filter(
            MovimientoInventario.fecha >= fecha_inicio,
            MovimientoInventario.fecha <= fecha_fin
        ).add_columns(
            Producto.nombre.label('nombre_producto'),
            MovimientoInventario.tipo,
            MovimientoInventario.cantidad,
            MovimientoInventario.descripcion,
            MovimientoInventario.fecha
        ).all()

        if 'export_pdf' in request.form:
            # Generar PDF con ReportLab
            # Necesitarás una función que tome 'report_data', 'fecha_inicio', 'fecha_fin'
            # y genere el PDF usando ReportLab.
            # Ejemplo conceptual:
            # pdf_bytes = generar_reporte_inventario_pdf_reportlab(report_data, fecha_inicio, fecha_fin)
            pdf_bytes = b"PDF content from ReportLab here" # Placeholder - Reemplazar con la llamada real
            return send_file(BytesIO(pdf_bytes), attachment_filename='reporte_inventario.pdf', as_attachment=True)

        if 'export_excel' in request.form:
            df = pd.DataFrame([(r.nombre_producto, r.tipo, r.cantidad, r.descripcion, r.fecha) for r in report_data], columns=['Producto', 'Tipo', 'Cantidad', 'Descripción', 'Fecha'])
            output = BytesIO()
            writer = pd.ExcelWriter(output, engine='xlsxwriter') # type: ignore
            df.to_excel(writer, index=False, sheet_name='Reporte Inventario')
            writer.close() # Usar close() en lugar de save() para versiones recientes de XlsxWriter con pandas
            output.seek(0)
            return send_file(output, attachment_filename='reporte_inventario.xlsx', as_attachment=True)

    return render_template('inventario/reportes_inventario.html', form=form, report_data=report_data)

@main.route('/editar_inventario/<int:id>', methods=['POST'])
@login_required
@roles_required('admin', 'revisor', 'supervisor')
def editar_inventario(id):
    form = EditarInventarioForm()
    if form.validate_on_submit():
        inventario = Inventario.query.get_or_404(id)
        
        # Actualizar los campos permitidos
        inventario.cantidad = form.cantidad.data
        inventario.umbral_minimo = form.umbral_minimo.data
        inventario.fecha_actualizacion = datetime.utcnow()
        
        db.session.commit()
        flash('Inventario actualizado correctamente.', 'success')
    else:
        flash('Error al actualizar el inventario. Por favor, revisa los campos ingresados.', 'danger')
    
    return redirect(url_for('main.inventario'))
@main.route('/inventario/eliminar/<int:id>', methods=['POST'])
@login_required
def eliminar_inventario(id):
    if current_user.rol != 'bodeguero':
        flash('No tienes permisos para eliminar el inventario.', 'error')
        return redirect(url_for('main.index'))
    
    inventario = Inventario.query.get_or_404(id)
    db.session.delete(inventario)
    db.session.commit()
    flash('Inventario eliminado correctamente.', 'success')
    return redirect(url_for('main.inventario'))

@main.route('/recepcionar_solicitud/<int:solicitud_id>', methods=['GET', 'POST'])
@login_required
@roles_required('bodeguero', 'admin')
def recepcionar_solicitud(solicitud_id):
    solicitud = Solicitud.query.get_or_404(solicitud_id)
    orden_compra = OrdenCompra.query.filter_by(solicitud_id=solicitud_id).first()
    
    if not orden_compra:
        flash('No existe una Orden de Compra asociada a esta Solicitud.', 'warning')
        return redirect(url_for('main.index'))
    
    form = RecepcionarOrdenForm()

    if request.method == 'GET':
        for producto_solicitud in solicitud.productos_solicitudes:
            producto_form = ProductoRecepcionForm()
            producto_form.producto_id.data = producto_solicitud.producto.id
            form.productos.append_entry(producto_form)

    if form.validate_on_submit():
        recepciones_correctas = True

        for idx, producto_form in enumerate(form.productos):
            producto_id = producto_form.producto_id.data
            recibido = producto_form.recibido.data

            producto_solicitud = ProductoSolicitud.query.filter_by(
                solicitud_id=solicitud_id,
                producto_id=producto_id
            ).first()

            if producto_solicitud:
                if recibido:
                    producto_solicitud.cantidad_recibida = producto_solicitud.cantidad

                    # Actualizar Inventario
                    inventario = Inventario.query.filter_by(producto_id=producto_id).first()
                    if inventario:
                        inventario.cantidad += producto_solicitud.cantidad_recibida
                        inventario.fecha_actualizacion = datetime.utcnow()
                    else:
                        inventario = Inventario(
                            producto_id=producto_id,
                            cantidad=producto_solicitud.cantidad_recibida,
                            fecha_actualizacion=datetime.utcnow()
                        )
                        db.session.add(inventario)
                    
                    # Registrar Movimiento de Inventario
                    movimiento = MovimientoInventario(
                        inventario=inventario,
                        tipo='entrada',
                        cantidad=producto_solicitud.cantidad_recibida,
                        descripcion=f'Recepción de solicitud #{solicitud_id}'
                    )
                    db.session.add(movimiento)
                else:
                    recepciones_correctas = False

        if recepciones_correctas:
            solicitud.estado = 'Recepcionada'
            orden_compra.estado = 'Recepcionada'
        else:
            solicitud.estado = 'Recepción Parcial'
            orden_compra.estado = 'Recepción Parcial'

        recepcion = Recepcion(
            solicitud_id=solicitud.id,
            orden_compra_id=orden_compra.id,  # Asegúrate de asignar esto
            comentario_general=form.comentario_general.data,
            usuario_id=current_user.id
        )
        db.session.add(recepcion)

        try:
            db.session.commit()
            flash('Recepción de orden actualizada correctamente.', 'success')
            notificar_solicitante_recepcion(solicitud)
            return redirect(url_for('main.ordenes_pendientes'))
        except Exception as e:
            db.session.rollback()
            flash('Error al actualizar la recepción de la orden.', 'danger')
            current_app.logger.error(f'Error en recepcionar_solicitud: {e}')

    if request.method == 'POST' and not form.validate_on_submit():
        flash('Por favor, revisa los errores en el formulario.', 'danger')

    return render_template('bodega/recepcionar_orden.html', solicitud=solicitud, form=form)
