import logging
import time

import device
import probe
from register import *

log = logging.getLogger()

class Reg_ver(Reg, int):
    def __init__(self, base, name):
        Reg.__init__(self, base, 1, name)

    def __int__(self):
        v = self.value
        return v[0] << 16 | v[1] << 8 | v[2]

    def __str__(self):
        return '%d.%d.%d' % self.value

    def decode(self, values):
        v = values[0]
        return self.update((v >> 12, v >> 8 & 0xf, v & 0xff))


class Reg_serial(Reg, str):

    def decode(self, values):
        newval = ''.join([chr(v) for v in values])
        return self.update(newval)


class EM24_Meter(device.CustomName, device.EnergyMeter):
    productid = 0xb017
    productname = 'Carlo Gavazzi EM24 Ethernet Energy Meter'
    min_timeout = 0.5

    nr_phases_configs = [ 3, 3, 2, 1, 3 ]

    phase_configs = [
        '3P.n',
        '3P.1',
        '2P',
        '1P',
        '3P',
    ]

    switch_positions = [
        'kVARh',
        '2',
        '1',
        'Locked',
    ]


    def __init__(self, *args):
        super(EM24_Meter, self).__init__(*args)

        self.info_regs = [
            Reg_ver( 0x0302, '/HardwareVersion'),
            Reg_ver( 0x0304, '/FirmwareVersion'),
            Reg_u16( 0x1002, '/PhaseConfig', text=self.phase_configs, write=(0, 4)),
            Reg_text(0x5000, 7, '/Serial'),
        ]

    def phase_regs(self, n):
        s = 2 * (n - 1)
        return [
            Reg_s32l(0x0000 + s, '/Ac/L%d/Voltage' % n,        10, '%.1f V'),
            Reg_s32l(0x000c + s, '/Ac/L%d/Current' % n,      1000, '%.1f A'),
            Reg_s32l(0x0012 + s, '/Ac/L%d/Power' % n,          10, '%.1f W'),
            Reg_s32l(0x0040 + s, '/Ac/L%d/Energy/Forward' % n, 10, '%.1f kWh'),
        ]

    def device_init(self):
        # make sure application is set to H
        appreg = Reg_u16(0xa000)
        if self.read_register(appreg) != 7:
            self.write_register(appreg, 7)

            # read back the value in case the setting is not accepted
            # for some reason
            if self.read_register(appreg) != 7:
                log.error('%s: failed to set application to H', self)
                return

        self.read_info()

        phases = self.nr_phases_configs[int(self.info['/PhaseConfig'])]

        regs = [
            Reg_s32l(0x0028, '/Ac/Power',          10, '%.1f W'),
            Reg_u16( 0x0033, '/Ac/Frequency',      10, '%.1f Hz'),
            Reg_s32l(0x0034, '/Ac/Energy/Forward', 10, '%.1f kWh'),
            Reg_s32l(0x004e, '/Ac/Energy/Reverse', 10, '%.1f kWh'),
            Reg_u16( 0xa100, '/SwitchPos', text=self.switch_positions),
        ]

        if phases == 3:
            regs += [
                Reg_mapu16(0x0032, '/PhaseSequence', { 0: 0, 0xffff: 1 }),
            ]

        for n in range(1, phases + 1):
            regs += self.phase_regs(n)

        self.data_regs = regs
        self.nr_phases = phases

    def dbus_write_register(self, reg, path, val):
        super(EM24_Meter, self).dbus_write_register(reg, path, val)
        self.sched_reinit()

    def get_ident(self):
        return 'cg_%s' % self.info['/Serial']


