# -*- coding: utf-8 -*-
# Copyright 2020-Today TechKhedut.
# Part of TechKhedut. See LICENSE file for full copyright and licensing details.
from dateutil.relativedelta import relativedelta
from datetime import timedelta
from odoo import fields, models, api
from odoo.exceptions import ValidationError, UserError


class RentInvoice(models.Model):
    _name = "rent.invoice"
    _description = "Create Invoice for Rented property"
    _rec_name = "tenancy_id"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    tenancy_id = fields.Many2one("tenancy.details", string="Tenancy No.")
    customer_id = fields.Many2one(
        related="tenancy_id.tenancy_id", string="Customer", store=True
    )
    type = fields.Selection(
        [
            ("deposit", "Deposit"),
            ("rent", "Rent"),
            ("maintenance", "Maintenance"),
            ("penalty", "Penalty"),
            ("full_rent", "Full Rent"),
        ],
        string="Payment",
        default="rent",
    )
    invoice_date = fields.Date(string="Invoice Date")
    company_id = fields.Many2one(
        "res.company", string="Company", default=lambda self: self.env.company
    )
    currency_id = fields.Many2one(
        "res.currency", related="tenancy_id.currency_id", string="Currency"
    )
    rent_amount = fields.Monetary(string="Rent Amount")
    amount = fields.Monetary(string="Total Rent Amount")
    description = fields.Char(string="Description")
    rent_invoice_id = fields.Many2one("account.move", string="Invoice")
    amount_tax = fields.Monetary(related="rent_invoice_id.amount_tax")
    payment_state = fields.Selection(
        related="rent_invoice_id.payment_state", string="Payment Status",
        store=True
    )
    landlord_id = fields.Many2one(
        related="tenancy_id.property_id.landlord_id", store=True
    )
    is_yearly = fields.Boolean()
    remain = fields.Integer()
    tenancy_type = fields.Selection(related="tenancy_id.type",
                                    string="Tenancy Type")
    service_amount = fields.Monetary(string="Service Amount")
    is_extra_service = fields.Boolean(related="tenancy_id.is_extra_service")
    last_rent_line = fields.Boolean(string="Last Rent Line")
    property_id = fields.Many2one(related="tenancy_id.property_id", store=True)
    invoice_period_to_date = fields.Date(string="Start Date")
    invoice_period_from_date = fields.Date(string="End Date")
    total_rent = fields.Monetary(related="tenancy_id.total_rent")
    rent_per_month = fields.Monetary(related="tenancy_id.total_rent_month")
    service_charge_month = fields.Monetary(
        related='tenancy_id.service_charge_month')
    contract_type_name = fields.Selection(
        related="tenancy_id.contract_type_name")
    property_type = fields.Selection(related="tenancy_id.property_type")
    rent = fields.Monetary(string='Rent / Month', compute='compute_rent_month')

    parent_property_id = fields.Many2one(
        related="property_id.parent_property_id", store=True,
        string="Parent Property")

    temp_end_date = fields.Date()
    team_members = fields.Char()

    tenancy_start_date = fields.Date(related='tenancy_id.start_date',
                                     string='Tenancy Start Date')
    tenancy_end_date = fields.Date(related='tenancy_id.end_date',
                                   string='Tenancy End Date')

    months = fields.Integer(compute='compute_months')
    active = fields.Boolean(default=True, string='Active')
    res_id = fields.Char(string='Contract Id')
    res_name = fields.Char(string='Contract Name')

    rent_month = fields.Monetary(string='Rent /Month')

    def unlink(self):
        for record in self:
            if (
                    record.payment_state == "not_paid"
                    or record.payment_state == "in_payment"
                    or record.payment_state == "paid"
                    or record.payment_state == "partial"
            ):
                raise ValidationError(
                    "You cannot delete an item linked to a posted entry."
                )
        res = super(RentInvoice, self).unlink()
        return res

    @api.onchange('invoice_period_to_date', 'invoice_period_from_date')
    def onchange_dates_compute_amount(self):
        for rec in self:
            amount = rec.amount
            if rec.invoice_period_to_date and rec.invoice_period_from_date:
                delta = relativedelta(
                    rec.invoice_period_from_date + timedelta(days=1),
                    rec.invoice_period_to_date)
                total_months = (delta.years * 12) + delta.months
                total_months = abs(total_months)
                amount = rec.rent_month * total_months
            rec.amount = amount

    @api.depends('invoice_period_to_date', 'invoice_period_from_date')
    def compute_months(self):
        for rec in self:
            total_months = 0
            if rec.invoice_period_to_date and rec.invoice_period_from_date:
                delta = relativedelta(
                    rec.invoice_period_from_date + timedelta(days=1),
                    rec.invoice_period_to_date)
                total_months = (delta.years * 12) + delta.months
                total_months = abs(total_months)
            rec.months = total_months

    @api.depends('tenancy_id')
    def compute_rent_month(self):
        for rec in self:
            rent_month = rec.tenancy_id.total_rent
            if rec.tenancy_id.property_type == "commercial" and rec.tenancy_id.contract_type_name == "lease":
                rent_month = rec.tenancy_id.total_rent_month
            if rec.tenancy_id.property_type in ["residential",
                                                "commercial"] and rec.tenancy_id.contract_type_name == "service":
                rent_month = rec.tenancy_id.service_charge_month
            rec.rent = rent_month

    def action_prior_payment_alert(self):
        """15 Days Prior alert of upcoming installment"""
        today = fields.Date.today()
        records = self.env["rent.invoice"].sudo().search(
            [('rent_invoice_id', '=', False),
             ('contract_type_name', '=', 'lease')])
        mail_template = self.env.ref(
            "rental_management.payment_prior_alert_mail_template").sudo()
        sender_email = self.env['ir.config_parameter'].sudo().get_param(
            'rental_management.alert_mail_sender_email')
        for record in records:
            if record.invoice_date:
                prior_fifteen_date = record.invoice_date - timedelta(days=14)
                prior_three_date = record.invoice_date - timedelta(days=2)
                if today in (
                        prior_fifteen_date, prior_three_date) and mail_template and sender_email:
                    company = record.company_id
                    mails = company.upcoming_installment_before_fifteen_days_ids.mapped(
                        'email')
                    filtered_mails = [item for item in mails if
                                      not isinstance(item, bool)]
                    mails_str = ""
                    if filtered_mails:
                        mails_str = ", ".join(filtered_mails)
                    mail_values = {
                        "email_cc": mails_str,
                        "email_from": sender_email
                    }
                    ctx = {
                        'remaining_days': 15 if today == prior_fifteen_date else 3
                    }
                    mail_template.with_context(ctx).send_mail(record.id, email_values=mail_values,
                                                              force_send=True)

    def action_payment_reminder_alert(self):
        """Property Payment due after 7 days of invoice creation"""
        today = fields.Date.today()
        records = self.env["rent.invoice"].sudo().search(
            [('payment_state', '=', 'not_paid'),
             ('contract_type_name', '=', 'lease')])
        mail_template = self.env.ref(
            "rental_management.payment_followup_alert_mail_template").sudo()
        sender_email = self.env['ir.config_parameter'].sudo().get_param(
            'rental_management.alert_mail_sender_email')
        for record in records:
            if record.invoice_date and (
                    today - record.invoice_date).days == 7 and mail_template and sender_email:
                company = record.company_id
                mails = company.payment_reminder_after_seven_days_ids.mapped(
                    'email')
                filtered_mails = [item for item in mails if
                                  not isinstance(item, bool)]
                mails_str = ""
                if filtered_mails:
                    mails_str = ", ".join(filtered_mails)
                mail_values = {
                    "subject": f"Follow-up: Outstanding Payment Reminder [{record.property_id.name}]",
                    "email_cc": mails_str,
                    "email_from": sender_email
                }
                mail_template.send_mail(record.id, email_values=mail_values,
                                        force_send=True)

    def action_invoice_raise_alert_before(self):
        today = fields.Date.today()
        records = self.env["rent.invoice"].sudo().search(
            [('rent_invoice_id', '=', False),
             ('contract_type_name', '=', 'lease')])
        mail_template = self.env.ref(
            "rental_management.invoice_raise_alert_mail_template").sudo()
        internal_user_id = self.env["ir.config_parameter"].sudo().get_param(
            "rental_management.internal_user_id")
        internal_user = self.env['res.users'].browse(int(internal_user_id))
        mail_ids = internal_user.team_member_ids.ids
        mails = internal_user.team_member_ids.mapped('email')
        mails_str = ", ".join(mails)
        names = internal_user.team_member_ids.mapped('name')
        name_str = ", ".join(names)
        self.team_members = name_str
        mail_values = {
            'recipient_ids': [(6, 0, mail_ids)],
            # 'email_to': mails_str,
            'email_from': self.env['ir.config_parameter'].sudo().get_param('rental_management.alert_mail_sender_email') or self.env.company.email or ''
        }
        for record in records:
            if record.invoice_date and (record.invoice_date - today).days == 3 and mail_template:
                mail_template.with_context(
                    {"team_member": name_str}).send_mail(record.id,
                                                         force_send=True,
                                                         email_values=mail_values)

    @api.model
    def get_parent_property(self):
        records = self.env['rent.invoice'].search(
            [('parent_property_id', '=', False)])
        for rec in records:
            temporary_id = rec.property_id.id
            rec.write({
                'property_id': False,
            })
            rec.write({
                'property_id': temporary_id,
            })

    @api.model
    def fix_total_rent_amount(self):
        records = self.env['rent.invoice'].sudo().search([])
        for rec in records:
            amount = rec.amount
            if rec.invoice_period_to_date and rec.invoice_period_from_date:
                delta = relativedelta(
                    rec.invoice_period_from_date + timedelta(days=1),
                    rec.invoice_period_to_date)
                total_months = (delta.years * 12) + delta.months
                total_months = abs(total_months)
                amount = rec.rent_month * total_months
            rec.write({
                'amount': amount
            })

    @api.model
    def fix_total_service_charge(self):
        records = self.env['rent.invoice'].sudo().search(
            [('rent_invoice_id', '=', False)])
        for rec in records:
            if rec.tenancy_id.contract_type_name == 'service':
                amount = rec.amount
                if rec.invoice_period_to_date and rec.invoice_period_from_date:
                    delta = relativedelta(
                        rec.invoice_period_from_date + timedelta(days=1),
                        rec.invoice_period_to_date)
                    total_months = (delta.years * 12) + delta.months
                    total_months = abs(total_months)
                    amount = rec.rent_month * total_months
                rec.amount = amount

    @api.model
    def fix_new_rent_per_month(self):
        records = self.env['rent.invoice'].sudo().search([])
        for rec in records:
            rent_month = rec.tenancy_id.total_rent
            if rec.tenancy_id.property_type == "commercial" and rec.tenancy_id.contract_type_name == "lease":
                rent_month = rec.tenancy_id.total_rent_month
            if rec.tenancy_id.property_type in ["residential",
                                                "commercial"] and rec.tenancy_id.contract_type_name == "service":
                rent_month = rec.tenancy_id.service_charge_month
            # if rec.tenancy_id.contract_type_name == 'lease' and rec.tenancy_id.contract_includes == 'rent_and_service':
            #     rent_month += rec.tenancy_id.service_charge_per_month
            rec.rent_month = rent_month

    def action_create_invoice(self):
        for rec in self:
            if not rec.rent_invoice_id:
                invoice_lines = []
                amount = 0
                total_rent_month = rec.tenancy_id.total_rent
                if rec.tenancy_id.property_type == "commercial" and rec.tenancy_id.contract_type_name == 'lease':
                    total_rent_month = rec.tenancy_id.total_rent_month
                if rec.tenancy_id.property_type in ["residential",
                                                    "commercial"] and rec.tenancy_id.contract_type_name == "service":
                    total_rent_month = rec.tenancy_id.service_charge_month

                unit = rec.tenancy_id.payment_term_id.month

                invoice_period_to_date = rec.invoice_date

                if rec.tenancy_id.payment_term_id.rent_unit == "Year" and (
                        not rec.last_rent_line
                ):
                    invoice_period_from_date = rec.invoice_date + relativedelta(
                        years=unit
                    )
                else:
                    invoice_period_from_date = rec.tenancy_id.end_date

                if not rec.last_rent_line:
                    invoice_period_from_date = (
                                                       rec.invoice_date + relativedelta(
                                                   months=unit)
                                               ) - relativedelta(days=1)
                else:
                    invoice_period_from_date = rec.tenancy_id.end_date

                delta = relativedelta(
                    invoice_period_from_date + timedelta(days=1),
                    invoice_period_to_date)
                total_months = (delta.years * 12) + delta.months
                total_months = abs(total_months)
                quantity = total_months

                record = {
                    "product_id": rec.tenancy_id.installment_item_id.id,
                    "name": rec.description,
                    "quantity": rec.months,
                    "price_unit": rec.rent_month,
                    'tax_ids': rec.tenancy_id.installment_item_id.taxes_id,
                }
                invoice_lines.append((0, 0, record))
                rent_record = {
                    "partner_id": rec.customer_id.id,
                    "move_type": "out_invoice",
                    "invoice_date": rec.invoice_date,
                    "invoice_period_to_date": rec.invoice_period_to_date,
                    "invoice_period_from_date": rec.invoice_period_from_date,
                    "tenancy_id": rec.tenancy_id.id,
                    "invoice_line_ids": invoice_lines,
                    "currency_id": rec.tenancy_id.currency_id.id,
                    "tenancy_property_id": rec.tenancy_id.property_id.id,
                    "tenancy_parent_property_id": rec.tenancy_id.property_id.parent_property_id.id
                }
                rec.service_amount = amount
                invoice_id = rec.env["account.move"].create(rent_record)

                invoice_id.action_post()
                rec.rent_invoice_id = invoice_id.id

        # Schedular

    @api.model
    def add_invoice_period_to_old_invoices(self):
        invoice_records = self.env['rent.invoice'].sudo().search([])
        for rec in invoice_records:
            if rec.rent_invoice_id:
                rec.write({
                    'invoice_period_to_date': rec.rent_invoice_id.invoice_period_to_date,
                    'invoice_period_from_date': rec.rent_invoice_id.invoice_period_from_date
                })
            else:
                if rec.last_rent_line:
                    rec.write({
                        'invoice_period_to_date': rec.invoice_date,
                        'invoice_period_from_date': rec.tenancy_id.end_date,
                    })
                else:
                    rec.write({
                        'invoice_period_to_date': rec.invoice_date,
                        'invoice_period_from_date': rec.invoice_date + relativedelta(
                            months=rec.tenancy_id.payment_term_id.month) - relativedelta(
                            days=1),
                    })

    @api.model
    def set_company_as_per_contract(self):
        records = self.env['rent.invoice'].sudo().search([])
        for rec in records:
            rec.company_id = rec.tenancy_id.company_id.id


