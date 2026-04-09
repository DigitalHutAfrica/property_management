import qrcode
import base64
import uuid
from io import BytesIO
from odoo import fields, models, api, _


class MaintenanceEquipment(models.Model):
    _inherit = 'maintenance.equipment'

    main_property_id = fields.Many2one('parent.property', string='Main Property')
    inspection_parameter_line_ids = fields.One2many('inspection.parameter.lines',
                                                    'maintenance_equipment_id')
    qr_code = fields.Binary(string='QR Code', compute='_compute_qr_code')
    access_token = fields.Char(string='Access Token')
    technician_ids = fields.Many2many('res.users', string='Technicians')

    @api.returns('self', lambda value: value.id)
    def copy(self, default=None):
        """ To get same inspection parameter lines in copied record """
        if default is None:
            default = {}
        # add (copy) in name off the copied record
        if not default.get('name'):
            default['name'] = _('%s(Copy)', self.name)
        res = super(MaintenanceEquipment, self).copy(default)

        if self.inspection_parameter_line_ids:
            for line in self.inspection_parameter_line_ids:
                line.copy({
                    'maintenance_equipment_id': res.id
                })
        return res

    @api.model_create_multi
    def create(self, vals_list):
        res = super(MaintenanceEquipment, self).create(vals_list)
        for rec in res:
            rec.access_token = str(uuid.uuid4())
        return res

    @api.depends('category_id', 'name', 'access_token')
    def _compute_qr_code(self):
        for rec in self:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=3,
                border=4,
            )
            data = f''' Equipment: {rec.name},\n
                    Equipment Category: {rec.category_id.name}, 
                    Access Token: {rec.access_token}'''
            qr.add_data(data)
            qr.make(fit=True)
            img = qr.make_image()
            temp = BytesIO()
            img.save(temp, format="PNG")
            qr_image = base64.b64encode(temp.getvalue())
            rec.qr_code = qr_image


class MaintenanceEquipmentCategory(models.Model):
    _inherit = 'maintenance.equipment.category'

    inspection_parameter_ids = fields.One2many('inspection.parameters', 'equipment_category_id')


class InspectionParameters(models.Model):
    _name = 'inspection.parameters'
    _description = 'Inspection Parameters'

    name = fields.Char(string='Description')
    inspection_frequency = fields.Selection(
        [('monthly', 'Monthly'), ('quarterly', 'Quarterly'), ('half_yearly', 'Half Yearly'),
         ('yearly', 'Yearly')],
        string='Inspection Frequency')
    param_val = fields.Float("Parameter Value")
    param_unit_id = fields.Many2one("uom.uom", "Parameter Unit")
    equipment_category_id = fields.Many2one('maintenance.equipment.category')


class InspectionParameterLines(models.Model):
    _name = 'inspection.parameter.lines'
    _description = 'Inspection Parameter Lines'

    name = fields.Char(string='Description')
    inspection_frequency = fields.Selection(
        [('daily', 'Daily'), ('weekly', 'Weekly'), ('monthly', 'Monthly'),
         ('quarterly', 'Quarterly'), ('half_yearly', 'Half Yearly'),
         ('yearly', 'Yearly')],
        string='Inspection Frequency')
    param_val = fields.Float("Parameter Value")
    param_unit_id = fields.Many2one("uom.uom", "Parameter Unit")
    maintenance_equipment_id = fields.Many2one('maintenance.equipment')
