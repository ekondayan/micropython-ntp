try:
    import usocket as socket
except ImportError:
    import socket

try:
    import ustruct as struct
except ImportError:
    import struct

try:
    import utime as time
except ImportError:
    import time

try:
    import ure as re
except ImportError:
    import re

# import machine

# Features:
# 1. calculate and compensate RTC drift
# 2. timezones
# 3. epochs
# 4. Get time in sec, ms and us
# 5. multiple servers
# 6. Logger with callback function

# TODO:
# 7. extra precision - take into account the time required to call the functions and compensate for that
# 8. daylight saving time


class Ntp:
    EPOCH_1900 = 0
    EPOCH_1970 = 1
    EPOCH_2000 = 2

    _NTP_DELTA_1900_1970 = 2208988800  # Seconds between 1900 and 1970
    _NTP_DELTA_1900_2000 = 3155673600  # Seconds between 1900 and 2000
    _NTP_DELTA_1970_2000 = 946684800   # Seconds between 1970 and 2000 = _NTP_DELTA_1900_2000 - _NTP_DELTA_1900_1970

    _logger = print
    # _extra_precision: bool = False
    _rtc = machine.RTC()
    _hosts: list = []
    _timezone: int = 0
    _rtc_last_sync: int = 0
    _drift_last_compensate: int = 0
    _drift_last_calculate: int = 0
    _ppm_drift: float = 0.0
    _ntp_timeout_s: int = 1

    # _dst_start_month = None
    # _dst_start_dow = None
    # _dst_start_hour = None
    #
    # _dst_end_month = None
    # _dst_end_dow = None
    # _dst_end_hour = None

    # @classmethod
    # def set_extra_precision(cls, on: bool = False):
    #     cls._extra_precision = on
    #
    # @classmethod
    # def extra_precision(cls):
    #     return cls._extra_precision

    @classmethod
    def set_logger(cls, callback = None):
        if callback is None or callable(callback):
            cls._logger = callback
        else:
            raise Exception('Callback parameter must be a callable object or None to set it to print()')

    @classmethod
    def set_ntp_timeout(cls, timeout_s: int = 1):
        if not instance(timeout_s, int):
            raise Exception('Timeout parameter represents seconds in integer form')

        cls._ntp_timeout_s = timeout_s

    @classmethod
    def ntp_timeout(cls):
        return cls._ntp_timeout_s

    @classmethod
    def hosts(cls):
        return tuple(cls._hosts)

    @classmethod
    def set_hosts(cls, value: list):
        cls._hosts.clear()

        for host in value:
            if Ntp.validate_hostname(host):
                cls._hosts.append(host)

    @classmethod
    def timezone(cls):
        return cls._timezone // 3600, (cls._timezone % 3600) // 60

    @classmethod
    def set_timezone(cls, hour: int, minute: int = 0):
        if (
                (minute == 0 and not (-12 <= hour <= 12)) or
                (minute == 30 and hour not in (-9, -3, 3, 4, 5, 6, 9, 10)) or
                (minute == 45 and hour not in (5, 8, 12))
        ):
            raise Exception('Timezone is invalid')

        cls._timezone = hour * 3600 + minute * 60

    @classmethod
    def time_s(cls, epoch: int = None):
        return cls.time_us(epoch) // 1000000

    @classmethod
    def time_ms(cls, epoch: int = None):
        return cls.time_us(epoch) // 1000

    @classmethod
    def time_us(cls, epoch: int = None):
        epochs = (cls._NTP_DELTA_1900_2000, cls._NTP_DELTA_1970_2000, 0)
        try:
            epoch = epochs[epoch]
        except (IndexError, TypeError):
            epoch = epochs[cls.EPOCH_2000]

        dst = 0

        # Do not take the value when on the verge of the next second
        # This is required to ensure that the sec and usec will be read within the boundaries of one second
        us = cls._rtc.datetime()[7]
        if us >= 995000:
            time.sleep_us(100000 - us)

        return (time.time() + epoch + cls._timezone + dst) * 1000000 + cls._rtc.datetime()[7]

        # +(250000 cpu ticks * (1000000 // frequency))us will negate the execution time of the below return statement
        # return ((time.time() + epoch + cls._timezone + dst) * 1000000 + cls._rtc.datetime()[7]) + (250000000000 // machine.freq())

    @classmethod
    def network_time(cls, epoch: int = None):
        if not any(cls._hosts):
            raise Exception('There are no valid Hostnames/IPs set for the time server')

        epochs = (0, cls._NTP_DELTA_1900_1970, cls._NTP_DELTA_1900_2000)
        try:
            epoch = epochs[epoch]
        except (IndexError, TypeError):
            epoch = 0

        query = bytearray(48)
        query[0] = 0x1B

        for host in cls._hosts:
            s = None
            try:
                host_addr = socket.getaddrinfo(host, 123)[0][-1]
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.settimeout(cls._ntp_timeout_s)
                s.sendto(query, host_addr)
                timestamp = time.ticks_us()
                msg = s.recv(48)
            except Exception as e:
                cls._log('(NTP) Network error: Host({}) Error({})'.format(host, str(e)))
                continue
            finally:
                if s is not None:
                    s.close()

            sec, nano = struct.unpack('!II', msg[40:48])
            if sec < epoch:
                cls._log('(NTP) Invalid packet: Host({})'.format(host))
                continue

            sec -= epoch
            micro = (nano * 1000000) >> 32
            return sec * 1000000 + micro, timestamp

        raise Exception('''Can't connect to any of the NTP servers''')

    @classmethod
    def rtc_sync(cls):
        ntp_reading = cls.network_time(cls.EPOCH_2000)

        # Negate the execution time of all the instructions up to this point
        ntp_us = ntp_reading[0] + (time.ticks_us() - ntp_reading[1])
        # +(115000 cpu ticks * (1000000 // frequency))us will negate the execution time of the functions localtime() and datetime()
        # ntp_us = ntp_reading[0] + (time.ticks_us() - ntp_reading[1]) + (115000000000 // machine.freq())
        lt = time.localtime(ntp_us // 1000000)
        cls._rtc.datetime((lt[0], lt[1], lt[2], lt[6] + 1, lt[3], lt[4], lt[5], ntp_us % 1000000))
        cls._rtc_last_sync = ntp_us

    @classmethod
    def rtc_last_sync(cls, epoch: int = None):
        epochs = (cls._NTP_DELTA_1900_2000, cls._NTP_DELTA_1970_2000, 0)
        try:
            epoch = epochs[epoch]
        except (IndexError, TypeError):
            epoch = epochs[cls.EPOCH_2000]

        return cls._rtc_last_sync + epoch * 1000000

    @classmethod
    def drift_calculate(cls):
        ntp_reading = cls.network_time(cls.EPOCH_2000)

        rtc_us = cls.time_us(Ntp.EPOCH_2000)
        # Negate the execution time of all the instructions up to this point
        ntp_us = ntp_reading[0] + (time.ticks_us() - ntp_reading[1])

        rtc_sync_delta = ntp_us - max(cls._rtc_last_sync, cls._drift_last_compensate)
        rtc_ntp_delta = rtc_us - ntp_us

        cls._ppm_drift = (rtc_ntp_delta / rtc_sync_delta) * 1000000

        cls._drift_last_calculate = ntp_us

        return cls._ppm_drift, rtc_ntp_delta

    @classmethod
    def drift_last_compensate(cls, epoch: int = None):
        epochs = (cls._NTP_DELTA_1900_2000, cls._NTP_DELTA_1970_2000, 0)
        try:
            epoch = epochs[epoch]
        except (IndexError, TypeError):
            epoch = epochs[cls.EPOCH_2000]

        return cls._drift_last_compensate + epoch * 1000000

    @classmethod
    def drift_last_calculate(cls, epoch: int = None):
        epochs = (cls._NTP_DELTA_1900_2000, cls._NTP_DELTA_1970_2000, 0)
        try:
            epoch = epochs[epoch]
        except (IndexError, TypeError):
            epoch = epochs[cls.EPOCH_2000]

        return cls._drift_last_calculate + epoch * 1000000

    @classmethod
    def drift_ppm(cls):
        return cls._ppm_drift

    @classmethod
    def set_drift_ppm(cls, ppm: float):
        if not isinstance(ppm, (float, int)):
            raise Exception('ppm parameter must be float or int')
        cls._ppm_drift = float(ppm)

    @classmethod
    def drift_us(cls, ppm_drift: float = None):
        if cls._rtc_last_sync == 0 and cls._drift_last_compensate == 0:
            return 0

        if ppm_drift is None:
            ppm_drift = cls._ppm_drift

        time = cls.time_us(cls.EPOCH_2000) - max(cls._rtc_last_sync, cls._drift_last_compensate)
        time_real = (1000000 * time) // (1000000 + ppm_drift)

        return time - time_real

    @classmethod
    def drift_compensate(cls, compensate_us: int):
        rtc_us = cls.time_us(Ntp.EPOCH_2000)
        # +(115000 cpu ticks * (1000000 / frequency)) will negate the execution time of the functions localtime() and datetime()
        # rtc_us += int(compensate_us + 115000000000 // machine.freq())
        rtc_us += compensate_us
        lt = time.localtime(rtc_us // 1000000)
        cls._rtc.datetime((lt[0], lt[1], lt[2], lt[6] + 1, lt[3], lt[4], lt[5], rtc_us % 1000000))
        # cls._rtc_last_sync = rtc_us
        cls._drift_last_compensate = rtc_us

    @staticmethod
    def validate_hostname(hostname: str):
        # strip exactly one dot from the right, if present
        if hostname[-1] == ".":
            hostname = hostname[:-1]

        if not (0 < len(hostname) <= 253):
            return False

        labels = hostname.split('.')

        # the TLD must be not all-numeric
        if re.match(r'[0-9]+$', labels[-1]):
            return False

        return True
        # allowed = re.compile(r'(?!-)[a-z0-9-]{1,63}(?<!-)$', re.IGNORECASE)
        # return all(allowed.match(label) for label in labels)

    @classmethod
    def _log(cls, message: str):
        if callable(cls._logger):
            cls._logger(message)
