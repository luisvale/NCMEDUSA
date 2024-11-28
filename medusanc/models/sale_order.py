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
        Genera una nota de crédito basada en los productos y cantidades del picking actual.
        """
        self.ensure_one()

        if not self.validated_invoice_id:
            raise ValueError(_("Este picking no tiene una factura validada asociada."))

        # Obtener la factura relacionada desde el campo validated_invoice_id
        invoice = self.validated_invoice_id

        # Crear las líneas de la nota de crédito usando los movimientos del picking
        credit_note_lines = []
        for move in self.move_lines.filtered(lambda m: m.quantity_done > 0):
            # Buscar la línea de factura correspondiente al producto
            invoice_line = invoice.invoice_line_ids.filtered(lambda l: l.product_id == move.product_id)
            if not invoice_line:
                raise ValueError(_("No se encontró una línea de factura para el producto %s") % move.product_id.display_name)

            # Crear las líneas de la nota de crédito
            credit_note_lines.append((0, 0, {
                'product_id': move.product_id.id,
                'quantity': move.quantity_done,
                'price_unit': invoice_line.price_unit,  # Usar el precio unitario de la línea original
                'name': move.product_id.name,
                'account_id': invoice_line.account_id.id,  # Cuenta de la línea de factura
                'tax_ids': [(6, 0, invoice_line.tax_ids.ids)] if 'tax_ids' in invoice_line else [],  # Verificar si 'tax_ids' existe
            }))

        # Crear la nota de crédito
        credit_note = self.env['account.move'].create({
            'move_type': 'out_refund',
            'partner_id': invoice.partner_id.id,
            'invoice_origin': invoice.name,
            'invoice_line_ids': credit_note_lines,
        })

        return {
            'name': _('Nota de Crédito'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': credit_note.id,
            'target': 'current',  # Abrir la nota de crédito en la misma pestaña
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

    def action_post(self):
        res = super(AccountMove, self).action_post()

        for move in self:
            if move.move_type == 'out_refund':
                # Confirmar el picking de devolución relacionado
                picking = self.env['stock.picking'].search([('origin', '=', move.invoice_origin)], limit=1)
                if picking and picking.state not in ['done', 'cancel']:
                    picking.action_confirm()
                    picking.action_assign()
                    for move_line in picking.move_lines:
                        move_line.quantity_done = move_line.product_uom_qty
                    picking.button_validate()

        return res
