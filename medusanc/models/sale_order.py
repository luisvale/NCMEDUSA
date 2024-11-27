from odoo import models, fields, api, _

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def button_validate(self):
        """
        Sobrescribe la validación del picking para regresar a la factura cuando proviene de ese flujo.
        """
        res = super(StockPicking, self).button_validate()

        # Verificar si el picking está relacionado con una factura
        if self.origin and self.sale_id:
            invoice = self.env['account.invoice'].search([('validated_picking_id', '=', self.id)], limit=1)
            if invoice:
                # Marcar como completada la devolución en la factura
                invoice.check_return = True

        return res


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    check_return = fields.Boolean(
        string="Devolución Completada",
        default=False,
        help="Este campo se activa cuando el usuario completa las devoluciones relacionadas con el picking validado."
    )

    def action_open_related_picking(self):
        """
        Abre directamente la pantalla del picking relacionado con la factura.
        """
        self.ensure_one()

        # Verificar que la factura tiene un picking validado
        if not self.validated_picking_id:
            raise ValueError(_("Esta factura no tiene un picking validado asociado."))

        # Asegurarse de que el picking existe y está relacionado correctamente
        picking = self.validated_picking_id
        if not picking.exists():
            raise ValueError(_("El picking relacionado no existe o ha sido eliminado."))

        # Abrir la pantalla del picking relacionado
        return {
            'type': 'ir.actions.act_window',
            'name': _('Picking Relacionado'),
            'res_model': 'stock.picking',
            'view_mode': 'form',
            'res_id': picking.id,
            'target': 'new',  # Abrir en una ventana modal para mantener la conexión con la factura
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