# -*- coding: utf-8 -*-
# Copyright 2020-Today TechKhedut.
# Part of TechKhedut. See LICENSE file for full copyright and licensing details.
import datetime
from dateutil.relativedelta import relativedelta
import calendar
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

from num2words import num2words



class UtilityBill(models.Model):
    _name = 'utility.bill'
    _description = 'Utility Bills'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = "bill_seq"

    bill_seq = fields.Char(string='Sequence', required=True, readonly=True,
                           copy=False,
                           default=lambda self: 'New')
    name = fields.Char(string="Name")
    contract_id = fields.Many2one('tenancy.details', string="Contract")
    property_id = fields.Many2one('property.details', string="Property")
    main_property_id = fields.Many2one('parent.property',
                                       string="Main Property",
                                       related="property_id.parent_property_id",
                                       store=True)
    tenant_name = fields.Many2one('res.partner', string="Tenant")

    # Address
    zip = fields.Char(string='Pin Code', size=6, related="tenant_name.zip")
    street = fields.Char(string='Street1', related="tenant_name.street",
                         store=True)
    street2 = fields.Char(string='Street2', related="tenant_name.street2")
    city = fields.Char(string='City', related="tenant_name.city")
    city_id = fields.Many2one('property.res.city', string='City ',
                              related="contract_id.property_id.parent_city_id")
    country_id = fields.Many2one('res.country', 'Country',
                                 related="tenant_name.country_id")
    state_id = fields.Many2one(
        "res.country.state", string='State', readonly=False, store=True,
        domain="[('country_id', '=?', country_id)]",
        related="tenant_name.state_id")
    tin = fields.Char(string="Tax ID ", related="tenant_name.vat")
    vrn = fields.Char(string="TVRN", related="tenant_name.vrn_no")

    tin_vrn = fields.Char(string="Tax ID & VRN", compute="_compute_tin_vrn",
                          readonly=False)
    dn_no = fields.Char(string="Debit Note No.")
    date = fields.Date(string='Date')
    month = fields.Char(string="Month")
    utility_meter_ids = fields.One2many('utility.meter.reading', 'utility_id',
                                        string="Utility Meter Reading")

    meter_type = fields.Many2one('meter.type')
    meter_type_line_id = fields.Many2one('meter.type.lines')
    currency_id = fields.Many2one('res.currency',
                                  related="meter_type_line_id.currency_id",
                                  string="Currency")
    total_amount = fields.Monetary(string='Total Amount',
                                   compute="_amount_total_meter_line",
                                   store=True)
    total_amount_word = fields.Char(string='Total Amount In Word',
                                    compute="compute_total_amount_word",
                                    store=True)
    payment_id = fields.Many2one('account.payment', string="Payment Ref")
    barcode = fields.Binary(string="Barcode")

    company_id = fields.Many2one(
        'res.company', string='Company', default=lambda self: self.env.company)

    lipa_number = fields.Char(related="property_id.lipa_number")
    debit_journal_entry_id = fields.Many2one('account.move')

    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('posted', 'Posted'),
        ],
        string='Status',
        required=True,
        readonly=True,
        copy=False,
        tracking=True,
        default='draft',
    )

    r_payment_state = fields.Selection(
        [('Unpaid', 'Unpaid'), ('Paid', 'Paid')], string="Payment Status",
        compute='_compute_payment_state', search="_filter_paid_unpaid")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('bill_seq', 'New') == 'New':
                vals['bill_seq'] = self.env['ir.sequence'].next_by_code(
                    'utility.bill') or 'New'

                vals['dn_no'] = vals['bill_seq']

        return super(UtilityBill, self).create(vals_list)

    def unlink(self):
        for rec in self:
            if rec.state in ['confirm', 'posted']:
                raise ValidationError(
                    _("You are not allowed to delete records that are in posted state."))
        return super(UtilityBill, self).unlink()

    def print_utility_bill_report(self):
        return self.env.ref(
            'rental_management.action_utility_bill_report').report_action(self)

    def reset_to_draft(self):
        for rec in self:
            if rec.r_payment_state != 'Paid':
                if (rec.debit_journal_entry_id and
                        rec.debit_journal_entry_id.state == 'posted'):
                    raise UserError(
                        _('You are not allowed to reset to draft because '
                          'journal entry is posted'))
                if (rec.debit_journal_entry_id and
                        rec.debit_journal_entry_id.state != 'posted'):
                    rec.debit_journal_entry_id.sudo().unlink()
                rec.state = 'draft'
                rec.r_payment_state = False

    def action_post_bill(self):
        for rec in self:
            rec.state = 'posted'
            rec.r_payment_state = 'Unpaid'

    def get_whatsapp_template(self, template_id):
        """Get Template from Settings"""
        wa_template_id = False
        config_template_id = self.env['ir.config_parameter'].sudo().get_param(template_id)
        if config_template_id:
            wa_template_id = self.env['whatsapp.template'].sudo().browse(int(config_template_id))
        return wa_template_id

    def _get_html_preview_whatsapp(self, wa_template_id, rec):
        """This method is used to get the html preview of the whatsapp message."""
        self.ensure_one()

        # Prepare Body
        template_variables_value = wa_template_id.variable_ids._get_variables_value(rec)

        return wa_template_id._get_formatted_body(variable_values=template_variables_value)

    def action_send_whatsapp_message(self, phone, wa_template_id, record):
        """Send Whatsapp Message"""
        body = self._get_html_preview_whatsapp(wa_template_id, record)
        post_values = {'body': body,
                       'message_type': 'whatsapp_message',
                       'partner_ids': [self.env.user.partner_id.id], }
        message = self.env['mail.message'].create(
            dict(post_values, res_id=record.id, model=wa_template_id.model,
                 subtype_id=self.env['ir.model.data']._xmlid_to_res_id(
                     "mail.mt_note")))
        message = self.env['whatsapp.message'].sudo().create({
            'mobile_number': phone,
            'wa_template_id': wa_template_id.id,
            'wa_account_id': wa_template_id.wa_account_id.id,
            'mail_message_id': message.id,
        })
        message._send(force_send_by_cron=True)

    def confirm_uility(self):
        for rec in self:
            bill_mail_template = self.env.ref("rental_management.utility_bill_mail_template")
            bill_wh_template = self.get_whatsapp_template(
                'rental_management.utility_bill_whatsapp_template_id')
            if rec.state == 'draft':
                rec.state = 'posted'
                rec.r_payment_state = 'Unpaid'
                if bill_mail_template:
                    if self.env.user.email:
                        bill_mail_template.send_mail(rec.id, force_send=True,
                                                     email_values={
                                                         'email_from': self.env.user.email
                                                     })
                    else:
                        bill_mail_template.send_mail(rec.id, force_send=True)
                if bill_wh_template:
                    rec.action_send_whatsapp_message(phone=rec.tenant_name.mobile,
                                                     wa_template_id=bill_wh_template,
                                                     record=rec)

    @api.depends('payment_id', 'state')
    def _compute_payment_state(self):
        for rec in self:
            payment_status = False
            if rec.state == 'posted' and rec.payment_id.amount >= rec.total_amount:
                payment_status = 'Paid'
            if rec.state == 'posted' and not rec.payment_id or rec.payment_id.amount < rec.total_amount:
                payment_status = 'Unpaid'
            if rec.state == 'draft':
                payment_status = False
            rec.r_payment_state = payment_status

    @api.depends('total_amount')
    def compute_total_amount_word(self):
        for record in self:
            record.write(
                {'total_amount_word': num2words(int(record.total_amount))})

    def _compute_tin_vrn(self):
        for record in self:
            tin_vrn = ''
            if record.tenant_name.vat and record.tenant_name.vrn_no:
                tin_vrn = record.tenant_name.vat + ', ' + record.tenant_name.vrn_no
            if record.tenant_name.vat and not record.tenant_name.vrn_no:
                tin_vrn = record.tenant_name.vat
            if not record.tenant_name.vat and record.tenant_name.vrn_no:
                tin_vrn = record.tenant_name.vrn_no

            record.write({'tin_vrn': tin_vrn})

    def _filter_paid_unpaid(self, operator, value):
        bills = []
        bill_ids = self.env['utility.bill'].search([])
        for rec in bill_ids:
            if operator == '=' and rec.r_payment_state == value:
                bills.append(rec.id)
            if operator == 'in' and rec.r_payment_state in value:
                bills.append(rec.id)
        return [('id', 'in', bills)]

    @api.onchange('date')
    def onchange_date(self):
        for rec in self:
            if rec.date:
                month = '%s-%s' % (
                    calendar.month_name[rec.date.month],
                    str(rec.date.year)[-2:])
                rec.month = month

    @api.depends('utility_meter_ids')
    def _amount_total_meter_line(self):
        for rec in self:
            if rec.utility_meter_ids:
                total = sum(rec.utility_meter_ids.mapped('amount'))
                rec.total_amount = total
                rec.meter_type_line_id = rec.utility_meter_ids[
                    0].meter_type_line_id.id

    def action_register_payment(self):
        ''' Open the account.payment.register wizard to pay the selected journal entries.
        :return: An action opening the account.payment.register wizard.
        '''
        for rec in self:
            if rec.r_payment_state == 'Paid':
                raise ValidationError(_("Selected Bill is already paid"))

            if rec.state != 'posted':
                raise ValidationError(
                    _("You have to confirm the utility bill before registering payment for it."))

        ctx = {
            'active_model': 'utility.bill',
            'active_ids': self.ids,
            # 'default_utility_id': self.id
        }
        return {
            'name': _('Register Payment'),
            'res_model': 'utility.bill.register',
            'view_mode': 'form',
            'context': ctx,
            'target': 'new',
            'type': 'ir.actions.act_window',
        }

    def action_send_and_print(self):
        template = self.env.ref("rental_management.utility_bill_mail_template")
        ctx = {
            'default_template_id': template.id,
            'active_id': self.ids[0],
            'active_ids': self.ids,
            'active_model': 'utility.bill',
        }
        return {
            'name': _('Send Bills'),
            'res_model': 'utility.bill.send',
            'view_mode': 'form',
            'context': ctx,
            'target': 'new',
            'type': 'ir.actions.act_window',
        }


