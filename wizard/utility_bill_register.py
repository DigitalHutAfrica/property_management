from collections import defaultdict

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools import frozendict


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    property_id = fields.Many2one('property.details', string="Property ")


class UtilityBillRegister(models.TransientModel):
    _name = 'utility.bill.register'
    _description = 'Utility Bill Register'

    payment_date = fields.Date(string="Payment Date", required=True,
                               default=fields.Date.context_today)
    amount = fields.Monetary(currency_field='currency_id', store=True,
                             readonly=False,
                             )
    communication = fields.Char(string="Memo", store=True, readonly=False,
                                )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Currency',
        store=True, readonly=False,
        help="The payment's currency.")

    journal_id = fields.Many2one('account.journal',
                                 string="Journal",
                                 domain="[('type', 'in', ('bank', 'cash'))]",
                                 default=lambda self: self.env[
                                     'account.journal'].search(
                                     [('type', '=', 'bank')],
                                     limit=1))

    payment_method_line_id = fields.Many2one('account.payment.method.line',
                                             string='Payment Method',
                                             readonly=False,
                                             domain="[('payment_type', '=', 'outbound'),('journal_id', '=', journal_id)]")
    show_partner_bank_account = fields.Boolean(string="Is Bank")
    partner_bank_id = fields.Many2one(
        comodel_name='res.partner.bank',
        string="Recipient Bank Account",
        readonly=True, related="journal_id.bank_account_id"
    )
    bill_ids = fields.Many2many('utility.bill',
                                'utility_bill_payment_register_rel',
                                'wizard_id', 'bill_id')
    is_multiple = fields.Boolean()

    @api.model
    def default_get(self, fields_list):
        # OVERRIDE
        res = super().default_get(fields_list)
        active_ids = self._context.get('active_ids')
        utility_bill_id = self.env['utility.bill'].browse(active_ids)
        res['currency_id'] = self.env.company.currency_id.id
        res['bill_ids'] = active_ids
        res['is_multiple'] = True if not len(active_ids) == 1 else False
        if len(active_ids) == 1:
            res['amount'] = utility_bill_id.total_amount
            res['communication'] = utility_bill_id.dn_no
            res['currency_id'] = utility_bill_id.currency_id.id
        return res

    def get_whatsapp_template(self, template_id):
        """Get Template from Settings"""
        wa_template_id = False
        config_template_id = self.env['ir.config_parameter'].sudo().get_param(template_id)
        if config_template_id:
            wa_template_id = self.env['whatsapp.template'].sudo().browse(int(config_template_id))
        return wa_template_id

    def action_create_payments(self):
        mail_template = self.env.ref(
            'account.mail_template_data_payment_receipt').sudo()
        payment_receipt_wh_template = self.get_whatsapp_template(
            'rental_management.payment_receipt_whatsapp_template_id')
        if len(self.bill_ids) == 1:
            active_id = self._context.get('active_ids')
            utility_bill_id = self.env['utility.bill'].browse(active_id)
            vals = {
                'payment_type': 'inbound',
                'partner_id': utility_bill_id.tenant_name.id,
                'amount': self.amount,
                'currency_id': self.currency_id.id,
                'ref': self.communication,
                'date': self.payment_date,
                'journal_id': self.journal_id.id,
                'payment_method_line_id': self.payment_method_line_id.id,
                'property_id': utility_bill_id.property_id.id,
                'utility_bill_id': utility_bill_id.id
            }

            payment = self.env['account.payment'].create(vals)
            payment.action_post()
            utility_bill_id.write({'payment_id': payment.id, 'state': 'posted',
                                   'r_payment_state': 'Paid'})
            if payment.move_id:
                payment.move_id.write({
                    'tenancy_property_id': utility_bill_id.property_id.id,
                    'tenancy_parent_property_id': utility_bill_id.main_property_id.id,
                })
            if mail_template and payment:
                mail_template.send_mail(payment.id, force_send=True)

            if payment_receipt_wh_template and payment:
                utility_bill_id.action_send_whatsapp_message(
                    phone=utility_bill_id.tenant_name.mobile,
                    wa_template_id=payment_receipt_wh_template,
                    record=payment)

            return {
                'type': 'ir.actions.act_window',
                'name': 'Payments',
                'res_model': 'account.payment',
                'res_id': payment.id,
                'view_mode': 'form',
                'target': 'current'
            }

        else:
            for rec in self.bill_ids:
                vals = {
                    'payment_type': 'inbound',
                    'partner_id': rec.tenant_name.id,
                    'amount': rec.total_amount,
                    'currency_id': rec.currency_id.id,
                    'ref': rec.dn_no,
                    'date': self.payment_date,
                    'journal_id': self.journal_id.id,
                    'payment_method_line_id': self.payment_method_line_id.id,
                    'property_id': rec.property_id.id,
                    'utility_bill_id': rec.id
                }
                payment = self.env['account.payment'].create(vals)
                payment.action_post()
                rec.write({'payment_id': payment.id, 'state': 'posted',
                           'r_payment_state': 'Paid'})
                if payment.move_id:
                    payment.move_id.write({
                        'tenancy_property_id': rec.property_id.id,
                        'tenancy_parent_property_id': rec.main_property_id.id,
                    })

                if mail_template and payment:
                    mail_template.send_mail(payment.id, force_send=True)

                if payment_receipt_wh_template and payment:
                    rec.action_send_whatsapp_message(
                        phone=rec.tenant_name.mobile,
                        wa_template_id=payment_receipt_wh_template,
                        record=payment)

            return {
                'effect': {
                    'fadeout': 'slow',
                    'message': 'Payment Registered Successfully',
                    'type': 'rainbow_man',
                }
            }
