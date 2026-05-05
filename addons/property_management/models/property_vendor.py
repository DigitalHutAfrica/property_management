# -*- coding: utf-8 -*-
# Property Sales & Bookings — tracks when a property is sold/booked to a customer
# This model is referenced by property.py, rent_invoice, and multiple wizards
# Do not remove without refactoring all dependencies
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class PropertyVendor(models.Model):
    _name = 'property.vendor'
    _description = 'Property Sale / Booking Record'
    _rec_name = 'sold_seq'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    sold_seq = fields.Char(string='Reference', required=True, readonly=True,
                           copy=False, default='New')
    stage = fields.Selection([
        ('booked', 'Booked'),
        ('sold', 'Sold'),
    ], string='Stage', default='booked', tracking=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    date = fields.Date(string='Date', default=fields.Date.today)
    sold_document = fields.Binary(string='Document')
    file_name = fields.Char('File Name')
    term_condition = fields.Html(string='Terms & Conditions')
    property_id = fields.Many2one('property.details', string='Property')
    landlord_id = fields.Many2one(related='property_id.landlord_id', store=True)
    customer_id = fields.Many2one('res.partner', string='Customer')
    sale_price = fields.Monetary(string='Sale Price')
    is_any_broker = fields.Boolean(string='Broker Involved')
    broker_id = fields.Many2one('res.partner', string='Broker')
    broker_commission = fields.Monetary(string='Broker Commission')
    commission_type = fields.Selection([('f', 'Fixed'), ('p', 'Percentage')])
    broker_commission_percentage = fields.Float(string='Commission %')
    commission_from = fields.Selection([
        ('customer', 'Customer'), ('landlord', 'Landlord')
    ], string='Commission From')
    broker_bill_id = fields.Many2one('account.move', string='Broker Bill', readonly=True)
    broker_bill_payment_state = fields.Selection(
        related='broker_bill_id.payment_state', string='Payment Status')
    notes = fields.Text(string='Notes')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('sold_seq', 'New') == 'New':
                vals['sold_seq'] = self.env['ir.sequence'].next_by_code(
                    'property.vendor') or 'New'
        return super().create(vals_list)

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"{rec.sold_seq} - {rec.customer_id.name or ''}"


class SaleInvoice(models.Model):
    _name = 'sale.invoice'
    _description = 'Sale Invoice'

    property_vendor_id = fields.Many2one('property.vendor', string='Sale Record')
    invoice_id = fields.Many2one('account.move', string='Invoice')
    amount = fields.Monetary(string='Amount', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency',
                                  default=lambda self: self.env.company.currency_id)
    date = fields.Date(string='Date', default=fields.Date.today)
    state = fields.Selection([('draft', 'Draft'), ('paid', 'Paid')], default='draft')
