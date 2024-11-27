from odoo import models, api, _

class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    @api.multi
    def action_invoice_open(self):
        res = super(AccountInvoice, self).action_invoice_open()
        for invoice in self:
            if invoice.type == 'out_refund' and invoice.refund_invoice_id:
                # Obtener la factura relacionada
                original_invoice = invoice.refund_invoice_id
                if original_invoice.picking_ids:
                    for picking in original_invoice.picking_ids.filtered(lambda p: p.state == 'done'):
                        self._create_inventory_return(picking, invoice)
        return res

    def _create_inventory_return(self, picking, refund_invoice):
        """
        Crea la devolución de inventario en base al picking original y la nota de crédito.
        """
        stock_return_picking = self.env['stock.return.picking'].create({
            'picking_id': picking.id,
        })
        return_wizard_lines = []
        for move in picking.move_lines:
            # Busca la línea correspondiente de la factura y verifica la cantidad devuelta
            invoice_line = refund_invoice.invoice_line_ids.filtered(
                lambda l: l.product_id == move.product_id and not l.product_id.type == 'service'
            )
            if invoice_line:
                return_wizard_lines.append((0, 0, {
                    'product_id': move.product_id.id,
                    'quantity': invoice_line.quantity,
                    'move_id': move.id,
                }))

        if return_wizard_lines:
            stock_return_picking.write({'product_return_moves': return_wizard_lines})
            stock_return_picking.create_returns()