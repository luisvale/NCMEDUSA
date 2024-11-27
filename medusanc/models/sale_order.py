from odoo import models, fields, api, _


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def action_return_picking_wizard(self):
        """
        Abre automáticamente el wizard de devolución desde el picking
        y configura las líneas del wizard con los movimientos del picking.
        """
        self.ensure_one()

        # Crear el wizard de devolución con la ubicación de devolución
        return_wizard = self.env['stock.return.picking'].create({
            'picking_id': self.id,
            'location_id': self.location_id.id,  # Asignar ubicación del picking
        })

        # Crear las líneas del wizard basadas en los movimientos del picking
        lines = []
        for move in self.move_lines.filtered(lambda m: m.quantity_done > 0):
            lines.append((0, 0, {
                'product_id': move.product_id.id,
                'quantity': move.quantity_done,
                'move_id': move.id,
            }))

        # Escribir las líneas en el wizard
        if lines:
            return_wizard.write({'product_return_moves': lines})

        # Redirigir al wizard de devolución
        return {
            'name': _('Devolución de Inventario'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.return.picking',
            'view_mode': 'form',
            'res_id': return_wizard.id,
            'target': 'new',  # Abrir como ventana modal
        }

    def action_create_credit_note(self):
        """
        Crea la nota de crédito basada en este picking de devolución.
        """
        self.ensure_one()

        if self.picking_type_id.code != 'incoming' or not self.origin:
            raise ValueError(_("Este picking no está configurado como devolución o no tiene un origen válido."))

        # Crear una factura de tipo devolución
        invoice_vals = {
            'type': 'out_refund',
            'partner_id': self.partner_id.id,
            'origin': self.name,
            'invoice_line_ids': [(0, 0, {
                'product_id': move.product_id.id,
                'quantity': move.quantity_done,
                'price_unit': move.product_id.list_price,
                'name': move.product_id.name,
            }) for move in self.move_lines if move.quantity_done > 0],
        }
        credit_note = self.env['account.invoice'].create(invoice_vals)

        # Retornar vista de la nota de crédito creada
        return {
            'type': 'ir.actions.act_window',
            'name': _('Nota de Crédito'),
            'res_model': 'account.invoice',
            'view_mode': 'form',
            'res_id': credit_note.id,
            'target': 'current',
        }




class StockReturnPicking(models.TransientModel):
    _inherit = 'stock.return.picking'

    def create_returns(self):
        """
        Completa el flujo de devolución automáticamente:
        1. Valida el movimiento de devolución creado.
        2. Redirige automáticamente al formulario de la factura.
        """
        res = super(StockReturnPicking, self).create_returns()

        # Obtener el picking de devolución recién creado
        return_pickings = self.env['stock.picking'].browse(res.get('res_id', []))
        for return_picking in return_pickings:
            # Confirmar el picking
            if return_picking.state in ['draft', 'waiting', 'confirmed']:
                return_picking.action_confirm()
                return_picking.action_assign()

                # Marcar las cantidades hechas y validar el picking
                for move in return_picking.move_lines:
                    move.quantity_done = move.product_uom_qty
                return_picking.button_validate()  # Validar el picking automáticamente

        # Si el contexto incluye una factura, redirigir al formulario de la factura
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
        Al confirmar la nota de crédito, valida el picking de devolución asociado.
        """
        res = super(AccountInvoice, self).action_invoice_open()
        for invoice in self:
            if invoice.type == 'out_refund' and invoice.origin:
                # Buscar el picking relacionado al origen de la factura
                picking = self.env['stock.picking'].search([('name', '=', invoice.origin)], limit=1)
                if picking and picking.state not in ['done']:
                    # Confirmar y validar el picking
                    picking.action_confirm()
                    picking.action_assign()
                    for move in picking.move_lines:
                        move.quantity_done = move.product_uom_qty
                    picking.button_validate()

        return res
