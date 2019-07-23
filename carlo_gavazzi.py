import logging
import sys

import device
from register import *
from utils import *

class Reg_cgver(Reg, int):
    def __new__(cls, *args):
        return int.__new__(cls)

    def __int__(self):
        v = self.value
        return v[0] << 16 | v[1] << 8 | v[2]

    def __str__(self):
        return '%d.%d.%d' % self.value

    def decode(self, values):
        v = values[0]
        return self.update((v >> 12, v >> 8 & 0xf, v & 0xff))

class CG_EM24_Meter(device.ModbusDevice):
    productid = 0xb002
    productname = 'Carlo Gavazzi EM24 Energy Meter'
    default_role = 'grid'
    default_instance = 40

    def __init__(self, *args):
        device.ModbusDevice.__init__(self, *args)

        self.info_regs = [
            Reg_cgver( 0x0302, 1, '/HardwareVersion'),
            Reg_cgver( 0x0304, 1, '/FirmwareVersion'),
            Reg_text(  0x5000, 7, '/Serial'),
        ]

        self.data_regs = [[
            Reg_int32( 0x0000, 2, '/Ac/L1/Voltage',        10,   '%.1f V'),
            Reg_int32( 0x0002, 2, '/Ac/L2/Voltage',        10,   '%.1f V'),
            Reg_int32( 0x0004, 2, '/Ac/L3/Voltage',        10,   '%.1f V'),
            Reg_int32( 0x000c, 2, '/Ac/L1/Current',        1000, '%.1f A'),
            Reg_int32( 0x000e, 2, '/Ac/L2/Current',        1000, '%.1f A'),
            Reg_int32( 0x0010, 2, '/Ac/L3/Current',        1000, '%.1f A'),
            Reg_int32( 0x0012, 2, '/Ac/L1/Power',          10,   '%.1f W'),
            Reg_int32( 0x0014, 2, '/Ac/L2/Power',          10,   '%.1f W'),
            Reg_int32( 0x0016, 2, '/Ac/L3/Power',          10,   '%.1f W'),
            Reg_int32( 0x0028, 2, '/Ac/Power',             10,   '%.1f W'),
            Reg_uint16(0x0033, 1, '/Ac/Frequency',         10,   '%.1f Hz'),
            Reg_int32( 0x0034, 2, '/Ac/Energy/Forward',    10,   '%.1f kWh'),
            Reg_int32( 0x0040, 2, '/Ac/L1/Energy/Forward', 10,   '%.1f kWh'),
            Reg_int32( 0x0042, 2, '/Ac/L2/Energy/Forward', 10,   '%.1f kWh'),
            Reg_int32( 0x0044, 2, '/Ac/L3/Energy/Forward', 10,   '%.1f kWh'),
            Reg_int32( 0x004e, 2, '/Ac/Energy/Reverse',    10,   '%.1f kWh'),
        ]]

    def get_ident(self):
        return 'cg_%s' % self.info['/Serial']

cg_models = {
    1648: {
        'model':    'EM24DINAV23XE1X',
        'handler':  CG_EM24_Meter
    },
    1649: {
        'model':    'EM24DINAV23XE1PFA',
        'handler':  CG_EM24_Meter,
    },
    1650: {
        'model':    'EM24DINAV23XE1PFB',
        'handler':  CG_EM24_Meter,
    },
    1651: {
        'model':    'EM24DINAV53XE1X',
        'handler':  CG_EM24_Meter,
    },
    1652: {
        'model':    'EM24DINAV53XE1PFA',
        'handler':  CG_EM24_Meter,
    },
    1653: {
        'model':    'EM24DINAV53XE1PFB',
        'handler':  CG_EM24_Meter,
    },
}

def probe(modbus, unit):
    try:
        logging.disable(logging.ERROR)
        with timeout(modbus, 0.1):
            rr = modbus.read_holding_registers(0xb, 1, unit=unit)
        m = cg_models[rr.registers[0]]
        return m['handler'](modbus, unit, m['model'])
    except:
        return None
    finally:
        logging.disable(logging.NOTSET)

__all__ = ['probe']

device.register(sys.modules[__name__])