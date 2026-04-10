# -*- coding: utf-8 -*-
# Copyright 2020-Today TechKhedut.
# Part of TechKhedut. See LICENSE file for full copyright and licensing details.
import re

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class Company(models.Model):
    _inherit = 'res.company'

    is_show_all_customer = fields.Boolean(string="Show all Customer")
    is_maintenance_company = fields.Boolean(string="Is Maintanance Company")

    agreement_expiring_in_forty_five_days = fields.Many2many(
        "res.partner",
        string="Agreement Expiring in 45 Days List")
    agreement_expiring_in_ninty_days_ids = fields.Many2many(
        'res.partner',
        'ninty_days_expiry_reminder',
        'ninty_days_reminder',
        'ninty_days_alert',
        string="Agreement Expiring in 90 Days"
    )
    payment_reminder_after_seven_days_ids = fields.Many2many(
        'res.partner',
        'payment_reminder_due',
        'payment_due_reminder_after',
        'seven_days',
        string="Payment Due Reminder after 7 Days"
    )
    upcoming_installment_before_fifteen_days_ids = fields.Many2many(
        'res.partner',
        'upcoming_installment_payment',
        'upcoming_installment_before',
        'fifteen_days',
        string='Upcoming Installment Payment in 15 Days'
    )

    @api.model_create_multi
    def create(self, vals_list):
        res = super(Company, self).create(vals_list)
        for vals in vals_list:
            if vals.get('partner_id'):
                partner_id = self.env['res.partner'].browse(
                    vals.get('partner_id'))
                res.partner_id.update({'company_id': res.id})
            return res


class UserTypes(models.Model):
    _inherit = 'res.partner'

    user_type = fields.Selection([('landlord', 'Landlord'),
                                  ('customer', 'Customer')],
                                 string='User Type')
    properties_count = fields.Integer(string='Properties Count',
                                      compute='_compute_properties_count')
    properties_ids = fields.One2many('property.details', 'landlord_id',
                                     string='Properties')
    brokerage_company_id = fields.Many2one('res.company',
                                           string=' Brokerage Company',
                                           default=lambda
                                               self: self.env.company)
    currency_id = fields.Many2one('res.currency',
                                  related='brokerage_company_id.currency_id',
                                  string='Currency')
    property_id = fields.Many2one('property.details', string="Property")

    # Customer Fields
    is_tenancy = fields.Boolean(string='Tenancy')
    is_sold_customer = fields.Boolean(string='Property Buyer')

    # Broker Fields
    tenancy_ids = fields.One2many('tenancy.details', 'broker_id',
                                  string='Tenancy ')
    property_sold_ids = fields.One2many('property.vendor', 'broker_id',
                                        string="Sold Commission")
    maintanance_company_id = fields.Many2one('res.company')

    company_id = fields.Many2one('res.company', string='Company')
    vrn_no = fields.Char(string="VRN No.")

    is_customer = fields.Boolean(string="Is Customer")
    is_landlord = fields.Boolean(string="Is Landlord")

    is_maintenance_team = fields.Boolean(string='Maintenance Team')

    access_card_no = fields.Char()
    barrier_card_no = fields.Char()
    parking_no = fields.Char()
    dada_name = fields.Char()
    dada_nida_no = fields.Char()
    vehicle_registration_no = fields.Char()

    # Contract Count
    contracts_count = fields.Integer(compute="_compute_contract_count")

    def _compute_contract_count(self):
        for rec in self:
            rec.contracts_count = self.env[
                'tenancy.details'].sudo().search_count(
                [('tenancy_id', '=', rec.id)])

    @api.depends('complete_name', 'email', 'vat', 'state_id', 'country_id',
                 'commercial_company_name')
    @api.depends_context('show_address', 'partner_show_db_id', 'address_inline', 'show_email',
                         'show_vat', 'lang')
    def _compute_display_name(self):
        for partner in self:
            name = partner.with_context({'lang': self.env.lang})._get_complete_name()
            if partner._context.get('show_address'):
                name = name + "\n" + partner._display_address(without_company=True)
            name = re.sub(r'\s+\n', '\n', name)
            if partner._context.get('partner_show_db_id'):
                name = f"{name} ({partner.id})"
            if partner._context.get('address_inline'):
                splitted_names = name.split("\n")
                name = ", ".join([n for n in splitted_names if n.strip()])
            if partner._context.get('show_email') and partner.email:
                name = f"{name} <{partner.email}>"
            if partner._context.get('show_vat') and partner.vat:
                name = f"{name}"

            partner.display_name = name.strip()

    def unlink(self):
        for rec in self:
            contracts = self.env['tenancy.details'].search([])
            for data in contracts:
                if rec.id == data.tenancy_id.id:
                    raise ValidationError(
                        _('You can not delete this record because it is linked with a contract'))
            properties = self.env['property.details'].search([])
            for data in properties:
                if rec.id == data.landlord_id.id:
                    raise ValidationError(
                        _('You can not delete this record because it is linked with a property'))
            main_properties = self.env['parent.property'].search([])
            for data in main_properties:
                if rec.id == data.landlord_id.id:
                    raise ValidationError(
                        _('You can not delete this record because it is linked with a main property'))
            handover_properties = self.env['handover.property'].search([])
            for data in handover_properties:
                if rec.id == data.tenant_id.id:
                    raise ValidationError(
                        _('You can not delete this record because it is linked with a handover property record'))
            utility_bills = self.env['utility.bill'].search([])
            for data in utility_bills:
                if rec.id == data.tenant_name.id:
                    raise ValidationError(
                        _('You can not delete this record because it is linked with a utility bill'))
            rent_invoices = self.env['rent.invoice'].search([])
            for data in rent_invoices:
                if rec.id == data.customer_id.id:
                    raise ValidationError(
                        _('You can not delete this record because it is linked with a rent invoice'))
        return super(UserTypes, self).unlink()

    @api.model
    def compute_customer_or_landlord(self):
        records = self.env['res.partner'].search([('user_type', '!=', False)])
        for rec in records:
            if rec.user_type == 'landlord':
                rec.is_landlord = True
            elif rec.user_type == 'customer':
                rec.is_customer = True

    @api.depends('properties_ids')
    def _compute_properties_count(self):
        for rec in self:
            count = self.env['property.details'].search_count(
                [('landlord_id', '=', rec.id)])
            rec.properties_count = count

    def action_properties(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Properties'),
            'res_model': 'property.details',
            'domain': [('landlord_id', '=', self.id)],
            'context': {'default_landlord_id': self.id},
            'view_mode': 'list,form',
            'target': 'current'
        }

    def action_view_contracts(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Contracts'),
            'res_model': 'tenancy.details',
            'domain': [('tenancy_id', '=', self.id)],
            'context': {'create': False},
            'view_mode': 'kanban,list,form',
            'target': 'current'
        }
