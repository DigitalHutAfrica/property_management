from odoo import fields, api, models


class BookingWizard(models.TransientModel):
    _name = 'booking.wizard'
    _description = 'Create Booking While Property on Sale'

    customer_id = fields.Many2one('res.partner', string='Customer', domain="[('is_customer','=', True)]")
    property_id = fields.Many2one('property.details', string='Property')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', string='Currency')
    book_price = fields.Monetary(related="property_id.token_amount", string="Book Price")
    ask_price = fields.Monetary(string="Ask Price")
    sale_price = fields.Monetary(related="property_id.sale_price", string="Sale Price")

    is_any_broker = fields.Boolean(string='Any Broker?')
    broker_id = fields.Many2one('res.partner', string='Broker')
    commission_type = fields.Selection([('f', 'Fix'), ('p', 'Percentage')], string="Commission Type")
    broker_commission = fields.Monetary(string='Commission')
    broker_commission_percentage = fields.Float(string='Percentage')
    commission_from = fields.Selection([('customer', 'Customer'), ('landlord', 'Landlord',)], default='customer',
                                       string="Commission From")
    from_inquiry = fields.Boolean('From Inquiry')
    inquiry_id = fields.Many2one('sale.inquiry', string="Inquiry")
    note = fields.Text(string="Note")

    def create_booking_action(self):
        self.customer_id.user_type = "customer"
        self.customer_id.is_customer = True
        lead = self._context.get('from_crm')
        data = {
            'customer_id': self.customer_id.id,
            'property_id': self.property_id.id,
            'ask_price': self.ask_price,
            'is_any_broker': self.is_any_broker,
            'broker_id': self.broker_id.id,
            'commission_type': self.commission_type,
            'broker_commission': self.broker_commission,
            'broker_commission_percentage': self.broker_commission_percentage,
            'stage': 'booked',
            'commission_from': self.commission_from
        }
        booking_id = self.env['property.vendor'].create(data)
        self.property_id.sold_booking_id = booking_id.id
        mail_template = self.env.ref('rental_management.property_book_mail_template')
        if mail_template:
            mail_template.send_mail(booking_id.id, force_send=True)
        record = {
            'product_id': self.env.ref('rental_management.property_product_1').id,
            'name': 'Booked Amount of   ' + booking_id.property_id.name,
            'quantity': 1,
            'price_unit': booking_id.book_price
        }
        invoice_lines = [(0, 0, record)]
        data = {
            'partner_id': booking_id.customer_id.id,
            'move_type': 'out_invoice',
            'invoice_date': fields.Date.today(),
            'invoice_line_ids': invoice_lines
        }
        book_invoice_id = self.env['account.move'].sudo().create(data)
        book_invoice_id.sold_id = booking_id.id
        book_invoice_id.action_post()
        booking_id.book_invoice_id = book_invoice_id.id
        booking_id.book_invoice_state = True
        booking_id.property_id.stage = 'booked'
        booking_id.stage = 'booked'
        return {
            'type': 'ir.actions.act_window',
            'name': 'Property Booking',
            'res_model': 'property.vendor',
            'res_id': booking_id.id,
            'view_mode': 'form,list',
            'target': 'current'
        }

    @api.onchange('from_inquiry')
    def _onchange_property_sale_inquiry(self):
        inquiry_ids = self.env['sale.inquiry'].search([('property_id', '=', self.property_id.id)]).mapped('id')
        for rec in self:
            if not rec.from_inquiry:
                return
            return {'domain': {'inquiry_id': [('id', 'in', inquiry_ids)]}}

    @api.onchange('inquiry_id')
    def _onchange_ask_price(self):
        for rec in self:
            if not rec.from_inquiry and not rec.inquiry_id:
                return
            rec.ask_price = rec.inquiry_id.ask_price
            rec.note = rec.inquiry_id.note
            rec.customer_id = rec.inquiry_id.customer_id.id
