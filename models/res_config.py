from odoo import models, fields, api


class ResUsers(models.Model):
    _inherit = "res.users"

    team_member_ids = fields.Many2many("res.partner", string="Team Members")
    agreement_expiring_in_ninty_ids = fields.Many2many(
        'res.partner',
        'ninty_days_reminder',
        'ninty_days',
        'ninty_days_alert',
        string="Agreement Expiring in 90 Days"
    )
    payment_reminder_after_seven_days_ids = fields.Many2many(
        'res.partner',
        'payment_reminder',
        'payment_due_reminder',
        'after_seven_days',
        string="Payment Due Reminder after 7 Days"
    )
    upcoming_installment_before_fifteen_days_ids = fields.Many2many(
        'res.partner',
        'upcoming_installment',
        'upcoming_installment_payment',
        'before_fifteen_days',
        string='Upcoming Installment Payment in 15 Days'
    )


class RentalConfig(models.TransientModel):
    _inherit = 'res.config.settings'

    reminder_days = fields.Integer(string='Days', default=5,
                                   config_parameter='rental_management.reminder_days')
    sale_reminder_days = fields.Integer(string="Days ", default=3,
                                        config_parameter='rental_management.sale_reminder_days')
    internal_user_id = fields.Many2one("res.users", string="Internal User",
                                       config_parameter='rental_management.internal_user_id')
    team_member_ids = fields.Many2many(
        related="internal_user_id.team_member_ids",
        string='Team Members',
        readonly=False)
    property_report_mails = fields.Char(string='Emails',
                                        config_parameter="rental_management.property_report_mails")

    agreement_expiring_in_ninty_ids = fields.Many2many(
        related="internal_user_id.agreement_expiring_in_ninty_ids",
        readonly=False)

    payment_reminder_after_seven_days_ids = fields.Many2many(
        related="internal_user_id.payment_reminder_after_seven_days_ids",
        readonly=False)

    upcoming_installment_before_fifteen_days_ids = fields.Many2many(
        related="internal_user_id.upcoming_installment_before_fifteen_days_ids",
        readonly=False
    )

    alert_mail_sender_email = fields.Char('Sender Email',
                                          config_parameter="rental_management.alert_mail_sender_email")

    utility_bill_wh_template_id = fields.Many2one('whatsapp.template',
                                                  string="Utility Bill Whatsapp Template",
                                                  domain="[('model','=','utility.bill')]",
                                                  config_parameter='rental_management.utility_bill_whatsapp_template_id')

    payment_receipt_wh_template_id = fields.Many2one('whatsapp.template',
                                                     string="Payment Receipt Whatsapp Template",
                                                     domain="[('model','=','account.payment')]",
                                                     config_parameter='rental_management.payment_receipt_whatsapp_template_id')

    # Bank Details (used in lease agreement reports)
    bank_name = fields.Char(
        string='Bank Name',
        default='CRDB BANK (T) LTD',
        config_parameter='rental_management.bank_name')

    bank_account_usd = fields.Char(
        string='USD Account No.',
        config_parameter='rental_management.bank_account_usd')

    bank_account_tzs = fields.Char(
        string='TZS Account No.',
        config_parameter='rental_management.bank_account_tzs')
