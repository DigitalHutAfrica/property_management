# -*- coding: utf-8 -*-
# Copyright 2020-Today TechKhedut.
# Part of TechKhedut. See LICENSE file for full copyright and licensing details.
import datetime
from dateutil.relativedelta import relativedelta
from odoo import fields, api, models


class PropertyVendor(models.Model):
    _name = 'property.vendor'
    _description = 'Stored Data About Sold Property'
    _rec_name = 'sold_seq'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    sold_seq = fields.Char(string='Sequence', required=True, readonly=True, copy=False, default=lambda self: ('New'))
    stage = fields.Selection([('booked', 'Booked'),
                              ('refund', 'Refund'),
                              ('sold', 'Sold')], string='Stage')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', string='Currency')
    date = fields.Date(string='Create Date', default=fields.Date.today())
    sold_document = fields.Binary(string='Sold Document')
    file_name = fields.Char('File Name')
    term_condition = fields.Html(string='Term and Condition')

    # Broker and Customer
    customer_id = fields.Many2one('res.partner', string='Customer', domain=[('is_customer', '=', True)])
    is_any_broker = fields.Boolean(string='Any Broker')
    broker_id = fields.Many2one('res.partner', string='Broker')
    broker_final_commission = fields.Monetary(string='Commission', compute="_compute_broker_final_commission")
    broker_commission = fields.Monetary(string='Commission ')
    commission_type = fields.Selection([('f', 'Fix'), ('p', 'Percentage')], string="Commission Type")
    broker_commission_percentage = fields.Float(string='Percentage')
    commission_from = fields.Selection([('customer', 'Customer'), ('landlord', 'Landlord',)], string="Commission From")
    broker_bill_id = fields.Many2one('account.move', string='Broker Bill', readonly=True)
    broker_bill_payment_state = fields.Selection(related='broker_bill_id.payment_state', string="Payment Status ")

    # Property Information
    property_id = fields.Many2one('property.details', string='Property', domain=[('stage', '=', 'sale')])
    landlord_id = fields.Many2one(related="property_id.landlord_id", store=True)
    book_price = fields.Monetary(related='property_id.token_amount', string='Book Price')
    sale_price = fields.Monetary(string='Sale Price', store=True)
    ask_price = fields.Monetary(string='Ask Price')
    book_invoice_id = fields.Many2one('account.move', string='Advance', readonly=True)
    book_invoice_payment_state = fields.Selection(related='book_invoice_id.payment_state', string="Payment Status")
    book_invoice_state = fields.Boolean(string='Invoice State')
    sold_invoice_id = fields.Many2one('account.move', string='Sold Invoice', readonly=True)
    sold_invoice_state = fields.Boolean(string='Sold Invoice State')
    sold_invoice_payment_state = fields.Selection(related='sold_invoice_id.payment_state', string="Payment Status  ")
    sale_invoice_ids = fields.One2many('sale.invoice', 'property_sold_id', string="Invoices")
    payment_term = fields.Selection([('monthly', 'Monthly'),
                                     ('full_payment', 'Full Payment'), ('quarterly', 'Quarterly')],
                                    string='Payment Term')

    # Remaining Payment
    remain_invoice_id = fields.Many2one('account.move', string="Invoice")
    total_amount = fields.Monetary(string="Total Amount", compute="_compute_remain_amount")
    remaining_amount = fields.Monetary(string="Remaining Amount", compute="_compute_remain_amount")
    paid_amount = fields.Monetary(string="Paid", compute="_compute_remain_amount")
    remain_check = fields.Boolean(compute="_compute_remain_check")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('sold_seq', ('New')) == ('New'):
                vals['sold_seq'] = self.env['ir.sequence'].next_by_code(
                    'property.vendor') or ('New')
        res = super(PropertyVendor, self).create(vals_list)
        return res

    @api.depends('sale_invoice_ids')
    def _compute_remain_amount(self):
        for rec in self:
            total_amount = 0.0
            paid_amount = 0.0
            if rec.sale_invoice_ids:
                for data in rec.sale_invoice_ids:
                    total_amount = total_amount + data.amount
                    if data.invoice_created and data.payment_state == "paid":
                        paid_amount = paid_amount + data.amount
            rec.total_amount = total_amount
            rec.paid_amount = paid_amount
            rec.remaining_amount = total_amount - paid_amount

    @api.depends('sale_invoice_ids')
    def _compute_remain_check(self):
        for rec in self:
            if rec.sale_invoice_ids:
                for data in rec.sale_invoice_ids:
                    if data.is_remain_invoice:
                        rec.remain_check = True
                    else:
                        rec.remain_check = False
            else:
                rec.remain_check = False

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s - %s' % (rec.sold_seq, rec.customer_id.name)

    def send_sold_mail(self):
        mail_template = self.env.ref('rental_management.property_sold_mail_template')
        if mail_template:
            mail_template.send_mail(self.id, force_send=True)

    def action_book_invoice(self):
        mail_template = self.env.ref('rental_management.property_book_mail_template')
        if mail_template:
            mail_template.send_mail(self.id, force_send=True)
        record = {
            'product_id': self.env.ref('rental_management.property_product_1').id,
            'name': 'Booked Amount of   ' + self.property_id.name,
            'quantity': 1,
            'price_unit': self.book_price
        }
        invoice_lines = [(0, 0, record)]
        data = {
            'partner_id': self.customer_id.id,
            'move_type': 'out_invoice',
            'invoice_date': fields.Date.today(),
            'invoice_line_ids': invoice_lines
        }
        book_invoice_id = self.env['account.move'].sudo().create(data)
        book_invoice_id.sold_id = self.id
        book_invoice_id.action_post()
        self.book_invoice_id = book_invoice_id.id
        self.book_invoice_state = True
        self.property_id.stage = 'booked'
        self.stage = 'booked'
        return {
            'type': 'ir.actions.act_window',
            'name': 'Booked Invoice',
            'res_model': 'account.move',
            'res_id': book_invoice_id.id,
            'view_mode': 'form,list',
            'target': 'current'
        }

    @api.depends('is_any_broker', 'broker_id', 'commission_type', 'sale_price')
    def _compute_broker_final_commission(self):
        for rec in self:
            if rec.is_any_broker:
                if rec.commission_type == 'p':
                    rec.broker_final_commission = rec.sale_price * rec.broker_commission_percentage / 100
                else:
                    rec.broker_final_commission = rec.broker_commission
            else:
                rec.broker_final_commission = 0.0

    def action_refund_amount(self):
        for rec in self:
            if rec.book_invoice_payment_state == "reversed" or rec.book_invoice_payment_state == "not_paid":
                rec.stage = 'refund'
                rec.property_id.stage = "available"
                rec.property_id.sold_booking_id = None
            else:
                message = {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'type': 'info',
                        'title': ('Not Refunded !'),
                        'message': 'Please Refund advance amount payment',
                        'sticky': True,
                    }
                }
                return message

    @api.model
    def sale_recurring_invoice(self):
        reminder_days = self.env['ir.config_parameter'].sudo().get_param('rental_management.sale_reminder_days')
        today_date = fields.Date.today()
        # today_date = datetime.date(2023, 7, 29)
        sale_invoice = self.env['sale.invoice'].sudo().search([('invoice_created', '=', False)])
        for data in sale_invoice:
            reminder_date = data.invoice_date - relativedelta(days=int(reminder_days))
            if today_date == reminder_date:
                record = {
                    'product_id': self.env.ref('rental_management.property_product_1').id,
                    'name': data.name,
                    'quantity': 1,
                    'price_unit': data.amount
                }
                invoice_lines = [(0, 0, record)]
                sold_data = {
                    'partner_id': data.property_sold_id.customer_id.id,
                    'move_type': 'out_invoice',
                    'sold_id': data.property_sold_id.id,
                    'invoice_date': data.invoice_date,
                    'invoice_line_ids': invoice_lines
                }
                invoice_id = self.env['account.move'].sudo().create(sold_data)
                invoice_id.action_post()
                data.invoice_id = invoice_id.id
                data.invoice_created = True

    def action_receive_remaining(self):
        amount = 0.0
        for rec in self.sale_invoice_ids:
            if not rec.invoice_created:
                amount = amount + rec.amount

        sold_invoice_data = {
            'name': "Remaining Invoice Payment",
            'property_sold_id': self.id,
            'invoice_date': fields.Date.today(),
            'amount': amount,
            'is_remain_invoice': True
        }
        sale_invoice = self.env['sale.invoice'].create(sold_invoice_data)
        sale_invoice.action_create_invoice()
        for data in self.sale_invoice_ids:
            if not data.invoice_created and (not data.is_remain_invoice):
                data.unlink()


