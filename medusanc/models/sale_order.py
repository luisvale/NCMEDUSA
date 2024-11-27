from odoo import models, fields, api, _

class StockReturnPicking(models.TransientModel):
    _inherit = 'stock.return.picking'

    def create_returns(self):
        """
        Sobrescribe la acción para devolver al usuario a la factura después de procesar.
        """
        res = super(StockReturnPicking, self).create_returns()

        # Si el contexto incluye una factura, redirigir al usuario a la factura
        if self.env.context.get('return_to_invoice_id'):
            return {
                'type': 'ir.actions.act_window',
                'name': _('Factura'),
                'res_model': 'account.invoice',
                'view_mode': 'form',
                'res_id': self.env.context['return_to_invoice_id'],
                'target': 'current',  # Regresar a la factura en la misma pestaña
            }

        return res



class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    check_return = fields.Boolean(
        string="Devolución Completada",
        default=False,
        help="Este campo se activa cuando el usuario completa las devoluciones relacionadas con el picking validado."
    )

    def action_open_return_wizard(self):
        """
        Abre la pantalla del picking relacionado y automáticamente muestra el wizard de devolución.
        """
        self.ensure_one()

        # Verificar que la factura tiene un picking validado
        if not self.validated_picking_id:
            raise ValueError(_("Esta factura no tiene un picking validado asociado."))

        # Verificar que el picking está en estado 'done'
        picking = self.validated_picking_id
        if picking.state != 'done':
            raise ValueError(_("El picking asociado a esta factura no está en estado 'done'."))

        # Ejecutar automáticamente el botón 'Devolver' y abrir el wizard
        return picking.with_context({
            'return_to_invoice_id': self.id  # Contexto para regresar a la factura al cerrar
        }).action_return_picking_wizard()




    @api.multi
    def action_invoice_open(self):
        """
        Modifica la validación de la nota de crédito para verificar el check.
        """
        for invoice in self:
            if invoice.type == 'out_refund' and not invoice.check_return:
                raise ValueError(_("No se puede validar la nota de crédito porque las devoluciones no están completadas."))
        return super(AccountInvoice, self).action_invoice_open()