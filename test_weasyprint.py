from weasyprint import HTML

HTML(string='<h1>Hola Mundo</h1>').write_pdf('test.pdf')