class ET340_Meter(device.CustomName, device.EnergyMeter):
    productid = 0xb345
    productname = 'Carlo Gavazzi ET340 Total Energy Meter'
    min_timeout = 0.5
    nr_phases_configs = [ 3, 3, 2 ]

    phase_configs = [
      '3P.n',
      '3P',
      '2P',
    ]

    def __init__(self, *args):
        super(ET340_Meter, self).__init__(*args)

        self.info_regs = [
            Reg_u16( 0x0302, '/HardwareVersion'), # versioncode
            Reg_u16( 0x0303, '/FirmwareVersion'), # revisioncode
            Reg_u16( 0x1002, '/PhaseConfig', text=self.phase_configs, write=(0, 2)),
            Reg_serial(0x5000, 7, '/Serial'),
            Reg_u16(0x5010, '/ProductionYear'),
        ]

    def init(self, dbus):
        super(ET340_Meter, self).init(dbus)
        self.dbus.add_path('/Ac/Energy/Forward', None, writeable=True)
        self.dbus.add_path('/Ac/Energy/Reverse', None, writeable=True)
        self.energy_forward = self.ef.get_value() or 0.0
        self.energy_reverse = self.er.get_value() or 0.0
        log.info('Loaded saved energy counters: F%.6f kWh R%.6f kWh' % (self.energy_forward, self.energy_reverse))
        self.last_update = time.time()
        self.last_checkpoint = time.time()

    def phase_regs(self, n):
        s = 2 * (n - 1)
        return [
            Reg_s32l(0x0000 + s, '/Ac/L%d/Voltage' % n,        10, '%.1f V'),
            Reg_s32l(0x000c + s, '/Ac/L%d/Current' % n,      1000, '%.1f A'),
            Reg_s32l(0x0012 + s, '/Ac/L%d/Power' % n,          10, '%.1f W'),
        ]

    def init_device_settings(self, dbus):
        super(ET340_Meter, self).init_device_settings(dbus)
        path = '/Settings/Devices/' + self.get_ident()
        self.ef = self.settings.addSetting(path + '/EnergyForward', 0.0, 0, 0)
        self.er = self.settings.addSetting(path + '/EnergyReverse', 0.0, 0, 0)

    def device_init(self):
        # make sure measurement mode is set to B (1) - positive and negative power
        appreg = Reg_u16(0x1103)
        if self.read_register(appreg) != 1:
            self.write_register(appreg, 1)

            # read back the value in case the setting is not accepted
            # for some reason
            if self.read_register(appreg) != 1:
                log.error('%s: failed to set measurement mode to B', self)
                return
        else:
            log.info('%s: measurement mode confirmed to be B', self)

        self.read_info()

        phases = self.nr_phases_configs[int(self.info['/PhaseConfig'])]

        regs = [
            Reg_s32l(0x0028, '/Ac/Power',          10, '%.1f W'),
            Reg_u16( 0x0033, '/Ac/Frequency',      10, '%.1f Hz'),
        ]

        if phases == 3:
            regs += [
                Reg_mapu16(0x0032, '/PhaseSequence', { 0: 0, 0xffff: 1 }),
            ]

        for n in range(1, phases + 1):
            regs += self.phase_regs(n)

        self.data_regs = regs
        self.nr_phases = phases

    def update(self):
        super(ET340_Meter, self).update()
        now = time.time()
        dt = now - self.last_update
        # Limit update rate due to reports of the device
        # locking up with faster updates (see some commentary
        # on 2.9x release)
        if dt < 0.8:
            return
        if dt > 10:
            log.error('Update interval too long, skipping')
            return
        self.last_update = now

        power = self.dbus['/Ac/Power'].value

        energy = power * dt / 3600 / 1000 # kwh
        if energy > 0:
            self.energy_forward += energy
        else:
            self.energy_reverse += abs(energy)
        self.dbus['/Ac/Energy/Forward'] = round(self.energy_forward, 1)
        self.dbus['/Ac/Energy/Reverse'] = round(self.energy_reverse, 1)

        if now - self.last_checkpoint > 300:
            log.info('Updating saved energy: F%.6f kWh R%.6f kWh' % (self.energy_forward, self.energy_reverse))
            self.ef.set_value(self.energy_forward)
            self.er.set_value(self.energy_reverse)
            self.last_checkpoint = now
        log.debug('update: dT%.1f P%.1fW dE%f F%.6f R%.6f' % (dt, power, energy, self.energy_forward, self.energy_reverse))

    def dbus_write_register(self, reg, path, val):
        super(ET340_Meter, self).dbus_write_register(reg, path, val)
        self.sched_reinit()

    def get_ident(self):
        return 'cg_%s' % self.info['/Serial'].value



models = {
    1648: {
        'model':    'EM24DINAV23XE1X',
        'handler':  EM24_Meter,
    },
    1649: {
        'model':    'EM24DINAV23XE1PFA',
        'handler':  EM24_Meter,
    },
    1650: {
        'model':    'EM24DINAV23XE1PFB',
        'handler':  EM24_Meter,
    },
    1651: {
        'model':    'EM24DINAV53XE1X',
        'handler':  EM24_Meter,
    },
    1652: {
        'model':    'EM24DINAV53XE1PFA',
        'handler':  EM24_Meter,
    },
    1653: {
        'model':    'EM24DINAV53XE1PFB',
        'handler':  EM24_Meter,
    },
}
probe.add_handler(probe.ModelRegister(Reg_u16(0x000b), models,
                                      methods=['tcp'],
                                      units=[1]))

models_rtu = {
    345: {
        'model': 'ET340DINAV23XS1X',
        'handler': ET340_Meter,
        }
}
probe.add_handler(probe.ModelRegister(Reg_u16(0x000b), models_rtu,
                                      methods=['rtu'],
                                      rates=[9600],
                                      units=[1]))
