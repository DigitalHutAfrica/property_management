# -*- coding: utf-8 -*-
# Copyright 2020-Today TechKhedut.
# Part of TechKhedut. See LICENSE file for full copyright and licensing details.
from odoo import models, api, fields
from datetime import date, timedelta, datetime


class ExtendContract(models.TransientModel):
    _name = 'extend.contract.wizard'
    _description = 'Wizard for extend contract'

    tenancy_id = fields.Many2one('tenancy.details', string='Tenancy')
    customer_id = fields.Many2one(related='tenancy_id.tenancy_id', string='Customer')
    property_id = fields.Many2one(related='tenancy_id.property_id', string='Property')
    parent_property_id = fields.Many2one(related='property_id.parent_property_id', string='Parent Property')
    property_type = fields.Selection(related='tenancy_id.property_type', string='Property Type')
    duration_id = fields.Many2one('contract.duration', string='Payment Term')
    month = fields.Integer(related='duration_id.month', string='Month')
    start_date = fields.Date(string='Start Date', compute='_compute_date_one_day_after', store=True, readonly=False)
    end_date = fields.Date(string='End Date')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='tenancy_id.currency_id', string='Currency')
    revised_price = fields.Monetary(string='Revised Price')
    rented_area = fields.Float(string='Rented Area')
    square_area = fields.Selection(string="square Area", related="tenancy_id.square_area")
    is_any_broker = fields.Boolean(related='tenancy_id.is_any_broker', string='Broker ')
    new_broker_id = fields.Many2one(related='tenancy_id.broker_id', string='Broker', readonly=False)
    contract_type_name = fields.Selection(string='Contract Type', related='tenancy_id.contract_type_name')
    rent_type = fields.Selection(related='tenancy_id.rent')

    @api.model
    def default_get(self, fields_list):
        active_id = self._context.get('active_id')
        res = super(ExtendContract, self).default_get(fields_list)
        if active_id:
            contract_id = self.env['tenancy.details'].browse(active_id)
            res['tenancy_id'] = contract_id.id
            res['duration_id'] = contract_id.payment_term_id.id
            if contract_id.rent == 'per_square_meter':
                res['rented_area'] = contract_id.rented_area
        return res

    @api.depends('tenancy_id.end_date')
    def _compute_date_one_day_after(self):
        for record in self:
            contract_date = record.tenancy_id.end_date
            if contract_date:
                contract_date += timedelta(days=1)
                record.start_date = contract_date
            else:
                record.start_date = False

    @api.onchange('tenancy_id')
    def revised_price_relate(self):
        for rec in self:
            if rec.tenancy_id:
                rent = rec.tenancy_id.total_rent
                if rec.tenancy_id.contract_type_name == 'lease' and rec.tenancy_id.property_type == 'commercial':
                    rent = rec.tenancy_id.total_rent_month
                if rec.tenancy_id.contract_type_name == 'service' and rec.tenancy_id.property_type in ['commercial',
                                                                                                       'residential']:
                    rent = rec.tenancy_id.service_charge_month
                rec.revised_price = rent
            else:
                return True

    def extend_contract_action(self):
        self.customer_id.is_tenancy = True
        record = {
            'tenancy_id': self.customer_id.id,
            # 'contract_type_name': 'addendum',
            'contract_type_name': self.contract_type_name,
            'property_id': self.property_id.id,
            'parent_property_id': self.parent_property_id.id,
            'is_any_broker': self.is_any_broker,
            'broker_id': self.new_broker_id.id,
            'payment_term_id': self.duration_id.id,
            'start_date': self.start_date,
            # 'total_rent': self.revised_price,
            'is_extra_service': self.tenancy_id.is_extra_service,
            'contract_type': 'new_contract',
            'last_invoice_payment_date': fields.Date.today(),
            'active_contract_state': True,
            'is_extended': True,
            'rent': self.property_id.rent,
            'installment_item_id': self.tenancy_id.installment_item_id.id,
            'late_payment_interest': self.tenancy_id.late_payment_interest,
            'late_payment_interest_amt': self.tenancy_id.late_payment_interest_amt,
            'rent_incremnet_period': self.tenancy_id.rent_incremnet_period,
            'rent_time_period': self.tenancy_id.rent_time_period,
            'rent_incerement': self.tenancy_id.rent_incerement,
            'currency_id': self.tenancy_id.currency_id.id,
            'company_id': self.tenancy_id.company_id.id,
            'pro_company_id': self.tenancy_id.pro_company_id.id,
            'pro_management_company_id': self.tenancy_id.pro_management_company_id.id,
            'security_deposit_currency_id': self.tenancy_id.security_deposit_currency_id.id,
        }
        new_tenancy_id = self.env['tenancy.details'].create(record)
        new_tenancy_id.onchange_get_rent_increment_date()
        if self.rent_type == 'per_square_meter':
            new_tenancy_id.write({
                'rented_area': self.rented_area,
                'rent_smtr': self.revised_price,
            })
            new_tenancy_id.onchange_rent_calculation()
        if self.rent_type == 'fixed':
            if self.tenancy_id.contract_type_name == 'lease' and self.tenancy_id.property_type == 'commercial':
                new_tenancy_id.write({
                    'total_rent_month': self.revised_price
                })
            elif self.tenancy_id.contract_type_name == 'lease' and self.tenancy_id.property_type != 'commercial':
                new_tenancy_id.write({
                    'total_rent': self.revised_price
                })
            elif self.tenancy_id.contract_type_name == 'service' and self.tenancy_id.property_type in ['commercial',
                                                                                                       'residential']:
                new_tenancy_id.write({
                    'service_charge_month': self.revised_price
                })
            elif self.tenancy_id.contract_type_name == 'service' and self.tenancy_id.property_type not in ['commercial',
                                                                                                           'residential']:
                new_tenancy_id.write({
                    'total_rent': self.revised_price
                })
        new_tenancy_id.write({'end_date': self.end_date, 'payment_term_id': self.duration_id.id, 'is_addendum': True})
        for data in self.tenancy_id.rent_invoice_ids:
            if data.invoice_date >= self.start_date and not data.rent_invoice_id:
                data.unlink()
        if self.contract_type_name == 'lease':
            self.property_id.stage = 'on_lease'

        return {
            'type': 'ir.actions.act_window',
            'name': 'Create Contract',
            'res_model': 'tenancy.details',
            'res_id': new_tenancy_id.id,
            'view_mode': 'form,list',
            'target': 'current'
        }
