from odoo import models, fields, api, _

class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    check_return = fields.Boolean(
        string="Devolución Completada",
        default=False,
        help="Este campo se activa cuando el usuario completa las devoluciones relacionadas con el picking validado."
    )

    def action_open_return_wizard(self):
        """
        Abre el wizard de devolución directamente desde el picking relacionado con la factura.
        """
        self.ensure_one()

        # Verificar que la factura tiene un picking validado
        if not self.validated_picking_id:
            raise ValueError(_("Esta factura no tiene un picking validado asociado para la devolución."))

        # Verificar que el picking está en estado 'done'
        picking = self.validated_picking_id
        if picking.state != 'done':
            raise ValueError(_("El picking asociado a esta factura no está en estado 'done'."))

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