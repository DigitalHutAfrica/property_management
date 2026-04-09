# -*- coding: utf-8 -*-
# Copyright 2020-Today TechKhedut.
# Part of TechKhedut. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _


class PropertyMaintenance(models.Model):
    _inherit = 'maintenance.request'

    property_id = fields.Many2one('property.details', string='Property')
    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency',
                                  related='company_id.currency_id',
                                  string='Currency')
    landlord_id = fields.Many2one('res.partner', string='Landlord',
                                  domain=[('is_landlord', '=', True)])
    maintenance_type_id = fields.Many2one('product.template', string='Type',
                                          domain=[
                                              ('is_maintenance', '=', True)])
    price = fields.Float(related='maintenance_type_id.list_price',
                         string='Price')
    invoice_id = fields.Many2one('account.move', string='Invoice')
    invoice_state = fields.Boolean(string='State')
    contract_id = fields.Many2one('tenancy.details', string='Contract',
                                  domain="[('property_id', '=', property_id)]")
    tenant_id = fields.Many2one('res.partner', string='Tenant',
                                domain="[('is_customer', '=', True)]")

    attachment_ids = fields.One2many('maintenance.photos',
                                     'maintenance_request_id', string='Images')
    parent_property_id = fields.Many2one('parent.property', 'Parent Property')
    request_description = fields.Text('Description ')

    @api.model_create_multi
    def create(self, vals_list):
        res = super(PropertyMaintenance, self).create(vals_list)
        for rec in res:
            if rec.property_id and not rec.user_id:
                maintenance_incharge_id = rec.property_id.parent_property_id.maintenance_incharge_id.id
                responsible_id = self.env['res.users'].sudo().search(
                    [('partner_id', '=', maintenance_incharge_id)],
                    limit=1).id
                rec.user_id = responsible_id
        return res

    @api.onchange('contract_id')
    def _onchange_contract(self):
        self.tenant_id = self.contract_id.tenancy_id.id

    @api.onchange('property_id')
    def _onchange_property(self):
        self.landlord_id = self.property_id.landlord_id.id
        self.parent_property_id = self.property_id.parent_property_id.id
        maintenance_incharge_id = self.property_id.parent_property_id.maintenance_incharge_id.id
        if maintenance_incharge_id:
            responsible_id = self.env['res.users'].sudo().search(
                [('partner_id', '=', maintenance_incharge_id)],
                limit=1).id
            self.user_id = responsible_id
        else:
            self.user_id = False

    def action_send_notification_mail(self, id):
        mail_template = self.env.ref(
            'rental_management.maintenance_request_notification_mail_template').sudo()
        if mail_template:
            mail_template.send_mail(id, force_send=True)

    def action_crete_invoice(self):
        full_payment_record = {
            'product_id': self.maintenance_type_id.product_variant_id.id,
            'name': 'Maintenance',
            'quantity': 1,
            'price_unit': self.price
        }
        invoice_lines = [(0, 0, full_payment_record)]
        data = {
            'partner_id': self.landlord_id.id,
            'move_type': 'out_invoice',
            'invoice_date': fields.Date.today(),
            'invoice_line_ids': invoice_lines
        }
        invoice_id = self.env['account.move'].sudo().create(data)
        invoice_id.action_post()
        self.invoice_id = invoice_id.id
        self.invoice_state = True

        return {
            'type': 'ir.actions.act_window',
            'name': 'Invoice',
            'res_model': 'account.move',
            'res_id': invoice_id.id,
            'view_mode': 'form',
            'target': 'current'
        }


class MaintenancePhotos(models.Model):
    _name = 'maintenance.photos'
    _description = 'Photos For Maintenance Request'
    _order = 'id desc'

    image = fields.Binary(string='Image')
    maintenance_request_id = fields.Many2one('maintenance.request')


class MaintenanceProduct(models.Model):
    _inherit = 'product.template'

    is_maintenance = fields.Boolean(string='Maintenance')
    property_id = fields.Many2one('property.details', string="Property")