class UtilityMeterReading(models.Model):
    _name = 'utility.meter.reading'
    _description = 'Utility Meter Reading'

    utility_id = fields.Many2one('utility.bill', string="Utility Id")
    main_property_id = fields.Many2one(related="utility_id.main_property_id")
    utility_rate_ids = fields.One2many(
        related="main_property_id.utility_rate_ids")
    sr_no = fields.Integer(string="Sr.No", compute="_compute_sr_no")
    meter_type_id = fields.Many2one('meter.type', string="Description ")
    meter_type_line_id = fields.Many2one('meter.type.lines',
                                         string="Description",
                                         domain="[('id','in',utility_rate_ids)]")
    curr_reading_date = fields.Date(string="Current Reading Date",
                                    default=fields.Date.today)
    curr_reading = fields.Float(string="Current Reading")
    pre_reading_date = fields.Date(string="Previous Reading Date")
    pre_reading = fields.Float(string="Previous Reading")
    total_consume = fields.Float(string="Total Consume")
    rate = fields.Monetary(string='Rate', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency',
                                  related="meter_type_line_id.currency_id",
                                  string="Currency")
    amount = fields.Monetary(string='Amount', currency_field='currency_id')

    @api.onchange('meter_type_line_id')
    def onchange_meter_type_line(self):
        for rec in self:
            if rec.meter_type_line_id:
                rec.rate = rec.meter_type_line_id.rate

    @api.onchange('meter_type_id')
    def _onchange_meter_type_id(self):
        for rec in self:
            if rec.utility_id.contract_id:
                utility_id = self.env['utility.bill'].search_count(
                    [('contract_id', '=', rec.utility_id.contract_id.id)])
                if utility_id == 0:
                    handover_id = self.env['handover.property'].search(
                        [('contract_id', '=', rec.utility_id.contract_id.id)])
                    if handover_id:
                        rec.write({'pre_reading_date': handover_id.date,
                                   'rate': rec.meter_type_line_id.rate,
                                   'currency_id': rec.meter_type_id.currency_id.id})
                        if rec.meter_type_line_id.meter_type_id.name == 'Electrical':
                            rec.write(
                                {'pre_reading': handover_id.electric_reading})
                        if rec.meter_type_line_id.meter_type_id.name == 'Generator':
                            rec.write(
                                {'pre_reading': handover_id.generator_reading})
                        total_consume = rec.curr_reading - rec.pre_reading
                        rec.write({'total_consume': total_consume})
                        amount = rec.total_consume * rec.rate
                        rec.write({'amount': amount})


                else:
                    record_ids = self.env['utility.bill'].search(
                        [('contract_id', '=', rec.utility_id.contract_id.id)],
                        order='id desc', limit=2)
                    previous_utility_id = self.env['utility.bill'].search(
                        [('id', 'in', record_ids.ids)], limit=1)
                    ele_id = self.env['utility.meter.reading'].search(
                        [('meter_type_id.name', '=', 'Electrical')],
                        order='id desc', limit=1)
                    gen_id = self.env['utility.meter.reading'].search(
                        [('meter_type_id.name', '=', 'Generator')],
                        order='id desc', limit=1)

                    rec.write(
                        {'rate': rec.meter_type_line_id.rate,
                         'currency_id': rec.meter_type_line_id.currency_id.id})
                    if rec.meter_type_line_id.meter_type_id.name == 'Electrical':
                        rec.write({'pre_reading': ele_id.curr_reading,
                                   'pre_reading_date': ele_id.curr_reading_date, })
                    if rec.meter_type_line_id.meter_type_id.name == 'Generator':
                        rec.write({'pre_reading': gen_id.curr_reading,
                                   'pre_reading_date': gen_id.curr_reading_date, })
                    total_consume = rec.curr_reading - rec.pre_reading
                    rec.write({'total_consume': total_consume})
                    amount = rec.total_consume * rec.rate
                    rec.write({'amount': amount})

    @api.onchange('curr_reading', 'pre_reading')
    def _onchange_curr_reading(self):
        for rec in self:
            rec.total_consume = rec.curr_reading - rec.pre_reading
            rec.amount = rec.total_consume * rec.rate
            if rec.utility_id.contract_id:
                handover_id = self.env['handover.property'].search(
                    [('contract_id', '=', rec.utility_id.contract_id.id)])
                if handover_id:
                    total_consume = rec.curr_reading - rec.pre_reading
                    rec.write({'total_consume': total_consume})
                    amount = rec.total_consume * rec.rate
                    rec.write({'amount': amount})

    @api.onchange('total_consume', 'rate')
    def _onchange_total_consume(self):
        for rec in self:
            if rec.total_consume:
                rec.amount = rec.total_consume * rec.rate

    def _compute_sr_no(self):
        no = 0
        for line in self:
            no += 1
            line.sr_no = no


class InheritAccountPayment(models.Model):
    """To add utility bill id"""
    _inherit = 'account.payment'

    utility_bill_id = fields.Many2one('utility.bill')

    def button_open_utility_bill(self):
        return {
            'name': 'Utility Bill',
            'res_model': 'utility.bill',
            'type': 'ir.actions.act_window',
            'res_id': self.utility_bill_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    @api.model
    def add_utility_bill_id_to_payments(self):
        """to link utility bill with payments"""

        records = self.env['account.payment'].sudo().search([
            ('utility_bill_id', '=', False)
        ])
        for rec in records:
            bill_id = self.env['utility.bill'].sudo().search([
                ('dn_no', '=', rec.ref)
            ])
            if bill_id:
                rec.utility_bill_id = bill_id.id
