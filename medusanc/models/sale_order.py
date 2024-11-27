from odoo import models, fields, api, _

class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    check_return = fields.Boolean(
        string="Devolución Completada",
        default=False,
        help="Este campo se activa cuando el usuario completa las devoluciones relacionadas con los pickings del pedido."
    )

    def action_open_return_wizard(self):
        """
        Abre el wizard de devolución desde la factura, filtrando los pickings por el origen de la factura.
        """
        self.ensure_one()

        # Verificar si hay un origen relacionado en la factura
        if not self.origin:
            raise ValueError(_("La factura no tiene un origen definido para buscar pickings relacionados."))

        # Buscar pickings relacionados con el origen de la factura
        pickings_done = self.env['stock.picking'].search([
            ('origin', '=', self.origin),  # Filtrar por el campo 'origin'
            ('state', '=', 'done')  # Solo pickings en estado 'done'
        ])
        if not pickings_done:
            raise ValueError(_("No hay movimientos de inventario completados para devolver relacionados con esta factura."))

        # Tomar el primer picking (ajusta si necesitas manejar múltiples pickings)
        picking = pickings_done[0]

        # Crear el wizard de devolución
        return_wizard = self.env['stock.return.picking'].create({
            'picking_id': picking.id,
        })

        # Redirigir al wizard para que el usuario complete el proceso manualmente
        return {
            'name': _('Devolución de Inventario'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.return.picking',
            'view_mode': 'form',
            'res_id': return_wizard.id,
            'target': 'new',
        }
        
    @api.multi
    def action_invoice_open(self):
        """
        Modifica la validación de la nota de crédito para verificar el check.
        """
        for invoice in self:
            if invoice.type == 'out_refund' and not invoice.check_return:
                raise ValueError(_("No se puede validar la nota de crédito porque las devoluciones no están completadas."))
        return super(AccountInvoice, self).action_invoice_open()