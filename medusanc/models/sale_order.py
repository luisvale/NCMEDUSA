from odoo import models, fields, api, _

class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    check_return = fields.Boolean(
        string="Devolución Completada",
        default=False,
        help="Este campo se activa automáticamente cuando se completa la devolución de los productos asociados a la factura."
    )

    def action_open_return_wizard_from_invoice(self):
        """
        Ejecuta el wizard de devolución desde la factura.
        """
        self.ensure_one()
        if not self.sale_order_id or not self.sale_order_id.picking_ids:
            raise ValueError(_("No hay movimientos de inventario asociados a esta factura."))

        # Filtrar los pickings en estado 'done'
        pickings_done = self.sale_order_id.picking_ids.filtered(lambda p: p.state == 'done')
        if not pickings_done:
            raise ValueError(_("No hay movimientos de inventario completados para devolver."))

        # Tomar el primer picking (puedes ajustar para manejar múltiples pickings)
        picking = pickings_done[0]

        # Crear el wizard de devolución
        return_wizard = self.env['stock.return.picking'].create({
            'picking_id': picking.id,
        })

        # Redirigir al wizard
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
                raise ValueError(_("No se puede validar la nota de crédito porque la devolución de inventario no está completada."))
        return super(AccountInvoice, self).action_invoice_open()