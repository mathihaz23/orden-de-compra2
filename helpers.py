def slugify(value):
    """
    Convierte una cadena en un slug seguro para usar en URLs y nombres de archivo.
    Maneja correctamente caracteres UTF-8.
    """
    import unicodedata
    import re
    
    # Convertir a unicode si es necesario
    if not isinstance(value, str):
        value = str(value)
    
    # Normalizar caracteres unicode
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    
    # Convertir a minúsculas y eliminar caracteres no alfanuméricos
    value = re.sub(r'[^\w\s-]', '', value.lower())
    
    # Reemplazar espacios y guiones repetidos
    value = re.sub(r'[-\s]+', '-', value).strip('-_')
    
    return value