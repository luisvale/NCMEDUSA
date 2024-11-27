{
    'name': 'NCDEVOLUCION',
    'version': '1.0',
    'category': 'Accounting',
    'summary': 'Relación entre facturas y pedidos de venta',
    'description': """
        Al confirmar la NC, se DEVUELVEN los movimientos de inventario del pedido de venta relacionado.
    """,
    'author': 'MEDUSA',
    'depends': ['account', 'sale', 'stock'],  # Dependencias del módulo
    'data': [
        'views/account_invoice_views.xml',  # Registro de la vista
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}