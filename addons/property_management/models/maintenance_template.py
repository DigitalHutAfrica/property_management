from odoo import fields, models


class MaintenanceTemplate(models.Model):
    _name = 'maintenance.template'
    _description = 'Maintenance Template For Inspection'

    name = fields.Char(string="Title")
    list_item_ids = fields.One2many("maintenance.template.lines", "maintenance_template_id",
                                    string="List of Items")
    property_inspection_id = fields.Many2one("property.maintenance")


class MaintenanceTemplateLines(models.Model):
    _name = "maintenance.template.lines"
    _description = "List of Items"

    maintenance_template_id = fields.Many2one("maintenance.template")
    name = fields.Char(string="Description")
    display_type = fields.Selection(
        selection=[
            ('line_section', "Section"),
            ('line_note', "Note"),
        ],
        default=False)
    sequence = fields.Integer()
