# -*- coding: utf-8 -*-
# Copyright 2020-Today TechKhedut.
# Part of TechKhedut. See LICENSE file for full copyright and licensing details.
from odoo import fields, models, api


class TemplatePreviewWizard(models.TransientModel):
    """To Preview Dynamic Agreement Template"""
    _name = 'template.preview.wizard'
    _description = __doc__

    agreement_template_id = fields.Many2one('agreement.template', string='Agreement Template')
    agreement_body = fields.Html(compute='_compute_agreement_body')

    @api.depends('agreement_template_id', 'agreement_body')
    def _compute_agreement_body(self):
        for rec in self:
            body = self.agreement_template_id.agreement
            for var in self.agreement_template_id.template_variable_ids:
                body = body.replace(var.name, var.demo_value)
            rec.agreement_body = body
