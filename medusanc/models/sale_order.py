from odoo import models, api

class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    @api.multi
    def action_invoice_open(self):
        res = super(AccountInvoice, self).action_invoice_open()
        for invoice in self:
            if invoice.type == 'out_refund' and invoice.refund_invoice_id:
                # Obtener la factura original
                original_invoice = invoice.refund_invoice_id

                # Acceder al pedido de venta desde el campo relacionado
                sale_order = original_invoice.sale_order_id

                if sale_order:
                    # Filtrar solo los pickings en estado 'done'
                    pickings_done = sale_order.picking_ids.filtered(lambda p: p.state == 'done')

                    if pickings_done:
                        for picking in pickings_done:
                            self._execute_return_wizard(picking)
        return res

    def _execute_return_wizard(self, picking):
        """
        Ejecuta el wizard de devolución para el picking proporcionado.
        """
        # Verificar que el picking existe y es válido
        if not picking or not picking.exists():
            return

        # Crear el wizard de devolución
        return_wizard = self.env['stock.return.picking'].create({
            'picking_id': picking.id,
        })

        # Llenar automáticamente las líneas del wizard
        return_wizard_lines = []
        for move in picking.move_lines:
            if move.product_id.type != 'service':  # Ignorar servicios
                return_wizard_lines.append((0, 0, {
                    'product_id': move.product_id.id,
                    'quantity': move.quantity_done,
                    'move_id': move.id,
                }))

        if return_wizard_lines:
            return_wizard.write({'product_return_moves': return_wizard_lines})
            # Ejecutar la devolución
            return_wizard.create_returns()