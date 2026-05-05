# -*- coding: utf-8 -*-
"""
Multi-Level Maintenance Approval System
========================================
Configurable approval levels per company.
Each level has its own approver and cost threshold.
Flow:
  Draft → Pending L1 → Pending L2 → Pending L3 → Approved → (maintenance continues)
                    ↘              ↘              ↘
                     Rejected (any level can reject with mandatory reason)
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


# ── Company-level approval configuration ─────────────────────────────────────

class ResCompanyApproval(models.Model):
    _inherit = 'res.company'

    # Level 1
    maint_approval_l1_enabled  = fields.Boolean(string='Enable Level 1 Approval', default=True)
    maint_approval_l1_name     = fields.Char(string='Level 1 Name', default='Property Manager')
    maint_approval_l1_group_id = fields.Many2one(
        'res.groups', string='Level 1 Approver Group',
        help="Users in this group can approve Level 1 requests.")
    maint_approval_l1_threshold = fields.Monetary(
        string='Level 1 Min Cost', default=0,
        help="Requests at or above this cost require Level 1 approval. 0 = all requests.")
    maint_approval_currency_id  = fields.Many2one(
        'res.currency', string='Approval Currency',
        default=lambda self: self.env.company.currency_id)

    # Level 2
    maint_approval_l2_enabled  = fields.Boolean(string='Enable Level 2 Approval', default=False)
    maint_approval_l2_name     = fields.Char(string='Level 2 Name', default='Finance Manager')
    maint_approval_l2_group_id = fields.Many2one(
        'res.groups', string='Level 2 Approver Group')
    maint_approval_l2_threshold = fields.Monetary(
        string='Level 2 Min Cost', default=5000,
        help="Requests at or above this cost also require Level 2 approval.")

    # Level 3
    maint_approval_l3_enabled  = fields.Boolean(string='Enable Level 3 Approval', default=False)
    maint_approval_l3_name     = fields.Char(string='Level 3 Name', default='Director')
    maint_approval_l3_group_id = fields.Many2one(
        'res.groups', string='Level 3 Approver Group')
    maint_approval_l3_threshold = fields.Monetary(
        string='Level 3 Min Cost', default=20000,
        help="Requests at or above this cost also require Level 3 approval.")


class ResConfigSettingsApproval(models.TransientModel):
    _inherit = 'res.config.settings'

    # Level 1
    maint_approval_l1_enabled   = fields.Boolean(related='company_id.maint_approval_l1_enabled',   readonly=False)
    maint_approval_l1_name      = fields.Char(related='company_id.maint_approval_l1_name',         readonly=False)
    maint_approval_l1_group_id  = fields.Many2one(related='company_id.maint_approval_l1_group_id', readonly=False)
    maint_approval_l1_threshold = fields.Monetary(related='company_id.maint_approval_l1_threshold',readonly=False)

    # Level 2
    maint_approval_l2_enabled   = fields.Boolean(related='company_id.maint_approval_l2_enabled',   readonly=False)
    maint_approval_l2_name      = fields.Char(related='company_id.maint_approval_l2_name',         readonly=False)
    maint_approval_l2_group_id  = fields.Many2one(related='company_id.maint_approval_l2_group_id', readonly=False)
    maint_approval_l2_threshold = fields.Monetary(related='company_id.maint_approval_l2_threshold',readonly=False)

    # Level 3
    maint_approval_l3_enabled   = fields.Boolean(related='company_id.maint_approval_l3_enabled',   readonly=False)
    maint_approval_l3_name      = fields.Char(related='company_id.maint_approval_l3_name',         readonly=False)
    maint_approval_l3_group_id  = fields.Many2one(related='company_id.maint_approval_l3_group_id', readonly=False)
    maint_approval_l3_threshold = fields.Monetary(related='company_id.maint_approval_l3_threshold',readonly=False)


# ── Approval level log line ───────────────────────────────────────────────────

class MaintenanceApprovalLine(models.Model):
    """One record per approval action taken on a maintenance request."""
    _name        = 'maintenance.approval.line'
    _description = 'Maintenance Approval Line'
    _order       = 'level asc, date asc'

    request_id       = fields.Many2one('maintenance.request', ondelete='cascade')
    level            = fields.Integer(string='Level')
    level_name       = fields.Char(string='Approval Level')
    state            = fields.Selection([
        ('pending',  'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], default='pending')
    approver_id      = fields.Many2one('res.users', string='Approver')
    date             = fields.Datetime(string='Date')
    note             = fields.Text(string='Note / Rejection Reason')


# ── Main approval logic on maintenance.request ────────────────────────────────

class MaintenanceRequestApproval(models.Model):
    _inherit = 'maintenance.request'

    # ── Approval state ────────────────────────────────────────────────────────
    approval_state = fields.Selection([
        ('not_required', 'Not Required'),
        ('draft',        'Draft'),
        ('pending_l1',   'Pending L1'),
        ('pending_l2',   'Pending L2'),
        ('pending_l3',   'Pending L3'),
        ('approved',     'Approved'),
        ('rejected',     'Rejected'),
    ], string='Approval Status', default='draft', tracking=True, copy=False)

    approval_line_ids = fields.One2many(
        'maintenance.approval.line', 'request_id', string='Approval Log')

    estimated_cost = fields.Monetary(
        string='Estimated Cost', tracking=True,
        currency_field='currency_id')
    actual_cost = fields.Monetary(
        string='Actual Cost', tracking=True,
        currency_field='currency_id')
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id)

    current_approver_id = fields.Many2one(
        'res.users', string='Current Approver', readonly=True)
    approved_by_ids = fields.Many2many(
        'res.users', 'maint_approved_by_rel',
        'request_id', 'user_id',
        string='Approved By', readonly=True)
    final_approved_date = fields.Datetime(
        string='Final Approval Date', readonly=True)
    rejection_reason = fields.Text(
        string='Rejection Reason', readonly=True)

    requires_approval = fields.Boolean(
        compute='_compute_requires_approval', store=False)
    approval_summary = fields.Char(
        compute='_compute_approval_summary', string='Approval Summary')

    # ── computed ──────────────────────────────────────────────────────────────

    @api.depends('estimated_cost', 'approval_state')
    def _compute_requires_approval(self):
        company = self.env.company
        for rec in self:
            rec.requires_approval = (
                company.maint_approval_l1_enabled and
                rec.estimated_cost >= (company.maint_approval_l1_threshold or 0)
            )

    @api.depends('approval_state', 'approval_line_ids')
    def _compute_approval_summary(self):
        labels = {
            'not_required': 'No approval needed',
            'draft':        'Not yet submitted',
            'pending_l1':   'Waiting for Level 1 approval',
            'pending_l2':   'Waiting for Level 2 approval',
            'pending_l3':   'Waiting for Level 3 approval',
            'approved':     'Fully approved',
            'rejected':     'Rejected',
        }
        for rec in self:
            rec.approval_summary = labels.get(rec.approval_state, '')

    # ── helpers ───────────────────────────────────────────────────────────────

    def _get_levels_required(self):
        """
        Return list of dicts describing which approval levels are required
        for this request based on estimated_cost and company config.
        """
        company  = self.env.company
        cost     = self.estimated_cost or 0
        levels   = []

        if company.maint_approval_l1_enabled and cost >= (company.maint_approval_l1_threshold or 0):
            levels.append({
                'level':     1,
                'name':      company.maint_approval_l1_name or 'Level 1',
                'group_id':  company.maint_approval_l1_group_id,
                'state_key': 'pending_l1',
            })
        if company.maint_approval_l2_enabled and cost >= (company.maint_approval_l2_threshold or 0):
            levels.append({
                'level':     2,
                'name':      company.maint_approval_l2_name or 'Level 2',
                'group_id':  company.maint_approval_l2_group_id,
                'state_key': 'pending_l2',
            })
        if company.maint_approval_l3_enabled and cost >= (company.maint_approval_l3_threshold or 0):
            levels.append({
                'level':     3,
                'name':      company.maint_approval_l3_name or 'Level 3',
                'group_id':  company.maint_approval_l3_group_id,
                'state_key': 'pending_l3',
            })
        return levels

    def _get_approvers_for_level(self, level_dict):
        """Return res.users in the approval group for this level."""
        group = level_dict.get('group_id')
        if group:
            return group.users
        # Fallback: property managers
        mgr_group = self.env.ref(
            'property_management.property_rental_manager', raise_if_not_found=False)
        return mgr_group.users if mgr_group else self.env['res.users']

    def _notify_approvers(self, level_dict, approvers):
        """Send email + WhatsApp notification to approvers."""
        subject = _('Maintenance Approval Required — %s') % self.name
        body    = _(
            '<p>Dear %s Approver,</p>'
            '<p>A maintenance request requires your approval:</p>'
            '<ul>'
            '<li><b>Request:</b> %s</li>'
            '<li><b>Property:</b> %s</li>'
            '<li><b>Estimated Cost:</b> %s %s</li>'
            '<li><b>Level:</b> %s</li>'
            '</ul>'
            '<p>Please log in to review and approve or reject.</p>'
        ) % (
            level_dict['name'],
            self.name,
            self.property_id.name if self.property_id else '—',
            self.currency_id.symbol or '',
            f'{self.estimated_cost:,.2f}',
            level_dict['name'],
        )

        for user in approvers:
            if user.email:
                self.env['mail.mail'].sudo().create({
                    'subject':       subject,
                    'body_html':     body,
                    'email_to':      user.email,
                    'email_from':    self.env.company.email or '',
                    'auto_delete':   True,
                }).send()

        # Post on chatter
        self.message_post(
            body=_('Approval request sent to %s approvers for <b>%s</b>.') % (
                len(approvers), level_dict['name']),
            subtype_xmlid='mail.mt_note',
        )

    def _notify_requestor(self, approved=True, reason=''):
        """Notify the person who created the request."""
        if not self.user_id or not self.user_id.email:
            return
        if approved:
            subject = _('✅ Maintenance Request Approved — %s') % self.name
            body    = _('<p>Your maintenance request <b>%s</b> has been fully approved and work can proceed.</p>') % self.name
        else:
            subject = _('❌ Maintenance Request Rejected — %s') % self.name
            body    = _('<p>Your maintenance request <b>%s</b> has been rejected.</p><p><b>Reason:</b> %s</p>') % (self.name, reason)
        self.env['mail.mail'].sudo().create({
            'subject':     subject,
            'body_html':   body,
            'email_to':    self.user_id.email,
            'email_from':  self.env.company.email or '',
            'auto_delete': True,
        }).send()

    # ── actions ───────────────────────────────────────────────────────────────

    def action_submit_for_approval(self):
        """Submit request — routes to first required level or auto-approves."""
        for rec in self:
            levels = rec._get_levels_required()
            if not levels:
                rec.approval_state = 'not_required'
                rec.message_post(
                    body=_('No approval required based on estimated cost.'),
                    subtype_xmlid='mail.mt_note')
                continue

            first = levels[0]
            # Create approval log lines for all levels
            rec.approval_line_ids.unlink()
            for lv in levels:
                self.env['maintenance.approval.line'].create({
                    'request_id': rec.id,
                    'level':      lv['level'],
                    'level_name': lv['name'],
                    'state':      'pending',
                })

            rec.approval_state = first['state_key']
            approvers = rec._get_approvers_for_level(first)
            if approvers:
                rec.current_approver_id = approvers[0]
            rec._notify_approvers(first, approvers)

    def action_approve(self):
        """Approve current level — advance to next or mark fully approved."""
        self.ensure_one()
        user    = self.env.user
        levels  = self._get_levels_required()
        current = self.approval_state

        # Find which level we're on
        level_map = {
            'pending_l1': 1,
            'pending_l2': 2,
            'pending_l3': 3,
        }
        current_level_num = level_map.get(current)
        if not current_level_num:
            raise UserError(_('This request is not pending approval.'))

        # Check user is in the right group
        company    = self.env.company
        level_info = next((l for l in levels if l['level'] == current_level_num), None)
        if level_info and level_info.get('group_id'):
            if user not in level_info['group_id'].users:
                raise UserError(_(
                    'Only members of "%s" can approve at this level.'
                ) % level_info['group_id'].name)

        # Mark this level approved in log
        log_line = self.approval_line_ids.filtered(
            lambda l: l.level == current_level_num and l.state == 'pending')
        if log_line:
            log_line.write({
                'state':       'approved',
                'approver_id': user.id,
                'date':        fields.Datetime.now(),
            })

        self.approved_by_ids = [(4, user.id)]

        # Find next level
        next_levels = [l for l in levels if l['level'] > current_level_num]
        if next_levels:
            nxt       = next_levels[0]
            self.approval_state = nxt['state_key']
            approvers = self._get_approvers_for_level(nxt)
            if approvers:
                self.current_approver_id = approvers[0]
            self._notify_approvers(nxt, approvers)
            self.message_post(
                body=_('<b>Level %s</b> approved by %s. Advancing to <b>%s</b>.') % (
                    current_level_num, user.name, nxt['name']),
                subtype_xmlid='mail.mt_note')
        else:
            # All levels done
            self.approval_state      = 'approved'
            self.final_approved_date = fields.Datetime.now()
            self.current_approver_id = False
            self._notify_requestor(approved=True)
            self.message_post(
                body=_('✅ <b>Fully approved</b> by %s. Work can proceed.') % user.name,
                subtype_xmlid='mail.mt_note')

    def action_reject(self):
        """Open rejection reason wizard."""
        return {
            'type':      'ir.actions.act_window',
            'name':      _('Reject Maintenance Request'),
            'res_model': 'maintenance.rejection.wizard',
            'view_mode': 'form',
            'target':    'new',
            'context':   {'default_request_id': self.id},
        }

    def action_reset_to_draft(self):
        """Allow requestor to reset and resubmit."""
        for rec in self:
            rec.approval_state      = 'draft'
            rec.rejection_reason    = False
            rec.current_approver_id = False
            rec.approved_by_ids     = [(5,)]
            rec.final_approved_date = False
            rec.approval_line_ids.unlink()
            rec.message_post(
                body=_('Request reset to draft by %s.') % self.env.user.name,
                subtype_xmlid='mail.mt_note')
