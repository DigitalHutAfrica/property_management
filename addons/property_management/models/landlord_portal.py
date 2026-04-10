# -*- coding: utf-8 -*-
from odoo import fields, models, api


class ResPartnerLandlordPortal(models.Model):
    """Landlord portal access - detected via portal user account, no extra column."""
    _inherit = "res.partner"

    has_landlord_portal = fields.Boolean(
        string="Has Landlord Portal",
        compute="_compute_has_landlord_portal",
        help="True if this landlord has a portal user account."
    )

    def _compute_has_landlord_portal(self):
        portal_group = self.env.ref("base.group_portal")
        for rec in self:
            portal_user = rec.user_ids.filtered(
                lambda u: portal_group in u.groups_id
            )
            rec.has_landlord_portal = bool(portal_user) and rec.is_landlord

    def action_grant_landlord_portal(self):
        """Invite landlord as portal user."""
        for rec in self:
            if not rec.email:
                continue
            existing = self.env["res.users"].sudo().search(
                [("partner_id", "=", rec.id)], limit=1
            )
            if not existing:
                portal_group = self.env.ref("base.group_portal")
                self.env["res.users"].sudo().create({
                    "name": rec.name,
                    "login": rec.email,
                    "email": rec.email,
                    "partner_id": rec.id,
                    "groups_id": [(6, 0, [portal_group.id])],
                })
            else:
                portal_group = self.env.ref("base.group_portal")
                if portal_group not in existing.groups_id:
                    existing.sudo().write({
                        "groups_id": [(4, portal_group.id)]
                    })

    def action_revoke_landlord_portal(self):
        """Remove portal access from landlord."""
        portal_group = self.env.ref("base.group_portal")
        for rec in self:
            portal_user = rec.user_ids.filtered(
                lambda u: portal_group in u.groups_id
            )
            if portal_user:
                portal_user.sudo().write({
                    "groups_id": [(3, portal_group.id)]
                })