class TenancyInvoice(models.Model):
    _inherit = "account.move"

    tenancy_id = fields.Many2one(
        "tenancy.details", string="Tenancy", store=True
    )
    sold_id = fields.Many2one(
        "property.vendor", string="Sold Information", store=True
    )
    property_id = fields.Many2one(related='tenancy_id.property_id',
                                  string='Related Property')
    tenancy_property_id = fields.Many2one('property.details',
                                          string="Property")
    tenancy_parent_property_id = fields.Many2one('parent.property',
                                                 string="Parent Property")
    sold_property_id = fields.Many2one(
        related="sold_id.property_id", string="Sold Property"
    )
    invoice_period_to_date = fields.Date(string="Start Date")
    invoice_period_from_date = fields.Date(string="End date")
    amount_total_in_words = fields.Char(
        "Amount Total in Words", compute="_compute_amount_total_in_words"
    )
    property_name = fields.Char(related="property_id.name", store=True,
                                string='Property Name')

    def _compute_amount_total_in_words(self):
        for record in self:
            record[
                "amount_total_in_words"] = record.currency_id.amount_to_text(
                record.amount_total
            )

    @api.onchange('tenancy_property_id')
    def onchange_tenancy(self):
        for rec in self:
            rec.tenancy_parent_property_id = rec.tenancy_property_id.parent_property_id.id

    @api.model
    def get_parent_property_account_move(self):
        records = self.env['account.move'].search(
            [('move_type', '=', 'out_invoice'),
             ('tenancy_parent_property_id', '=', False),
             ('tenancy_property_id', '!=', False)])
        for rec in records:
            temporary_id = rec.tenancy_property_id.id
            rec.write({
                'tenancy_property_id': False,
            })
            rec.write({
                'tenancy_property_id': temporary_id,
            })

    @api.model
    def add_property_and_parent_property(self):
        records = self.env['account.move'].search(
            [('tenancy_id', '!=', False)])
        for rec in records:
            rec.tenancy_property_id = rec.tenancy_id.property_id
            rec.tenancy_parent_property_id = rec.tenancy_id.property_id.parent_property_id

    @api.model
    def add_properties_and_dates_to_journal_entries(self):
        records = self.env['account.move'].sudo().search(
            [('move_type', '=', 'entry'), ('tenancy_property_id', '=', False)])
        for rec in records:
            invoice_record = self.env['account.move'].sudo().search(
                [('payment_reference', '=', rec.ref)], limit=1)
            if invoice_record:
                rec.write({
                    'tenancy_property_id': invoice_record.tenancy_property_id.id,
                    'tenancy_parent_property_id': invoice_record.tenancy_parent_property_id.id,
                    'invoice_period_to_date': invoice_record.invoice_period_to_date,
                    'invoice_period_from_date': invoice_record.invoice_period_from_date,
                })
            bill_record = self.env['utility.bill'].sudo().search(
                [('dn_no', '=', rec.ref)], limit=1)
            if bill_record:
                rec.write({
                    'tenancy_property_id': bill_record.property_id.id,
                    'tenancy_parent_property_id': bill_record.main_property_id.id,
                })
