# seed_db.py

from app import create_app, db
from models import Categoria, Producto

def seed_db():
    app = create_app()
    with app.app_context():
        # Verificar si ya existen categorías para evitar duplicados
        if Categoria.query.first():
            print("La base de datos ya está poblada.")
            return
        
        # Crear categorías
        categorias = [
            Categoria(nombre='Electrónica', descripcion='Dispositivos electrónicos y gadgets.'),
            Categoria(nombre='Muebles', descripcion='Muebles para el hogar y oficina.'),
            Categoria(nombre='Ropa', descripcion='Vestimenta y accesorios.'),
            Categoria(nombre='Alimentos', descripcion='Productos alimenticios y bebidas.')
        ]
        
        db.session.add_all(categorias)
        db.session.commit()
        print("Categorías añadidas.")
        
        # Crear productos
        productos = [
            Producto(nombre='Smartphone XYZ', descripcion='Último modelo de Smartphone XYZ.', especificaciones='128GB, 6GB RAM', precio_unitario=699.99, categoria_id=categorias[0].id),
            Producto(nombre='Laptop ABC', descripcion='Laptop de alto rendimiento ABC.', especificaciones='16GB RAM, 512GB SSD', precio_unitario=1199.99, categoria_id=categorias[0].id),
            Producto(nombre='Sofá Comfort', descripcion='Sofá de 3 plazas Comfort.', especificaciones='Tela resistente, color gris', precio_unitario=499.99, categoria_id=categorias[1].id),
            Producto(nombre='Mesa de Oficina', descripcion='Mesa ergonómica para oficina.', especificaciones='Ajustable en altura, color negro', precio_unitario=299.99, categoria_id=categorias[1].id),
            Producto(nombre='Camisa Casual', descripcion='Camisa de algodón casual.', especificaciones='Color azul, talla M', precio_unitario=29.99, categoria_id=categorias[2].id),
            Producto(nombre='Chocolate Premium', descripcion='Chocolate negro con alto porcentaje de cacao.', especificaciones='100g, sin azúcar añadida', precio_unitario=5.99, categoria_id=categorias[3].id)
        ]
        
        db.session.add_all(productos)
        db.session.commit()
        print("Productos añadidos.")

if __name__ == '__main__':
    seed_db()
