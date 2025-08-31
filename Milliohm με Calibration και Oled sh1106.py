from machine import Pin, I2C
import time
from ads1x15 import ADS1115
import sh1106    # βιβλιοθήκη για το OLED

try:
    from statistics import median
except:
    # MicroPython fallback
    def median(seq):
        s = sorted(seq)
        n = len(s)
        return s[n//2] if n % 2 else 0.5*(s[n//2-1] + s[n//2])

class MilliohmMeterPro:
    def __init__(self, i2c, address=0x48, gain=5, current=0.100):
        self.adc = ADS1115(i2c, address=address, gain=gain)
        self.current = current
        self.v_offset = 0.0
        self.scale = 1.0

    def set_current(self, amps):
        self.current = amps

    def _continuous_samples(self, n=32, rate=0, ch1=0, ch2=1):
        self.adc.conversion_start(rate=rate, channel1=ch1, channel2=ch2)
        samples = []
        for _ in range(n):
            raw = self.adc.alert_read()
            v   = self.adc.raw_to_v(raw)
            samples.append(v)
            time.sleep_ms(8)
        return samples

    def zero(self, n=64, rate=0, ch1=0, ch2=1):
        vs = self._continuous_samples(n=n, rate=rate, ch1=ch1, ch2=ch2)
        self.v_offset = median(vs)
        return self.v_offset

    def measure_once(self, n_groups=5, per_group=16, rate=0, ch1=0, ch2=1):
        group_means = []
        for _ in range(n_groups):
            vs = self._continuous_samples(n=per_group, rate=rate, ch1=ch1, ch2=ch2)
            vs_corr = [v - self.v_offset for v in vs]
            group_means.append(sum(vs_corr)/len(vs_corr))
        v_med = median(group_means)
        R = (v_med / self.current) * self.scale if self.current > 0 else None
        return R, v_med

    def calibrate_with_reference(self, R_ref_ohm, n_groups=6, per_group=20, rate=0, ch1=0, ch2=1):
        R_meas, _ = self.measure_once(n_groups=n_groups, per_group=per_group, rate=rate, ch1=ch1, ch2=ch2)
        if (R_meas is not None) and (R_meas > 0):
            self.scale = R_ref_ohm / R_meas
        return self.scale


"""
-------------------------------
Κύριο πρόγραμμα
-------------------------------
"""

# I2C setup (προσαρμόζεις SDA/SCL pins για Pico 2)
i2c = I2C(1, scl=Pin(15), sda=Pin(14), freq=400000)

# Δημιουργία οργάνου
meter = MilliohmMeterPro(i2c, current=0.100, gain=5)

# OLED setup (τυπικά διεύθυνση 0x3C)
oled = sh1106.SH1106_I2C(128, 64, i2c, addr=0x3C)

# Zero-offset
# print("=== Zero-offset ===")
# print("Βραχυκύκλωσε τα Kelvin sense leads...")
# time.sleep(5)
# offset = meter.zero(n=80, rate=0)
# print("Offset =", offset*1e6, "μV")

# Προαιρετικό Calibration
print("=== Calibration ===")
print("Σύνδεσε γνωστή αντίσταση 0.ΧΧΧ Ω")
time.sleep(5)
scale = meter.calibrate_with_reference(0.0968)
print("Scale factor =", scale)

print("=== Μετρήσεις DUT ===")

"""
        Νόμος του Ωμ        
            V
         ------- -->  V/I = R (σε mΩ)
         I  |  R
         
"""

while True:
    R, V = meter.measure_once(n_groups=7, per_group=24, rate=0)
    text_console = "U = {:.6f} V , R = {:.3f} mΩ".format(V, (R or 0)*1000)
    print(text_console)

    # OLED display
    oled.fill(0)
    oled.text("Milliohm Meter", 8, 0)
    oled.text("U: {:.6f} V".format(V), 0, 20)
    oled.text("R: {:.3f} mOHM".format((R or 0)*1000), 0, 40)
    oled.show()

    time.sleep(1)