class SaleInvoice(models.Model):
    _name = 'sale.invoice'
    _description = "Sale Invoice"

    name = fields.Char(string="Title")
    property_sold_id = fields.Many2one('property.vendor', string="Property Sold", ondelete='cascade')
    invoice_id = fields.Many2one('account.move', string="Invoice")
    invoice_date = fields.Date(string="Date")
    payment_state = fields.Selection(related="invoice_id.payment_state")
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', string='Currency')
    amount = fields.Monetary(string="Amount")
    invoice_created = fields.Boolean()
    desc = fields.Text(string="Description")
    is_remain_invoice = fields.Boolean()

    def action_create_invoice(self):
        record = {
            'product_id': self.env.ref('rental_management.property_product_1').id,
            'name': self.name,
            'quantity': 1,
            'price_unit': self.amount
        }
        invoice_lines = [(0, 0, record)]
        data = {
            'partner_id': self.property_sold_id.customer_id.id,
            'move_type': 'out_invoice',
            'sold_id': self.property_sold_id.id,
            'invoice_date': self.invoice_date,
            'invoice_line_ids': invoice_lines
        }
        invoice_id = self.env['account.move'].sudo().create(data)
        invoice_id.action_post()
        self.invoice_id = invoice_id.id
        self.invoice_created = True
        self.action_send_sale_invoice(invoice_id.id)

    def action_send_sale_invoice(self, invoice_id):
        mail_template = self.env.ref('rental_management.sale_invoice_payment_mail_template')
        if mail_template:
            mail_template.send_mail(invoice_id, force_send=True)
