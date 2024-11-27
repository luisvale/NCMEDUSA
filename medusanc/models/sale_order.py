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


class StockReturnPicking(models.TransientModel):
    _inherit = 'stock.return.picking'

    def create_returns(self):
        """
        Sobrescribe la acción para:
        1. Completar automáticamente el picking de devolución (estado done).
        2. Redirigir al usuario a la factura relacionada.
        """
        res = super(StockReturnPicking, self).create_returns()

        # Obtener el picking de devolución recién creado
        return_pickings = self.env['stock.picking'].browse(res.get('res_id', []))
        for return_picking in return_pickings:
            if return_picking.state in ['draft', 'waiting', 'confirmed']:
                # Confirmar el picking
                return_picking.action_confirm()

                # Asignar productos
                return_picking.action_assign()

                # Marcar cantidades hechas y validar el picking
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
        Modifica la validación de la nota de crédito para verificar el check.
        """
        for invoice in self:
            if invoice.type == 'out_refund' and not invoice.check_return:
                raise ValueError(_("No se puede validar la nota de crédito porque las devoluciones no están completadas."))
        return super(AccountInvoice, self).action_invoice_open()

    @api.multi
    def action_invoice_open(self):
        """
        Modifica la validación de la nota de crédito para verificar el check.
        """
        for invoice in self:
            if invoice.type == 'out_refund' and not invoice.check_return:
                raise ValueError(_("No se puede validar la nota de crédito porque las devoluciones no están completadas."))
        return super(AccountInvoice, self).action_invoice_open()