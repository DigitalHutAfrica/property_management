from collections import defaultdict

from odoo import Command, models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools import frozendict


class InheritRegisterPayment(models.TransientModel):
    _inherit = 'account.payment.register'

    def _create_payments(self):
        res = super(InheritRegisterPayment, self)._create_payments()
        self.action_assign_property(res)
        return res

    def action_assign_property(self, payments):
        for payment in payments:
            invoice_id = False
            if len(payment.reconciled_invoice_ids) == 1:
                invoice_id = payment.reconciled_invoice_ids
            move_id = payment.move_id
            if invoice_id:
                payment.property_id = invoice_id.tenancy_property_id.id
                move_id.write({
                    'tenancy_property_id': invoice_id.tenancy_property_id.id,
                    'tenancy_parent_property_id': invoice_id.tenancy_parent_property_id.id,
                    'invoice_period_to_date': invoice_id.invoice_period_to_date,
                    'invoice_period_from_date': invoice_id.invoice_period_from_date
                })
