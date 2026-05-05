# -*- coding: utf-8 -*-
from odoo import fields, models, _
from odoo.exceptions import UserError


class MaintenanceRejectionWizard(models.TransientModel):
    _name        = 'maintenance.rejection.wizard'
    _description = 'Maintenance Rejection Wizard'

    request_id = fields.Many2one(
        'maintenance.request', string='Request', required=True)
    reason     = fields.Text(string='Rejection Reason', required=True)

    def action_confirm_reject(self):
        self.ensure_one()
        if not self.reason or not self.reason.strip():
            raise UserError(_('Please provide a rejection reason.'))

        req  = self.request_id
        user = self.env.user

        # Find current pending level
        level_map = {'pending_l1': 1, 'pending_l2': 2, 'pending_l3': 3}
        level_num = level_map.get(req.approval_state)

        if level_num:
            log_line = req.approval_line_ids.filtered(
                lambda l: l.level == level_num and l.state == 'pending')
            if log_line:
                log_line.write({
                    'state':       'rejected',
                    'approver_id': user.id,
                    'date':        fields.Datetime.now(),
                    'note':        self.reason,
                })

        req.write({
            'approval_state':   'rejected',
            'rejection_reason': self.reason,
        })
        req._notify_requestor(approved=False, reason=self.reason)
        req.message_post(
            body=_('❌ <b>Rejected</b> by %s at Level %s.<br/>Reason: %s') % (
                user.name, level_num or '?', self.reason),
            subtype_xmlid='mail.mt_note')

        return {'type': 'ir.actions.act_window_close'}
