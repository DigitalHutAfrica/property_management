import tempfile
import binascii
import xlrd
from dateutil import parser
import dateutil
from odoo import fields, models, _


class UploadUtilityExcel(models.TransientModel):
    _name = 'upload.utility.excel'
    _description = 'Upload Utility Bill Excel'

    file_name = fields.Char(string='Upload Excel File')
    file = fields.Binary(string='Utility Bill Excel')

    def upload_file(self):
        fp = tempfile.NamedTemporaryFile(delete=False, suffix='.xls')
        fp.write(binascii.a2b_base64(self.file))
        fp.seek(0)
        workbook = xlrd.open_workbook(fp.name)
        sheet = workbook.sheet_by_index(0)
        keys = [sheet.cell(0, col_index).value for col_index in
                range(sheet.ncols)]
        start_range = 1
        lines = []
        for row_index in range(start_range, sheet.nrows):
            raw_data = {keys[col_index]: sheet.cell(row_index, col_index).value
                        for col_index in
                        range(sheet.ncols)}
            lines.append(raw_data)

        for line in lines:
            records = self.env['utility.bill'].sudo()
            date = line.get('Date')
            cr_date = line.get('Utility Meter Reading/Current Reading Date')
            pr_date = line.get('Utility Meter Reading/Previous Reading Date')
            if date:
                line['Date'] = convert_to_date(date=date)
            else:
                line['Date'] = False
            if cr_date:
                line[
                    'Utility Meter Reading/Current Reading Date'] = convert_to_date(
                    date=cr_date)
            else:
                line['Utility Meter Reading/Current Reading Date'] = False
            if pr_date:
                line[
                    'Utility Meter Reading/Previous Reading Date'] = convert_to_date(
                    date=pr_date)
            else:
                line['Utility Meter Reading/Previous Reading Date'] = False
            property_id = self.env['property.details'].sudo().search(
                [('lipa_number', '=', int(line.get('Lipa Number')))], limit=1)
            tenancy_id = self.env['res.partner'].sudo().search(
                [('name', '=', line.get('Tenant').strip())], limit=1)
            meter_type_id = self.env['meter.type'].sudo().search(
                [('name', '=',
                  line.get('Utility Meter Reading/Description').strip())],
                limit=1)
            meter_type_line_id = self.env['meter.type.lines'].sudo().search(
                [('meter_type_id', '=', meter_type_id.id)],
                limit=1)
            if property_id and tenancy_id:
                utility_record = records.search(
                    [('lipa_number', '=', property_id.lipa_number),
                     ('date', '=', line.get('Date')),
                     ('tenant_name', '=', tenancy_id.id)],
                    limit=1)
                if utility_record:
                    utility_record_to_use = utility_record
                else:
                    data = {
                        'property_id': property_id.id,
                        'date': line.get('Date'),
                        'month': line.get('Month'),
                        'tenant_name': tenancy_id.id,
                        'lipa_number': property_id.lipa_number
                    }
                    utility_record_to_use = records.create(data)
                    utility_record_to_use.onchange_date()

                if meter_type_line_id:
                    self.create_lines(
                        meter_type_line_id=meter_type_line_id,
                        line=line, utility_record=utility_record_to_use
                    )
                else:
                    data = {
                        'rate': line.get('Utility Meter Reading/Rate'),
                        'currency_id': self.env.company.currency_id.id,
                        'main_property_id': property_id.parent_property_id.id if property_id.parent_property_id else False
                    }

                    if meter_type_id:
                        data['meter_type_id'] = meter_type_id.id
                    else:
                        type_data = {
                            'name': line.get(
                                'Utility Meter Reading/Description')
                        }
                        new_meter_type_id = self.env[
                            'meter.type'].sudo().create(type_data)
                        data['meter_type_id'] = new_meter_type_id.id

                    property_meter_type_line_id = self.env[
                        'meter.type.lines'].sudo().create(data)
                    self.create_lines(
                        meter_type_line_id=property_meter_type_line_id,
                        line=line, utility_record=utility_record_to_use
                    )
        return {
            'name': _('Utility Bills'),
            'res_model': 'utility.bill',
            'view_mode': 'list,form',
            'target': 'current',
            'type': 'ir.actions.act_window',
        }

    def create_lines(self, meter_type_line_id, line, utility_record):
        reading_lines = {
            'meter_type_line_id': meter_type_line_id.id,
            'curr_reading_date': line.get(
                'Utility Meter Reading/Current Reading Date'),
            'pre_reading_date': line.get(
                'Utility Meter Reading/Previous Reading Date'),
            'curr_reading': line.get('Utility Meter Reading/Current Reading'),
            'pre_reading': line.get('Utility Meter Reading/Previous Reading'),
            'total_consume': line.get('Utility Meter Reading/Total Consume'),
            'rate': line.get('Utility Meter Reading/Rate'),
            'currency_id': self.env['res.currency'].sudo().search(
                [('symbol', '=', line.get('currency_id'))]),
            'amount': line.get('Utility Meter Reading/Amount'),
            'utility_id': utility_record.id
        }
        line_id = self.env['utility.meter.reading'].sudo().create(
            reading_lines)
        line_id._onchange_total_consume()


def convert_to_date(date):
    if isinstance(date, float):
        datetime_date = xlrd.xldate_as_datetime(date, 0)
        date_date = datetime_date.date()
    else:
        datetime_date = dateutil.parser.parse(date)
        date_date = datetime_date.date()
    return date_date
