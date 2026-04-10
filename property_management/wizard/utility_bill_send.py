from odoo import api, fields, models, _
from odoo.tools.misc import get_lang


class UtilityBillSend(models.TransientModel):
    _name = 'utility.bill.send'
    _inherits = {'mail.compose.message': 'composer_id'}
    _description = 'Utility Bill Send'

    is_email = fields.Boolean('Email', default=True)
    bill_without_email = fields.Text(compute='_compute_bill_without_email',
                                     string='bill(s) that will not be sent')
    is_print = fields.Boolean('Print', default=True)
    printed = fields.Boolean('Is Printed', default=False)
    bill_ids = fields.Many2many('utility.bill', string='Utility Bills')
    composer_id = fields.Many2one('mail.compose.message', string='Composer',
                                  required=True, ondelete='cascade')
    template_id = fields.Many2one(
        'mail.template', 'Use template',
        domain="[('model', '=', 'utility.bill')]"
    )

    @api.model
    def default_get(self, fields):
        res = super(UtilityBillSend, self).default_get(fields)
        res_ids = self._context.get('active_ids')

        composer = self.env['mail.compose.message'].create({
            'composition_mode': 'comment' if len(
                res_ids) == 1 else 'mass_mail',
        })
        res.update({
            'bill_ids': res_ids,
            'composer_id': composer.id,
        })
        return res

    @api.onchange('bill_ids')
    def _compute_bill_composition_mode(self):
        for wizard in self:
            wizard.composer_id.composition_mode = 'comment' if len(
                wizard.bill_ids) == 1 else 'mass_mail'

    @api.onchange('template_id')
    def onchange_template_id(self):
        for wizard in self:
            if wizard.composer_id:
                wizard.composer_id.template_id = wizard.template_id.id
                wizard._compute_bill_composition_mode()
                # wizard.composer_id._onchange_template_id_wrapper()

    @api.onchange('is_email')
    def onchange_is_email(self):
        if self.is_email:
            res_ids = self._context.get('active_ids')
            if not self.composer_id:
                self.composer_id = self.env['mail.compose.message'].create({
                    'composition_mode': 'comment' if len(
                        res_ids) == 1 else 'mass_mail',
                    'template_id': self.template_id.id
                })
            else:
                self.composer_id.composition_mode = 'comment' if len(
                    res_ids) == 1 else 'mass_mail'
                self.composer_id.template_id = self.template_id.id
                self._compute_bill_composition_mode()
            # self.composer_id._onchange_template_id_wrapper()

    @api.onchange('is_email')
    def _compute_bill_without_email(self):
        for wizard in self:
            if wizard.is_email and len(wizard.bill_ids) > 1:
                bills = self.env['utility.bill'].search([
                    ('id', 'in', self.env.context.get('active_ids')),
                    ('tenant_name.email', '=', False)
                ])
                if bills:
                    wizard.bill_without_email = "%s\n%s" % (
                        _("The following bill(s) will not be sent by email, because the customers don't have email address."),
                        "\n".join([i.name for i in bills])
                    )
                else:
                    wizard.bill_without_email = False
            else:
                wizard.bill_without_email = False

    def _send_email(self):
        if self.is_email:
            self.composer_id._action_send_mail()

    def _print_document(self):
        self.ensure_one()
        action = self.bill_ids.print_utility_bill_report()
        action.update({'close_on_report_download': True})
        return action

    def send_and_print_action(self):
        self.ensure_one()
        if self.composition_mode == 'mass_mail' and self.template_id:
            active_ids = self.env.context.get('active_ids', self.bill_ids)
            active_records = self.env['utility.bill'].browse(active_ids)
            langs = set(active_records.mapped('tenant_name.lang'))
            for lang in langs:
                active_ids_lang = active_records.filtered(
                    lambda r: r.tenant_name.lang == lang).ids
                self_lang = self.with_context(active_ids=active_ids_lang,
                                              lang=get_lang(self.env,
                                                            lang).code)
                self_lang.onchange_template_id()
                self_lang._send_email()
        else:
            active_record = self.env['utility.bill'].browse(self.bill_ids.id)
            lang = get_lang(self.env, active_record.tenant_name.lang).code
            single_lang = self.with_context(active_ids=self.bill_ids.id,
                                            lang=lang)
            single_lang.onchange_template_id()
            single_lang._send_email()
        if self.is_print:
            return self._print_document()
        return {'type': 'ir.actions.act_window_close'}
