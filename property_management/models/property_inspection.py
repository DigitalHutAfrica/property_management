from odoo import fields, models, api, _


class PropertyMaintenance(models.Model):
    _name = "property.maintenance"
    _description = "A model for inspection"
    _rec_name = 'project'

    name = fields.Char(string="Title")
    access_token = fields.Char()
    supervisor_id = fields.Many2one("res.users", string="Technician")
    month = fields.Date(string="Date", default=fields.Date.today())
    project = fields.Many2one("parent.property", string="Project")
    property_maintenance_line_ids = fields.One2many(
        "property.maintenance.lines",
        "property_maintenance_id", string="Items")
    maintenance_template_id = fields.Many2one("maintenance.template",
                                              string="Maintenance Template")
    equipment_id = fields.Many2one('maintenance.equipment', string='Equipment')
    inspection_frequency = fields.Selection(
        [('daily', 'Daily'), ('weekly', 'Weekly'), ('monthly', 'Monthly'),
         ('quarterly', 'Quarterly'),
         ('half_yearly', 'Half Yearly'), ('yearly', 'Yearly')],
        string='Inspection Frequency')
    status = fields.Selection([('open', 'Open'), ('close', 'Close')],
                              compute='_compute_status',
                              search="_search_status")

    @api.depends('property_maintenance_line_ids', 'property_maintenance_line_ids.status')
    def _compute_status(self):
        for rec in self:
            status = 'open'
            if all(status == 'closed' for status in
                   set(rec.property_maintenance_line_ids.mapped('status'))):
                status = 'close'
            rec.status = status

    def _search_status(self, operator, value):
        inspections = []
        inspection_ids = self.env['property.maintenance'].search([])
        for rec in inspection_ids:
            if operator == '=' and rec.status == value:
                inspections.append(rec.id)
            if operator == 'in' and rec.status in value:
                inspections.append(rec.id)
        return [('id', 'in', inspections)]

    @api.onchange('equipment_id', 'inspection_frequency')
    def onchange_equipment_technician(self):
        lines = []
        self.property_maintenance_line_ids = [(5, 0, 0)]
        for rec in self.equipment_id.inspection_parameter_line_ids:
            if rec.inspection_frequency == self.inspection_frequency:
                lines.append((0, 0, {
                    'inspection_parameter_line_id': rec.id,
                    'param_val': rec.param_val,
                    'param_unit_id': rec.param_unit_id.id,
                    'property_maintenance_id': self.id,
                }))
        self.property_maintenance_line_ids = lines

    @api.onchange('maintenance_template_id')
    def onchange_template_lines(self):
        lines = []
        self.property_maintenance_line_ids = [(5, 0, 0)]
        for rec in self.maintenance_template_id.list_item_ids:
            lines.append((0, 0, {
                'name': rec.name,
                'sequence': rec.sequence,
                'display_type': rec.display_type
            }))
        self.property_maintenance_line_ids = lines


class PropertyMaintenanceLines(models.Model):
    _name = "property.maintenance.lines"
    _description = "Property Maintenance Lines"

    name = fields.Char(string="Description")
    inspection_parameter_line_id = fields.Many2one(
        'inspection.parameter.lines', string='Inspection Parameters',
        domain="[('inspection_frequency', '=', inspection_frequency)]")
    inspection_frequency = fields.Selection(
        related='property_maintenance_id.inspection_frequency')
    status = fields.Selection(
        [("open", "Open"), ("closed", "Closed"), ("yes", "Yes"), ("no", "No"), ("good", "Good"),
         ("bad", "Bad"), ("high", "High"), ("medium", "Medium"), ("maximum", "Maximum"),
         ("normal", "Normal"), ("abnormal", "Abnormal")],
        string="Status")
    remark = fields.Char(string="Remark")
    property_maintenance_id = fields.Many2one("property.maintenance")
    param_val = fields.Float("Parameter Value")
    param_unit_id = fields.Many2one("uom.uom", "Parameter Unit")
    display_type = fields.Selection(
        selection=[
            ('line_section', "Section"),
            ('line_note', "Note"),
        ],
        default=False)
    sequence = fields.Integer()
