# -*- coding: utf-8 -*-
# Copyright 2020-Today TechKhedut.
# Part of TechKhedut. See LICENSE file for full copyright and licensing details.
from odoo import models, fields, api
from dateutil.relativedelta import relativedelta
from datetime import datetime


class PropertySold(models.TransientModel):
    _name = 'property.vendor.wizard'
    _description = 'Wizard For Selecting Customer to sale'

    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', string='Currency')
    property_id = fields.Many2one('property.details', string='Property')
    customer_id = fields.Many2one('property.vendor', string='Customer')
    final_price = fields.Monetary(string='Final Price')
    sold_invoice_id = fields.Many2one('account.move')
    broker_id = fields.Many2one(related='customer_id.broker_id')
    is_any_broker = fields.Boolean(related='customer_id.is_any_broker')
    quarter = fields.Integer(string="Quarter", default=4)

    # Payment Term
    duration_id = fields.Many2one('contract.duration', string='Duration')
    payment_term = fields.Selection([('monthly', 'Monthly'),
                                     ('full_payment', 'Full Payment'), ('quarterly', 'Quarterly')],
                                    string='Payment Term')
    start_date = fields.Date(string="Start From")

    @api.onchange('payment_term')
    def _onchange_payment_term(self):
        if self.payment_term == 'quarterly':
            return {'domain': {'duration_id': [('month', '>=', 3)]}}

    @api.onchange('customer_id')
    def drive_final_price(self):
        for rec in self:
            active_id = self._context.get('active_id')
            sale_id = self.env['property.vendor'].browse(active_id)
            if sale_id:
                rec.final_price = sale_id.ask_price

    def property_sale_action(self):
        active_id = self._context.get('active_id')
        sale_id = self.env['property.vendor'].browse(active_id)
        self.property_id = sale_id.property_id
        self.customer_id = sale_id.id

        if self.customer_id.is_any_broker:
            if self.customer_id.commission_type == 'p':
                broker_final_commission = self.final_price * self.customer_id.broker_commission_percentage / 100
            else:
                broker_final_commission = self.customer_id.broker_commission
            broker_name = 'Commission of %s' % self.customer_id.broker_id.name
            broker_record = {
                'product_id': self.env.ref('rental_management.property_product_1').id,
                'name': broker_name,
                'quantity': 1,
                'price_unit': broker_final_commission
            }
            invoice_lines = [(0, 0, broker_record)]
            data = {
                'partner_id': self.customer_id.customer_id.id,
                'move_type': 'in_invoice',
                'invoice_date': fields.Date.today(),
                'invoice_line_ids': invoice_lines
            }
            broker_bill_id = self.env['account.move'].sudo().create(data)
            self.customer_id.broker_bill_id = broker_bill_id.id

        self.customer_id.customer_id.is_sold_customer = True
        count = 0
        for rec in self:
            if rec.payment_term == "monthly":
                if rec.customer_id.is_any_broker and rec.customer_id.commission_from == 'customer':
                    if rec.customer_id.commission_type == 'p':
                        broker_final_commission = rec.final_price * rec.customer_id.broker_commission_percentage / 100
                    else:
                        broker_final_commission = rec.customer_id.broker_commission
                    sold_invoice_data = {
                        'name': "Broker Commission",
                        'property_sold_id': rec.customer_id.id,
                        'invoice_date': fields.Date.today(),
                        'amount': broker_final_commission
                    }
                    self.env['sale.invoice'].create(sold_invoice_data)
                amount = (rec.final_price - rec.customer_id.book_price) / rec.duration_id.month
                invoice_date = rec.start_date
                for r in range(rec.duration_id.month):
                    count = count + 1
                    sold_invoice_data = {
                        'name': str(count) + " Installment",
                        'property_sold_id': rec.customer_id.id,
                        'invoice_date': invoice_date,
                        'amount': amount
                    }
                    self.env['sale.invoice'].create(sold_invoice_data)
                    invoice_date = invoice_date + relativedelta(months=1)
            elif rec.payment_term == "quarterly":
                if rec.customer_id.is_any_broker and rec.customer_id.commission_from == 'customer':
                    if rec.customer_id.commission_type == 'p':
                        broker_final_commission = rec.final_price * rec.customer_id.broker_commission_percentage / 100
                    else:
                        broker_final_commission = rec.customer_id.broker_commission
                    sold_invoice_data = {
                        'name': "Broker Commission",
                        'property_sold_id': rec.customer_id.id,
                        'invoice_date': fields.Date.today(),
                        'amount': broker_final_commission
                    }
                    self.env['sale.invoice'].create(sold_invoice_data)
                if rec.quarter > 1:
                    amount = (rec.final_price - rec.customer_id.book_price) / rec.quarter
                    invoice_date = rec.start_date
                    for r in range(rec.quarter):
                        count = count + 1
                        sold_invoice_data = {
                            'name': str(count) + " Quarter Payment",
                            'property_sold_id': rec.customer_id.id,
                            'invoice_date': invoice_date,
                            'amount': amount
                        }
                        self.env['sale.invoice'].create(sold_invoice_data)
                        invoice_date = invoice_date + relativedelta(months=3)
            elif rec.payment_term == "full_payment":
                if rec.customer_id.is_any_broker and rec.customer_id.commission_from == 'customer':
                    if rec.customer_id.commission_type == 'p':
                        broker_final_commission = rec.final_price * rec.customer_id.broker_commission_percentage / 100
                    else:
                        broker_final_commission = rec.customer_id.broker_commission
                    sold_invoice_data = {
                        'name': "Broker Commission",
                        'property_sold_id': rec.customer_id.id,
                        'invoice_date': fields.Date.today(),
                        'amount': broker_final_commission
                    }
                    sale_invoice = self.env['sale.invoice'].create(sold_invoice_data)
                    sale_invoice.action_create_invoice()
                amount = rec.final_price - rec.customer_id.book_price
                sold_invoice_data = {
                    'name': "Full Payment",
                    'property_sold_id': self.customer_id.id,
                    'invoice_date': fields.Date.today(),
                    'amount': amount,
                    'is_remain_invoice': True
                }
                sale_full_invoice = self.env['sale.invoice'].create(sold_invoice_data)
                sale_full_invoice.action_create_invoice()
        self.customer_id.property_id.stage = "sold"
        self.customer_id.stage = "sold"
        self.customer_id.sale_price = self.final_price
        self.customer_id.payment_term = self.payment_term
        self.customer_id.send_sold_mail()
